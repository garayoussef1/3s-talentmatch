from __future__ import annotations

import json
import math
import os
from uuid import UUID
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_recruteur_or_admin
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.models.match import Match
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
_report_generator: Optional[ReportGenerator] = None
_claude_summarizer: Optional[ClaudeSummarizer] = None


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
        # Forcer l'usage du modèle de base même si TalentMatch-BERT est présent
        _bert_base_scorer.model_name    = "paraphrase-multilingual-MiniLM-L12-v2"
        _bert_base_scorer.model_version = "Base (paraphrase-multilingual)"
    return _bert_base_scorer


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
    if engine not in {"heuristic_ml", "bert", "compare_all", "heuristic", "hybrid"}:
        raise HTTPException(
            status_code=400,
            detail="engine must be one of: heuristic_ml, bert, compare_all, heuristic, hybrid",
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
    bert = _get_bert_scorer()
    bert_base = _get_bert_base_scorer() if engine == "compare_all" else None
    report_gen = _get_report_generator() if engine == "compare_all" else None
    summarizer = _get_claude_summarizer() if engine == "compare_all" else None

    bert_weight       = max(0.0, min(1.0, float(alpha)))
    heuristic_weight  = 1.0 - bert_weight

    # ── Calcul des scores pour tous les candidats ─────────────────────────
    raw_data: List[Dict[str, Any]] = []
    for candidate in candidates:
        h_score, h_details = heuristic_engine.score(offer, candidate)
        b_score, b_details = bert.score(offer, candidate)
        base_raw = float(bert_base.score(offer, candidate)[0]) if bert_base else None

        raw_data.append({
            "candidate":         candidate,
            "heuristic_score":   float(h_score),
            "heuristic_details": h_details,
            "bert_score":        float(b_score),
            "bert_details":      b_details,
            "base_score_raw":    base_raw,
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
        elif engine == "bert":
            row.update({
                "score":           bert_score,
                "bert_score":      bert_score,
                "bert_details":    bert_details,
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
