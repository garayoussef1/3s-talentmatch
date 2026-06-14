from __future__ import annotations

import json
import math
import os
from pathlib import Path
from uuid import UUID
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_recruteur_or_admin
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.models.match import Match
from app.models.notification import Notification
from app.models.user import User
from app.schemas.matching import MatchCandidatesResponse, MatchCandidateItem
from app.services.matching.match_engine import MatchEngine
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.services.matching_sandbox.ml_scorer import SandboxMLScorer
from app.services.matching_sandbox.report_generator import ReportGenerator
from app.services.ai_summary.claude_summarizer import ClaudeSummarizer
from app.services.access_logger import log_access, MATCH_LAUNCHED

router = APIRouter()

# Singletons — chargés une seule fois au démarrage du serveur
_heuristic_engine: Optional[Any] = None
_ml_scorer: Optional[Any] = None
_bert_scorer: Optional[Any] = None
_bert_base_scorer: Optional[Any] = None
_bert_v2_scorer: Optional[Any] = None
_report_generator: Optional[ReportGenerator] = None
_claude_summarizer: Optional[ClaudeSummarizer] = None
_fusion_mlp_model: Optional[Any] = None   # False si chargement échoué, None si pas encore tenté

_BERT_V2_MODEL_PATH  = str(Path(__file__).resolve().parents[2] / "data" / "models" / "talentmatch-bert-v2.0")
_FUSION_MLP_PATH     = str(Path(__file__).resolve().parents[3] / "data" / "models" / "fusion_mlp" / "fusion_mlp.pt")


# ── MLP Fusion (PyTorch) ──────────────────────────────────────────────────────
def _get_fusion_mlp():
    """Charge le MLP Fusion v3.0 (7->64->32->1) depuis le fichier .pt.
    Retourne le modèle si disponible, None sinon (fallback sur poids fixes).
    """
    global _fusion_mlp_model
    if _fusion_mlp_model is not None:
        return _fusion_mlp_model if _fusion_mlp_model is not False else None

    try:
        import torch
        import torch.nn as nn

        class _FusionMLP(nn.Module):
            def __init__(self):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Linear(7, 64),  nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
                    nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
                    nn.Linear(32, 1),  nn.Sigmoid(),
                )
            def forward(self, x):
                return self.net(x).squeeze(-1)

        model = _FusionMLP()
        model.load_state_dict(torch.load(_FUSION_MLP_PATH, map_location="cpu"))
        model.eval()
        _fusion_mlp_model = model
        print(f"[Fusion MLP v3.0] Chargé depuis {_FUSION_MLP_PATH}")
        return model
    except FileNotFoundError:
        print(f"[Fusion MLP] Modèle non trouvé — fallback sur poids fixes. "
              f"Lancez generate_mlp_dataset_fusion.py + train_mlp_fusion.py pour l'entraîner.")
        _fusion_mlp_model = False
        return None
    except Exception as exc:
        print(f"[Fusion MLP] Erreur de chargement : {exc}")
        _fusion_mlp_model = False
        return None


def _compute_skills_raw(offer_skills: list, cv_skills: list) -> float:
    """Ratio brut compétences matchées — sans boost BERT. Feature clé pour hors-domaine."""
    from rapidfuzz import fuzz as _rfuzz
    from app.services.matching.match_engine import _normalize_skill
    if not offer_skills:
        return 0.5
    matches = 0
    for req in offer_skills:
        req_n = _normalize_skill(req)
        for cv_s in cv_skills:
            if req_n == _normalize_skill(cv_s) or _rfuzz.token_set_ratio(req_n, _normalize_skill(cv_s)) >= 80:
                matches += 1
                break
    return round(min(1.0, matches / len(offer_skills)), 4)


def _get_heuristic_engine():
    global _heuristic_engine
    if _heuristic_engine is None:
        _heuristic_engine = MatchEngine()
    return _heuristic_engine


def _get_ml_scorer():
    global _ml_scorer
    if _ml_scorer is None:
        _ml_scorer = SandboxMLScorer()
    return _ml_scorer


