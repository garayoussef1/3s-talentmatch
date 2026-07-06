"""
Routes — Test d'évaluation adaptatif (Module 1 du "Reality Gap Score").

Endpoints :
  POST /api/assessment/start          → démarre une session, renvoie la 1ʳᵉ question
  POST /api/assessment/answer         → enregistre une réponse, renvoie la suivante
  GET  /api/assessment/result/{id}    → niveau démontré (global + par compétence)

Le déroulé est adaptatif (IRT) : la difficulté des questions s'ajuste au niveau
estimé du candidat. 100% local (catsim + numpy).
"""
from __future__ import annotations

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import get_db
from app.models.candidate import Candidate
from app.models.assessment import (
    AssessmentQuestion, AssessmentSession, AssessmentStatus,
)
from app.services.assessment import cat_engine

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────
class StartPayload(BaseModel):
    candidate_id: str
    offer_id: Optional[str] = None
    domaine: str = "IT"


class AnswerPayload(BaseModel):
    session_id: str
    question_id: str
    reponse: int   # index de l'option choisie (0-based)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _pool(db: Session, domaine: str) -> List[AssessmentQuestion]:
    """Banque de questions du domaine, ordre déterministe (= index catsim)."""
    return (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.domaine == domaine)
        .order_by(AssessmentQuestion.created_at, AssessmentQuestion.id)
        .all()
    )


def _question_public(q: AssessmentQuestion) -> dict:
    """Question renvoyée au candidat — SANS la bonne réponse."""
    return {
        "question_id": str(q.id),
        "competence": q.competence_esco,
        "difficulte": q.difficulte,
        "question": q.question,
        "options": q.options,
    }


def _next_question(db: Session, session: AssessmentSession, pool: List[AssessmentQuestion]):
    """Sélectionne la prochaine question adaptée (ou None si le test est fini)."""
    administered = session.administered or []
    if cat_engine.is_finished(len(administered), len(pool)):
        return None
    bank = cat_engine.build_item_bank(pool)
    administered_idx = [it["index"] for it in administered]
    idx = cat_engine.select_next_index(bank, administered_idx, session.theta)
    if idx is None:
        return None
    return pool[idx], idx


# ── POST /assessment/start ───────────────────────────────────────────────────
@router.post("/assessment/start", summary="Démarrer un test d'évaluation adaptatif")
def start_assessment(payload: StartPayload, db: Session = Depends(get_db)):
    try:
        cand_uuid = UUID(str(payload.candidate_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="candidate_id invalide")

    candidate = db.query(Candidate).filter(Candidate.id == cand_uuid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")

    pool = _pool(db, payload.domaine)
    if len(pool) < 3:
        raise HTTPException(status_code=400, detail=f"Banque insuffisante pour le domaine « {payload.domaine} »")

    offer_uuid = None
    if payload.offer_id:
        try:
            offer_uuid = UUID(str(payload.offer_id))
        except (ValueError, AttributeError):
            offer_uuid = None

    session = AssessmentSession(
        candidate_id=cand_uuid,
        job_offer_id=offer_uuid,
        domaine=payload.domaine,
        status=AssessmentStatus.in_progress,
        theta=0.0,
        administered=[],
        competence_scores={},
    )
    db.add(session)
    db.flush()

    # Première question (max information à theta = 0)
    nxt = _next_question(db, session, pool)
    if not nxt:
        raise HTTPException(status_code=400, detail="Aucune question disponible")
    question, _idx = nxt
    db.commit()

    return {
        "session_id": str(session.id),
        "domaine": session.domaine,
        "total_prevu": min(cat_engine.TEST_LENGTH, len(pool)),
        "question": _question_public(question),
        "progression": 0,
    }


# ── POST /assessment/answer ──────────────────────────────────────────────────
@router.post("/assessment/answer", summary="Répondre à une question (adaptatif)")
def answer_assessment(payload: AnswerPayload, db: Session = Depends(get_db)):
    try:
        sess_uuid = UUID(str(payload.session_id))
        q_uuid = UUID(str(payload.question_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Identifiant invalide")

    session = db.query(AssessmentSession).filter(AssessmentSession.id == sess_uuid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    if session.status == AssessmentStatus.completed:
        raise HTTPException(status_code=409, detail="Test déjà terminé")

    pool = _pool(db, session.domaine)
    id_to_index = {str(q.id): i for i, q in enumerate(pool)}
    if str(q_uuid) not in id_to_index:
        raise HTTPException(status_code=404, detail="Question hors banque")
    question = pool[id_to_index[str(q_uuid)]]

    # Éviter le double comptage d'une même question
    administered = list(session.administered or [])
    if any(it["question_id"] == str(q_uuid) for it in administered):
        raise HTTPException(status_code=409, detail="Question déjà répondue")

    correct = int(payload.reponse) == int(question.bonne_reponse)
    administered.append({
        "question_id": str(q_uuid),
        "index": id_to_index[str(q_uuid)],
        "competence": question.competence_esco,
        "difficulte": question.difficulte,
        "reponse": int(payload.reponse),
        "correct": correct,
    })

    # Ré-estimation de theta (IRT)
    bank = cat_engine.build_item_bank(pool)
    idxs = [it["index"] for it in administered]
    resps = [it["correct"] for it in administered]
    session.theta = cat_engine.estimate_theta(bank, idxs, resps, session.theta)
    session.administered = administered
    session.competence_scores = cat_engine.competence_scores(administered)

    # Fin du test ?
    if cat_engine.is_finished(len(administered), len(pool)):
        session.status = AssessmentStatus.completed
        session.completed_at = func.now()
        db.commit()
        return {
            "done": True,
            "progression": len(administered),
            "niveau_global": cat_engine.theta_to_niveau(session.theta),
            "competence_scores": session.competence_scores,
        }

    # Sinon : question suivante
    nxt = _next_question(db, session, pool)
    db.commit()
    if not nxt:
        return {"done": True, "progression": len(administered),
                "niveau_global": cat_engine.theta_to_niveau(session.theta),
                "competence_scores": session.competence_scores}
    next_q, _ = nxt
    return {
        "done": False,
        "progression": len(administered),
        "question": _question_public(next_q),
    }


# ── GET /assessment/result/{id} ──────────────────────────────────────────────
@router.get("/assessment/result/{session_id}", summary="Résultat du test (niveau démontré)")
def assessment_result(session_id: UUID, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    return {
        "session_id": str(session.id),
        "candidate_id": str(session.candidate_id),
        "domaine": session.domaine,
        "status": session.status.value,
        "theta": round(session.theta, 3) if session.theta is not None else None,
        "niveau_global": cat_engine.theta_to_niveau(session.theta),
        "competence_scores": session.competence_scores or {},
        "nb_questions": len(session.administered or []),
    }
