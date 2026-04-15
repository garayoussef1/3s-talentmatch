from __future__ import annotations

import json
from uuid import UUID
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_recruteur_or_admin
from app.models.job_offer import JobOffer
from app.models.match import Match
from app.models.user import User
from app.schemas.matching import MatchCandidatesResponse, MatchCandidateItem
from app.services.matching.match_engine import MatchEngine
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.services.matching_sandbox.ml_scorer import SandboxMLScorer

router = APIRouter()


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

    # On ne retourne que les candidats qui ont postulé (Match existant)
    matches: List[Match] = (
        db.query(Match)
        .filter(Match.job_offer_id == job_offer_id)
        .all()
    )

    engine = MatchEngine()
    results: List[MatchCandidateItem] = []

    for m in matches:
        if not m.candidate:
            continue

        score, details = engine.score(offer, m.candidate)
        m.score = float(score)
        m.details = engine.details_to_text(details)

        results.append(
            MatchCandidateItem(
                candidate_id=str(m.candidate_id),
                cv_id=m.candidate.cv_id,
                candidate_name=m.candidate.nom,
                candidate_email=m.candidate.email,
                score=float(score),
                details=details,
            )
        )

    # Persist scores
    db.commit()

    # Sort desc
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

    if current_user.role.value != "admin" and offer.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")

    alpha = max(0.0, min(1.0, float(alpha)))
    engine = (engine or "heuristic_ml").strip().lower()
    if engine not in {"heuristic_ml", "bert", "compare_all"}:
        raise HTTPException(
            status_code=400,
            detail="engine must be one of: heuristic_ml, bert, compare_all",
        )

    matches: List[Match] = (
        db.query(Match)
        .filter(Match.job_offer_id == job_offer_id)
        .all()
    )

    heuristic_engine = MatchEngine()
    ml = SandboxMLScorer()
    bert = BERTMatchingScorer()

    results: List[Dict[str, Any]] = []
    for m in matches:
        if not m.candidate:
            continue

        if engine == "bert":
            bert_score, bert_details = bert.score(offer, m.candidate)
            results.append(
                {
                    "candidate_id": str(m.candidate_id),
                    "cv_id": m.candidate.cv_id,
                    "candidate_name": m.candidate.nom,
                    "candidate_email": m.candidate.email,
                    "bert_score": round(float(bert_score), 4),
                    "details": bert_details,
                    "inconsistencies": bert_details.get("inconsistencies", []),
                }
            )
            continue

        heuristic_score, heuristic_details = heuristic_engine.score(offer, m.candidate)
        feature_dict = SandboxMLScorer.build_feature_dict(
            details=heuristic_details,
            candidate=m.candidate,
            offer=offer,
        )
        ml_score, ml_info = ml.predict(feature_dict)

        if engine == "compare_all":
            bert_score, bert_details = bert.score(offer, m.candidate)
            hybrid_score = (0.4 * float(bert_score)) + (0.3 * float(ml_score)) + (0.3 * float(heuristic_score))
            hybrid_score = max(0.0, min(1.0, float(hybrid_score)))
            results.append(
                {
                    "candidate_id": str(m.candidate_id),
                    "cv_id": m.candidate.cv_id,
                    "candidate_name": m.candidate.nom,
                    "candidate_email": m.candidate.email,
                    "heuristic_score": round(float(heuristic_score), 4),
                    "ml_score": round(float(ml_score), 4),
                    "bert_score": round(float(bert_score), 4),
                    "hybrid_score": round(float(hybrid_score), 4),
                    "ml": ml_info,
                    "bert": {
                        "ready": bert_details.get("ready", False),
                        "model": bert_details.get("model"),
                        "inconsistencies": bert_details.get("inconsistencies", []),
                    },
                    "features": feature_dict,
                    "heuristic_details": heuristic_details,
                }
            )
        else:
            # mode par défaut: comportement actuel (heuristic + ml + hybrid alpha)
            hybrid_score = (alpha * ml_score) + ((1.0 - alpha) * heuristic_score)
            hybrid_score = max(0.0, min(1.0, float(hybrid_score)))
            results.append(
                {
                    "candidate_id": str(m.candidate_id),
                    "cv_id": m.candidate.cv_id,
                    "candidate_name": m.candidate.nom,
                    "candidate_email": m.candidate.email,
                    "heuristic_score": round(float(heuristic_score), 4),
                    "ml_score": round(float(ml_score), 4),
                    "hybrid_score": round(float(hybrid_score), 4),
                    "alpha": alpha,
                    "ml": ml_info,
                    "features": feature_dict,
                    "heuristic_details": heuristic_details,
                }
            )

    if engine == "bert":
        results.sort(key=lambda r: r["bert_score"], reverse=True)
        return {
            "job_offer_id": str(job_offer_id),
            "total": len(results),
            "mode": "sandbox_bert",
            "engine": engine,
            "persisted": False,
            "model_ready": bert.ready,
            "model_error": bert.load_error,
            "results": results,
        }

    results.sort(key=lambda r: r["hybrid_score"], reverse=True)

    return {
        "job_offer_id": str(job_offer_id),
        "total": len(results),
        "mode": "sandbox_compare",
        "engine": engine,
        "persisted": False,
        "alpha": alpha,
        "model_ready": ml.ready,
        "model_error": ml.load_error,
        "results": results,
    }