def _get_bert_scorer():
    global _bert_scorer
    if _bert_scorer is None:
        _bert_scorer = BERTMatchingScorer()
    return _bert_scorer


def _get_bert_base_scorer():
    global _bert_base_scorer
    if _bert_base_scorer is None:
        _bert_base_scorer = BERTMatchingScorer(model_name="paraphrase-multilingual-MiniLM-L12-v2")
        _bert_base_scorer.model_name    = "paraphrase-multilingual-MiniLM-L12-v2"
        _bert_base_scorer.model_version = "Base (paraphrase-multilingual)"
    return _bert_base_scorer


def _get_bert_v2_scorer():
    global _bert_v2_scorer
    if _bert_v2_scorer is None:
        _bert_v2_scorer = BERTMatchingScorer(model_name=_BERT_V2_MODEL_PATH)
        _bert_v2_scorer.model_name    = "TalentMatch-BERT-v2.0"
        _bert_v2_scorer.model_version = "TalentMatch-BERT v2.0 (Google Colab — bilingue FR/EN)"
        # Désactiver le MLP : les poids MLP actuels sont calibrés pour BGE-M3
        # → utiliser la formule pondérée avec les features du modèle fine-tuné
        _bert_v2_scorer._disable_mlp = True
    return _bert_v2_scorer


def _get_report_generator():
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator()
    return _report_generator


def _get_claude_summarizer():
    global _claude_summarizer
    if _claude_summarizer is None:
        _claude_summarizer = ClaudeSummarizer()
    return _claude_summarizer


