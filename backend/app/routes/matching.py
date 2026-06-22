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
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.services.ai_summary.claude_summarizer import ClaudeSummarizer
from app.services.access_logger import log_access, MATCH_LAUNCHED

router = APIRouter()

# Singletons — chargés une seule fois au démarrage du serveur
_bert_scorer: Optional[Any] = None
_claude_summarizer: Optional[ClaudeSummarizer] = None


def _get_bert_scorer():
    """Moteur de matching TalentMatch (BGE-M3 + cross-encoder + MLP v3b1)."""
    global _bert_scorer
    if _bert_scorer is None:
        _bert_scorer = BERTMatchingScorer()
    return _bert_scorer


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
    summary="Matcher les candidats d'une offre (moteur TalentMatch BGE-M3 + MLP)",
)
def match_candidates_for_offer_sandbox(
    job_offer_id: UUID,
    engine: str = "bert",   # conservé pour compatibilité frontend (seul 'bert' supporté)
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == job_offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    # Matcher uniquement les candidats ayant un Match pour cette offre.
    candidates: List[Candidate] = (
        db.query(Candidate)
        .join(Match, Match.candidate_id == Candidate.id)
        .filter(Match.job_offer_id == job_offer_id)
        .order_by(Candidate.created_at.desc())
        .all()
    )

    bert = _get_bert_scorer()
    results: List[Dict[str, Any]] = []
    for candidate in candidates:
        b_score, b_details = bert.score(offer, candidate)
        results.append({
            "candidate_id":    str(candidate.id),
            "cv_id":           candidate.cv_id,
            "candidate_name":  candidate.nom,
            "candidate_email": candidate.email,
            "score":           round(float(b_score), 4),
            "bert_score":      round(float(b_score), 4),
            "bert_details":    b_details,
            "inconsistencies": b_details.get("inconsistencies", []),
        })

    results.sort(key=lambda r: r.get("score", 0.0), reverse=True)

    return {
        "job_offer_id":  str(job_offer_id),
        "total":         len(results),
        "engine":        "bert",
        "persisted":     False,
        "model_ready":   bert.ready,
        "model_version": bert.model_version if bert.ready else None,
        "model_error":   bert.load_error,
        "results":       results,
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