def _parse_details(details_text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not details_text:
        return None
    try:
        return json.loads(details_text)
    except Exception:
        return None


@router.post(
    "/match/{job_offer_id}",
    response_model=MatchCandidatesResponse,
    summary="Matcher les candidats d'une offre (recruteur/admin)",
)
def match_candidates_for_offer(
    job_offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == job_offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    if current_user.role.value != "admin" and offer.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")

    log_access(db, MATCH_LAUNCHED, current_user, resource_type="job_offer", resource_id=str(job_offer_id), detail=offer.titre)

    # Traiter uniquement les candidats qui ont un Match existant pour cette offre.
    # (identique au sandbox — évite de lancer BERT sur toute la base en une seule requête)
    candidates: List[Candidate] = (
        db.query(Candidate)
        .join(Match, Match.candidate_id == Candidate.id)
        .filter(Match.job_offer_id == job_offer_id)
        .order_by(Candidate.created_at.desc())
        .all()
    )

    bert = _get_bert_scorer()
    results: List[MatchCandidateItem] = []

    for candidate in candidates:
        b_score, b_details = bert.score(offer, candidate)

        # Mettre à jour le Match en base
        m = (
            db.query(Match)
            .filter(Match.job_offer_id == job_offer_id, Match.candidate_id == candidate.id)
            .first()
        )
        if m:
            m.score = float(b_score)
            m.details = json.dumps(b_details, ensure_ascii=False)

        results.append(
            MatchCandidateItem(
                candidate_id=str(candidate.id),
                cv_id=candidate.cv_id,
                candidate_name=candidate.nom,
                candidate_email=candidate.email,
                score=float(b_score),
                details=b_details,
                bert_details=b_details,
                inconsistencies=b_details.get("inconsistencies", []),
            )
        )

    db.commit()

    # Auto-dismiss new_cv notifications liées à cette offre pour le recruteur courant
    try:
        db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.type == "new_cv",
            Notification.link == f"/offers/{job_offer_id}",
            Notification.is_read == False,
        ).update({"is_read": True})
        db.commit()
    except Exception:
        pass

    results.sort(key=lambda r: r.score, reverse=True)

    return MatchCandidatesResponse(
        job_offer_id=str(job_offer_id),
        total=len(results),
        results=results,
    )


@router.post(
    "/match-sandbox/{job_offer_id}",
    summary="Comparer matching heuristique vs IA sandbox (non destructif)",
)
def match_candidates_for_offer_sandbox(
    job_offer_id: UUID,
    alpha: float = 0.6,
    engine: str = "heuristic_ml",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == job_offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    # Tout recruteur/admin peut lancer le matching sur n'importe quelle offre

    alpha = max(0.0, min(1.0, float(alpha)))
    engine = (engine or "heuristic_ml").strip().lower()
    if engine not in {"heuristic_ml", "bert", "compare_all", "heuristic", "hybrid", "bert_v2", "fusion"}:
        raise HTTPException(
            status_code=400,
            detail="engine must be one of: heuristic_ml, bert, compare_all, heuristic, hybrid, bert_v2, fusion",
        )

    # Sandbox : matcher uniquement les candidats qui ont postulé à CETTE offre.
    candidates: List[Candidate] = (
        db.query(Candidate)
        .join(Match, Match.candidate_id == Candidate.id)
        .filter(Match.job_offer_id == job_offer_id)
        .order_by(Candidate.created_at.desc())
        .all()
    )

    heuristic_engine = _get_heuristic_engine()
    bert = _get_bert_v2_scorer() if engine == "bert_v2" else _get_bert_scorer()
    bert_base = _get_bert_base_scorer() if engine == "compare_all" else None
    report_gen = _get_report_generator() if engine == "compare_all" else None
    summarizer = _get_claude_summarizer() if engine == "compare_all" else None
    # Pour le mode fusion : BGE-M3 (bert) + BERT v2 (bert_fusion_v2)
    bert_fusion_v2 = _get_bert_v2_scorer() if engine == "fusion" else None

    bert_weight       = max(0.0, min(1.0, float(alpha)))
    heuristic_weight  = 1.0 - bert_weight

    # ── Calcul des scores pour tous les candidats ─────────────────────────
    raw_data: List[Dict[str, Any]] = []
    for candidate in candidates:
        h_score, h_details = heuristic_engine.score(offer, candidate)
        b_score, b_details = bert.score(offer, candidate)
        base_raw = float(bert_base.score(offer, candidate)[0]) if bert_base else None
        bv2_score_raw, bv2_details_raw = (
            bert_fusion_v2.score(offer, candidate) if bert_fusion_v2 else (None, None)
        )

        raw_data.append({
            "candidate":         candidate,
            "heuristic_score":   float(h_score),
            "heuristic_details": h_details,
            "bert_score":        float(b_score),
            "bert_details":      b_details,
            "base_score_raw":    base_raw,
            "bv2_score":         float(bv2_score_raw) if bv2_score_raw is not None else None,
            "bv2_details":       bv2_details_raw,
        })

    # ── Scores absolus — aucune normalisation batch ──────────────────────
    # Le score 4-dimensions est déjà calibré de manière absolue :
    #   · Candidat parfait (toutes dimensions = 1.0)  → ~90-95%
    #   · Candidat hors-domaine (skills < 15%)        → ≤ 25% (plafond)
    #   · Candidat partiel (60% skills, exp correcte) → ~55-70%
    # Un plancher cosmétique à 5% évite l'affichage de 0.0%.

    results: List[Dict[str, Any]] = []
    for idx_raw, d in enumerate(raw_data):
        candidate         = d["candidate"]
        heuristic_score   = d["heuristic_score"]
        heuristic_details = d["heuristic_details"]
        bert_score        = round(float(d["bert_score"]), 4)
        bert_details      = d["bert_details"]
        base_score        = round(d["base_score_raw"], 4) if d["base_score_raw"] is not None else None
        bv2_score         = round(d["bv2_score"], 4) if d.get("bv2_score") is not None else None
        bv2_details       = d.get("bv2_details") or {}

        hybrid_score = round(max(0.0, min(1.0,
            (bert_weight * bert_score) + (heuristic_weight * heuristic_score),
        )), 4)

        row: Dict[str, Any] = {
            "candidate_id":    str(candidate.id),
            "cv_id":           candidate.cv_id,
            "candidate_name":  candidate.nom,
            "candidate_email": candidate.email,
        }

        if engine == "heuristic":
            row.update({
                "score":              round(heuristic_score, 4),
                "heuristic_score":    round(heuristic_score, 4),
                "heuristic_details":  heuristic_details,
            })
        elif engine in ("bert", "bert_v2"):
            row.update({
                "score":           bert_score,
                "bert_score":      bert_score,
                "bert_details":    bert_details,
                "inconsistencies": bert_details.get("inconsistencies", []),
            })
        elif engine == "fusion":
            # ── Fusion intelligente : MLP appris ou poids fixes ───────────────
            # Features (0-1) : exactement celles utilisées à l'entraînement
            _sem_bge  = bert_details.get("semantique",  50) / 100
            _comp_bge = bert_details.get("competences", 50) / 100
            _exp_bge  = bert_details.get("experience",  50) / 100
            _form_bge = bert_details.get("formation",   50) / 100
            _sem_v2   = bv2_details.get("semantique",   50) / 100

            # Nouvelles features v3.0 : discriminantes hors-domaine et formation
            from app.services.matching.match_engine import (
                _extract_offer_skills, _candidate_skills,
                _candidate_education_level, _extract_required_education_level,
                _normalize_offer_text,
            )
            _offer_skills_raw = _extract_offer_skills(offer)
            _cv_skills_raw    = _candidate_skills(candidate)
            _skills_raw       = _compute_skills_raw(_offer_skills_raw, _cv_skills_raw)
            _desc_blob        = _normalize_offer_text(
                ((offer.description or "") + "\n" + (offer.titre or "")).strip()
            )
            _req_edu_raw  = getattr(offer, "experience_requise", None)
            _req_edu      = _extract_required_education_level(_desc_blob) or 0
            _cand_edu     = _candidate_education_level(candidate)
            _edu_gap_norm = max(-1.0, min(1.0, (_req_edu - _cand_edu) / 5.0))

            fusion_mlp = _get_fusion_mlp()
            mlp_used   = False

            if fusion_mlp is not None:
                # ── MLP Fusion entraîné v3.0 (7 features) ────────
                try:
                    import torch
                    features_t = torch.tensor(
                        [[_sem_bge, _comp_bge, _exp_bge, _form_bge, _sem_v2,
                          _skills_raw, _edu_gap_norm]],
                        dtype=torch.float32,
                    )
                    with torch.no_grad():
                        score_fused = float(fusion_mlp(features_t).item())
                    score_fused = round(max(0.02, min(0.95, score_fused)), 4)
                    mlp_used = True
                except Exception as _mlp_err:
                    print(f"[Fusion MLP] Erreur inference: {_mlp_err}", flush=True)
                    fusion_mlp = None  # fallback si erreur inférence

            if not mlp_used:
                # ── Fallback : poids fixes (avant entraînement du MLP) ───────
                # Compétences : BGE-M3 plus fiable (768M params, multilingual)
                # Sémantique : BERT v2 plus fiable (fine-tuné sur CVs FR)
                _comp_v2 = bv2_details.get("competences", 50) / 100
                _exp_v2  = bv2_details.get("experience",  50) / 100
                comp_f   = 0.65 * _comp_bge + 0.35 * _comp_v2
                sem_f    = 0.35 * _sem_bge  + 0.65 * _sem_v2
                exp_f    = 0.50 * _exp_bge  + 0.50 * _exp_v2
                score_fused = round(
                    max(0.05, min(0.95,
                        0.50 * comp_f + 0.25 * exp_f + 0.15 * _form_bge + 0.10 * sem_f,
                    )), 4
                )

            # ── Dimensions fusionnées (pour affichage frontend) ───────────────
            _comp_v2_d = bv2_details.get("competences", 50) / 100
            _exp_v2_d  = bv2_details.get("experience",  50) / 100
            fused_details = {
                **bert_details,
                "competences": round((0.65 * _comp_bge + 0.35 * _comp_v2_d) * 100, 1),
                "semantique":  round((0.35 * _sem_bge  + 0.65 * _sem_v2)    * 100, 1),
                "experience":  round((0.50 * _exp_bge  + 0.50 * _exp_v2_d)  * 100, 1),
                "formation":   round(_form_bge * 100, 1),
                "fusion": {
                    "bge_m3_score":  bert_score,
                    "bert_v2_score": bv2_score,
                    "mlp_trained":   mlp_used,
                },
            }

            row.update({
                "score":           score_fused,
                "bert_score":      score_fused,
                "bge_m3_score":    bert_score,
                "bert_v2_score":   bv2_score,
                "bert_details":    fused_details,
                "inconsistencies": bert_details.get("inconsistencies", []),
            })
        elif engine == "compare_all":
            scores_for_report = {
                "hybrid":          round(hybrid_score, 4),
                "heuristic":       round(heuristic_score, 4),
                "bert_base":       base_score or 0.0,
                "talentmatch":     bert_score,
                "inconsistencies": bert_details.get("inconsistencies", []),
                "bert_details":    bert_details,
            }

            confidence_info: Dict[str, Any] = {}
            if base_score is not None:
                try:
                    confidence_info = bert.compute_confidence(
                        talentmatch_score=bert_score,
                        bert_base_score=base_score,
                        heuristic_score=heuristic_score,
                    )
                except Exception:
                    pass

            report: Dict[str, Any] = {}
            if report_gen is not None:
                try:
                    report = report_gen.generate_candidate_report(
                        candidate, offer, scores_for_report
                    )
                except Exception as exc:
                    report = {"error": str(exc)}

            ai_summary: Dict[str, Any] = {}
            if summarizer is not None and report:
                try:
                    ai_summary = summarizer.generate_candidate_summary(
                        {"nom": candidate.nom, "email": candidate.email},
                        {"titre": offer.titre, "description": offer.description},
                        scores_for_report,
                        report,
                    )
                except Exception as exc:
                    ai_summary = {"error": str(exc), "source": "fallback"}

            bert_gain = (
                round(bert_score - base_score, 4)
                if base_score is not None else None
            )

            row.update({
                "score":            bert_score,
                "heuristic_score":  round(heuristic_score, 4),
                "bert_score":       bert_score,
                "bert_base_score":  base_score,
                "bert_gain":        bert_gain,
                "hybrid_score":     round(hybrid_score, 4),
                "weights": {
                    "bert":        round(bert_weight, 4),
                    "heuristic":   round(heuristic_weight, 4),
                },
                "bert": {
                    "ready":           bert_details.get("ready", False),
                    "model":           bert_details.get("model"),
                    "inconsistencies": bert_details.get("inconsistencies", []),
                },
                "bert_details":       bert_details,
                "heuristic_details":  heuristic_details,
                "confidence":         confidence_info,
                "report":             report,
                "ai_summary":         ai_summary,
            })
        else:
            # mode heuristic_ml / hybrid
            row.update({
                "score":            bert_score,
                "heuristic_score":  round(heuristic_score, 4),
                "bert_score":       bert_score,
                "hybrid_score":     round(hybrid_score, 4),
                "weights": {
                    "bert":       round(bert_weight, 4),
                    "heuristic":  round(heuristic_weight, 4),
                },
                "bert": {
                    "ready":           bert_details.get("ready", False),
                    "model":           bert_details.get("model"),
                    "inconsistencies": bert_details.get("inconsistencies", []),
                },
                "heuristic_details": heuristic_details,
            })

        results.append(row)

    if engine == "heuristic":
        results.sort(key=lambda r: r.get("heuristic_score", 0.0), reverse=True)
    else:
        results.sort(key=lambda r: r.get("bert_score", r.get("score", 0.0)), reverse=True)

    return {
        "job_offer_id": str(job_offer_id),
        "total": len(results),
        "mode": "sandbox_compare",
        "engine": engine,
        "persisted": False,
        "weights": {
            "bert": round(float(alpha), 4),
            "heuristic": round(float(1.0 - alpha), 4),
        },
        "model_ready": bert.ready,
        "model_version": bert.model_version if bert.ready else None,
        "model_error": bert.load_error,
        "results": results,
    }


# ──────────────────────────────────────────────
# Chemin fichier annotations
# ──────────────────────────────────────────────
_ANNOTATIONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "annotations.json"
)


def _load_annotations() -> Dict[str, Any]:
    try:
        with open(_ANNOTATIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_annotations(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_ANNOTATIONS_PATH), exist_ok=True)
    with open(_ANNOTATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────
# POST /match-sandbox/{offer_id}/annotate
# ──────────────────────────────────────────────
@router.post("/match-sandbox/{job_offer_id}/annotate", summary="Sauvegarder les annotations (admin)")
def save_annotations(
    job_offer_id: UUID,
    payload: Dict[str, int] = Body(..., example={"candidate-uuid": 2}),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == job_offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    data = _load_annotations()
    offer_key = str(job_offer_id)

    if offer_key not in data:
        data[offer_key] = {"offer_title": offer.titre, "candidates": []}

    # Met à jour ou insère chaque annotation
    existing = {c["candidate_id"]: c for c in data[offer_key].get("candidates", [])}
    for cid, rel in payload.items():
        if rel not in (0, 1, 2):
            raise HTTPException(status_code=400, detail=f"Relevance invalide pour {cid}: doit être 0, 1 ou 2")
        cand = db.query(Candidate).filter(Candidate.id == cid).first()
        existing[cid] = {
            "candidate_id": cid,
            "name": cand.nom if cand else cid,
            "relevance": rel,
        }

    data[offer_key]["candidates"] = list(existing.values())
    _save_annotations(data)
    return {"success": True, "saved": len(payload)}


# ──────────────────────────────────────────────
# POST /match-sandbox/{offer_id}/evaluate
# ──────────────────────────────────────────────
@router.post("/match-sandbox/{job_offer_id}/evaluate", summary="Calculer les métriques d'évaluation (admin)")
def evaluate_matching(
    job_offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == job_offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    # Charger annotations
    data = _load_annotations()
    offer_annots = data.get(str(job_offer_id), {}).get("candidates", [])
    # Garder seulement les annotations valides (0, 1 ou 2) — ignorer les -1 (non notés)
    offer_annots = [a for a in offer_annots if a.get("relevance", -1) >= 0]
    if not offer_annots:
        raise HTTPException(
            status_code=400,
            detail="Aucune annotation valide pour cette offre. Notez au moins un candidat (0, 1 ou 2) puis sauvegardez."
        )

    relevance_map = {a["candidate_id"]: a["relevance"] for a in offer_annots}

    # Recalculer le ranking — on utilise le score heuristique seul pour la rapidité.
    # Le BERT est déjà évalué dans le tab Matching IA ; l'évaluation mesure le classement
    # du système, pas le score absolu.
    candidates = (
        db.query(Candidate)
        .join(Match, Match.candidate_id == Candidate.id)
        .filter(Match.job_offer_id == job_offer_id)
        .all()
    )
    seen, uniq = set(), []
    for c in candidates:
        if c.email not in seen:
            seen.add(c.email); uniq.append(c)

    heuristic_engine = _get_heuristic_engine()

    scored = []
    for c in uniq:
        h, _ = heuristic_engine.score(offer, c)
        rel = relevance_map.get(str(c.id), -1)
        scored.append({"candidate_id": str(c.id), "name": c.nom, "hybrid": float(h), "relevance": rel})

    # Trier par score (ordre du système)
    scored.sort(key=lambda x: x["hybrid"], reverse=True)

    # Garder uniquement les candidats annotés (relevance ≥ 0)
    annotated = [s for s in scored if s["relevance"] >= 0]
    if not annotated:
        raise HTTPException(
            status_code=400,
            detail="Les candidats annotés ne correspondent à aucun candidat de cette offre."
        )

    n = len(annotated)
    relevances = [s["relevance"] for s in annotated]

    # ── Precision@K
    def precision_at_k(rels: List[int], k: int) -> float:
        top = rels[:k]
        return sum(1 for r in top if r > 0) / k if top else 0.0

    # ── NDCG@K
    def dcg(rels: List[int], k: int) -> float:
        return sum(r / math.log2(i + 2) for i, r in enumerate(rels[:k]))

    def ndcg_at_k(rels: List[int], k: int) -> float:
        ideal = sorted(rels, reverse=True)
        idcg = dcg(ideal, k)
        return dcg(rels, k) / idcg if idcg > 0 else 0.0

    # ── MRR
    def mrr(rels: List[int]) -> float:
        for i, r in enumerate(rels):
            if r > 0:
                return 1.0 / (i + 1)
        return 0.0

    k_values = [k for k in [2, 3, 4, 5] if k <= n]

    metrics = {
        "precision": {f"P@{k}": round(precision_at_k(relevances, k), 3) for k in k_values},
        "ndcg":      {f"NDCG@{k}": round(ndcg_at_k(relevances, k), 3) for k in k_values},
        "mrr":       round(mrr(relevances), 3),
        "annotated_count": len(annotated),
        "relevant_count": sum(1 for r in relevances if r > 0),
        "ranking": [
            {"rank": i + 1, "name": s["name"], "hybrid": round(s["hybrid"], 4), "relevance": s["relevance"]}
            for i, s in enumerate(annotated)
        ],
    }

    return {
        "job_offer_id": str(job_offer_id),
        "offer_title": offer.titre,
        "metrics": metrics,
    }


# ──────────────────────────────────────────────
# POST /matching/summarize
# ──────────────────────────────────────────────
class SummarizePayload(BaseModel):
    candidate_id: str
    offer_id: str
    bert_score: Optional[float] = None
    bert_details: Optional[Dict[str, Any]] = None


@router.post("/summarize", summary="Générer une analyse IA d'un candidat pour une offre")
def generate_ai_summary(
    payload: SummarizePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    from uuid import UUID as _UUID
    try:
        cand_uuid  = _UUID(str(payload.candidate_id))
        offer_uuid = _UUID(str(payload.offer_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID invalide")

    candidate = db.query(Candidate).filter(Candidate.id == cand_uuid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")

    offer = db.query(JobOffer).filter(JobOffer.id == offer_uuid).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    details = payload.bert_details or {}
    score   = payload.bert_score or 0.0

    candidate_data = {
        "nom": candidate.nom or "Candidat",
        "competences": (candidate.parsed_data or {}).get("competences", []) if candidate.parsed_data else [],
    }
    offer_data = {
        "titre": offer.titre,
        "competences_requises": offer.competences_requises or [],
    }
    scores = {"hybrid": score, "bert_score": score}

    # Construire un rapport simplifié depuis les détails BERT
    comp_score = float(details.get("competences", 0))
    exp_score  = float(details.get("experience", 0))
    edu_score  = float(details.get("formation", 0))

    # Skills présents / manquants
    offer_skills = [s.lower() for s in (offer.competences_requises or [])]
    raw_cand = (candidate.parsed_data or {}).get("competences", []) if candidate.parsed_data else []
    cand_skills = [
        (s.get("name") or s.get("skill") or s.get("label") or "").lower()
        if isinstance(s, dict) else str(s).lower()
        for s in raw_cand
    ]
    strong  = [s for s in offer_skills if any(s in c or c in s for c in cand_skills)]
    missing = [s for s in offer_skills if s not in strong]

    recommendation = (
        "HAUTEMENT_RECOMMANDE" if score >= 0.75 else
        "RECOMMANDE"           if score >= 0.55 else
        "NEUTRE"               if score >= 0.35 else
        "NON_RECOMMANDE"
    )

    report = {
        "recommendation":   recommendation,
        "strong_points":    strong[:5],
        "missing_skills":   missing[:5],
        "experience_match": exp_score >= 0.5,
        "education_match":  edu_score >= 0.5,
        "confidence":       "HAUTE" if score >= 0.6 else "MOYENNE" if score >= 0.4 else "BASSE",
    }

    summarizer = _get_claude_summarizer()
    result = summarizer.generate_candidate_summary(candidate_data, offer_data, scores, report)
    return result
