"""
Routes — Entretien IA conversationnel.

Flux :
  POST /interviews/start          → génère les questions + crée l'entretien en DB
  GET  /interviews/{id}           → récupère l'entretien (questions, réponses, rapport)
  POST /interviews/{id}/answer    → soumet une réponse + l'analyse (scoring)
  POST /interviews/{id}/report    → génère le rapport final + recommandation
"""
from __future__ import annotations

import os
import json
import secrets
from uuid import UUID
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import get_db
from app.dependencies import get_current_recruteur_or_admin
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.models.user import User
from app.models.notification import Notification
from app.models.interview import (
    Interview, InterviewQuestion, InterviewAnswer, InterviewReport,
    InterviewStatus, InterviewPhase, Recommendation,
)
from app.services.interview.groq_interview_service import (
    CVSummary, OfferSummary, GroqInterviewService,
)
from app.services import email_service

router = APIRouter()

# URL du frontend (pour construire le lien complet candidat dans l'email)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _notify_candidate(db: Session, candidate: Candidate, offer: JobOffer,
                      full_link: str) -> Dict[str, bool]:
    """Envoie l'email + crée la notification in-app. Best-effort (n'échoue jamais)."""
    prenom = (candidate.nom or "Candidat").split()[0]
    email_sent = False
    notif_created = False

    # Email (si le candidat a une adresse)
    if candidate.email:
        try:
            email_sent = email_service.send_interview_invitation_email(
                candidate.email, prenom, offer.titre or "le poste", full_link
            )
        except Exception:
            email_sent = False

    # Notification in-app (si le candidat a un compte utilisateur lié)
    if candidate.user_id:
        try:
            db.add(Notification(
                user_id=candidate.user_id,
                type="interview_invite",
                title="Invitation à un entretien",
                message=f"Vous êtes invité(e) à passer un entretien pour « {offer.titre} ».",
                link=f"/entretien/{full_link.rsplit('/', 1)[-1]}",
            ))
            notif_created = True
        except Exception:
            notif_created = False

    return {"email_sent": email_sent, "notification_created": notif_created}

# Singleton — chargé une fois
_service: Optional[GroqInterviewService] = None


def _get_service() -> GroqInterviewService:
    global _service
    if _service is None:
        _service = GroqInterviewService()
    return _service


# ─────────────────────────────────────────────────────────────────────────────
# Mapping phases / recommandation (texte service → enum DB)
# ─────────────────────────────────────────────────────────────────────────────
_PHASE_MAP = {
    "validation_profil": InterviewPhase.profile,
    "technique":         InterviewPhase.technical,
    "mise_en_situation": InterviewPhase.situational,
    "soft_skill":        InterviewPhase.soft_skills,
    "motivation":        InterviewPhase.motivation,
    "cloture":           InterviewPhase.closing,
}
_RECO_MAP = {
    "RECRUTER": Recommendation.recruit,
    "HESITER":  Recommendation.hesitate,
    "REJETER":  Recommendation.reject,
}

# Pondération des 5 dimensions (identique au moteur)
_WEIGHTS = {"technique": 0.40, "star": 0.20, "coherence": 0.15,
            "specificite": 0.15, "communication": 0.10}


def _weighted_score(scores: Dict[str, float]) -> float:
    """Score pondéré d'une réponse, ramené sur [0,1]."""
    total = sum(_WEIGHTS[k] * float(scores.get(k, 0)) for k in _WEIGHTS)
    return round(total / 10.0, 4)


# ─────────────────────────────────────────────────────────────────────────────
# Constructeurs CVSummary / OfferSummary depuis les modèles ORM
# ─────────────────────────────────────────────────────────────────────────────
def _build_cv(candidate: Candidate) -> CVSummary:
    return CVSummary.from_parsed_data(
        nom=candidate.nom or "Candidat",
        email=candidate.email or "",
        parsed_data=candidate.parsed_data or {},
    )


def _build_offer(offer: JobOffer) -> OfferSummary:
    return OfferSummary(
        titre=offer.titre or "Poste",
        domaine_metier=getattr(offer, "domaine_metier", None) or "IT / Développement",
        type_contrat=offer.type_contrat or "CDI",
        competences_requises=offer.competences_requises or [],
        competences_appreciees=getattr(offer, "competences_appreciees", None) or [],
        description=offer.description or "",
        niveau_seniorite=getattr(offer, "niveau_seniorite", None) or "",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Schémas de requête
# ─────────────────────────────────────────────────────────────────────────────
class StartPayload(BaseModel):
    candidate_id: str
    offer_id: str
    langue: str = "fr"


class AnswerPayload(BaseModel):
    question_id: str
    answer_text: str


# ─────────────────────────────────────────────────────────────────────────────
# POST /interviews/start
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/interviews/start", summary="Démarrer un entretien IA pour un candidat")
def start_interview(
    payload: StartPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    try:
        cand_uuid  = UUID(str(payload.candidate_id))
        offer_uuid = UUID(str(payload.offer_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID invalide")

    candidate = db.query(Candidate).filter(Candidate.id == cand_uuid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")
    offer = db.query(JobOffer).filter(JobOffer.id == offer_uuid).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    cv    = _build_cv(candidate)
    offer_summary = _build_offer(offer)
    service = _get_service()

    try:
        questions = service.generate_questions(cv, offer_summary)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur génération questions : {exc}")

    if not questions:
        raise HTTPException(status_code=502, detail="Aucune question générée")

    # Création de l'entretien (avec jeton d'accès candidat)
    interview = Interview(
        candidate_id=cand_uuid,
        job_offer_id=offer_uuid,
        status=InterviewStatus.created,
        domaine=offer_summary.domaine_metier,
        langue=payload.langue,
        llm_model=service.model,
        access_token=secrets.token_urlsafe(24),
        started_at=func.now(),
    )
    db.add(interview)
    db.flush()  # pour avoir interview.id

    # Création des questions
    out_questions = []
    for q in questions:
        phase_enum = _PHASE_MAP.get(q.get("phase", ""), InterviewPhase.technical)
        iq = InterviewQuestion(
            interview_id=interview.id,
            order_index=int(q.get("index", 0)),
            phase=phase_enum,
            question_text=q.get("question", ""),
            target_competence=(q.get("skill_targeted") or "")[:150] or None,
            intent=(q.get("context_hint") or "")[:255] or None,
            meta=json.dumps(q, ensure_ascii=False),
        )
        db.add(iq)
        db.flush()
        out_questions.append({
            "id": str(iq.id),
            "order_index": iq.order_index,
            "phase": phase_enum.value,
            "question": iq.question_text,
            "context_hint": q.get("context_hint", ""),
            "cv_reference": q.get("cv_reference", ""),
        })

    db.commit()

    # Envoi automatique : email au candidat + notification in-app (best-effort)
    full_link = f"{FRONTEND_URL}/entretien/{interview.access_token}"
    notif = _notify_candidate(db, candidate, offer, full_link)
    db.commit()

    return {
        "interview_id": str(interview.id),
        "status": interview.status.value,
        "domaine": interview.domaine,
        "provider": service.provider,
        "model": service.model,
        "candidate_name": candidate.nom,
        "candidate_email": candidate.email,
        "offer_titre": offer.titre,
        "total_questions": len(out_questions),
        "questions": out_questions,
        # Lien à transmettre au candidat (entretien autonome)
        "access_token": interview.access_token,
        "candidate_link": f"/entretien/{interview.access_token}",
        "full_link": full_link,
        "email_sent": notif["email_sent"],
        "notification_created": notif["notification_created"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /interviews/{id}
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/interviews/{interview_id}", summary="Récupérer un entretien")
def get_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Entretien non trouvé")

    answers_by_q = {a.question_id: a for a in interview.answers}
    questions = []
    for q in interview.questions:
        a = answers_by_q.get(q.id)
        questions.append({
            "id": str(q.id),
            "order_index": q.order_index,
            "phase": q.phase.value,
            "question": q.question_text,
            "context_hint": q.intent,
            "answered": a is not None,
            "answer_text": a.answer_text if a else None,
            "score": a.score if a else None,
        })

    report = None
    if interview.report:
        report = json.loads(interview.report.full_payload) if interview.report.full_payload else {
            "score_global_100": interview.report.global_score,
            "recommandation": interview.report.recommendation.value,
            "synthese_executive": interview.report.summary,
        }

    return {
        "interview_id": str(interview.id),
        "status": interview.status.value,
        "domaine": interview.domaine,
        "candidate_id": str(interview.candidate_id),
        "global_score": interview.global_score,
        "recommendation": interview.recommendation.value if interview.recommendation else None,
        "questions": questions,
        "report": report,
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /interviews/{id}/answer
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/interviews/{interview_id}/answer", summary="Soumettre + analyser une réponse")
def submit_answer(
    interview_id: UUID,
    payload: AnswerPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Entretien non trouvé")

    try:
        q_uuid = UUID(str(payload.question_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="question_id invalide")

    question = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == q_uuid,
        InterviewQuestion.interview_id == interview_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question non trouvée")

    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    cv = _build_cv(candidate) if candidate else CVSummary(nom="Candidat")

    # Reconstruire le dict question attendu par score_answer (depuis meta)
    q_dict = json.loads(question.meta) if question.meta else {
        "question": question.question_text,
        "skill_targeted": question.target_competence,
    }

    service = _get_service()
    try:
        analysis = service.score_answer(q_dict, payload.answer_text, cv, interview.domaine or "")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur analyse réponse : {exc}")

    scores = analysis.get("scores", {})
    weighted = _weighted_score(scores)

    # Upsert de la réponse
    answer = db.query(InterviewAnswer).filter(
        InterviewAnswer.question_id == q_uuid
    ).first()
    if answer is None:
        answer = InterviewAnswer(interview_id=interview_id, question_id=q_uuid)
        db.add(answer)

    answer.answer_text = payload.answer_text
    answer.analysis = json.dumps(analysis, ensure_ascii=False)
    answer.score = weighted
    answer.flags = json.dumps(analysis.get("flags", {}), ensure_ascii=False)

    if interview.status == InterviewStatus.created:
        interview.status = InterviewStatus.in_progress

    db.commit()

    return {
        "question_id": str(q_uuid),
        "score": weighted,
        "scores": scores,
        "flags": analysis.get("flags", {}),
        "cv_contradiction": analysis.get("cv_contradiction", False),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /interviews/{id}/report
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/interviews/{interview_id}/report", summary="Générer le rapport final")
def generate_report(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Entretien non trouvé")

    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    offer = db.query(JobOffer).filter(JobOffer.id == interview.job_offer_id).first()
    if not candidate or not offer:
        raise HTTPException(status_code=404, detail="Candidat ou offre introuvable")

    cv = _build_cv(candidate)
    offer_summary = _build_offer(offer)

    # Construire qa_pairs + scores agrégés depuis les réponses
    answers_by_q = {a.question_id: a for a in interview.answers}
    qa_pairs: List[Dict[str, Any]] = []
    dim_totals = {k: [] for k in _WEIGHTS}

    for q in interview.questions:
        a = answers_by_q.get(q.id)
        if a is None or not a.answer_text:
            continue
        analysis = json.loads(a.analysis) if a.analysis else {}
        scores = analysis.get("scores", {})
        for k in _WEIGHTS:
            if k in scores:
                dim_totals[k].append(float(scores[k]))
        qa_pairs.append({
            "phase": q.phase.value,
            "question": q.question_text,
            "answer": a.answer_text,
            "scores": scores,
            "flags": json.loads(a.flags) if a.flags else {},
        })

    if not qa_pairs:
        raise HTTPException(status_code=400, detail="Aucune réponse à analyser")

    aggregated = {
        k: round(sum(v) / len(v), 2) if v else 0.0
        for k, v in dim_totals.items()
    }

    service = _get_service()
    try:
        rapport = service.generate_report(cv, offer_summary, qa_pairs, aggregated)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur génération rapport : {exc}")

    reco_enum = _RECO_MAP.get(rapport.get("recommandation", ""), Recommendation.hesitate)
    score_100 = float(rapport.get("score_global_100", 0))

    # Persistance du rapport
    existing = db.query(InterviewReport).filter(
        InterviewReport.interview_id == interview_id
    ).first()
    if existing:
        db.delete(existing)
        db.flush()

    report = InterviewReport(
        interview_id=interview_id,
        global_score=score_100,
        recommendation=reco_enum,
        summary=rapport.get("synthese_executive", ""),
        validated_competences=json.dumps(rapport.get("competences", {}), ensure_ascii=False),
        soft_skills=json.dumps(rapport.get("soft_skills_detectes", []), ensure_ascii=False),
        cross_check=json.dumps(rapport.get("cross_check", {}), ensure_ascii=False),
        next_steps=json.dumps(rapport.get("prochaines_etapes", []), ensure_ascii=False),
        full_payload=json.dumps(rapport, ensure_ascii=False),
    )
    db.add(report)

    interview.status = InterviewStatus.completed
    interview.global_score = score_100
    interview.recommendation = reco_enum
    interview.completed_at = func.now()

    db.commit()

    return rapport


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINTS PUBLICS — accès candidat par jeton (sans compte recruteur)
# ═════════════════════════════════════════════════════════════════════════════
class PublicAnswerPayload(BaseModel):
    question_id: str
    answer_text: str


def _interview_by_token(db: Session, token: str) -> Interview:
    interview = db.query(Interview).filter(Interview.access_token == token).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Lien d'entretien invalide ou expiré")
    return interview


# GET /interviews/public/{token} — le candidat récupère ses questions (sans scores)
@router.get("/interviews/public/{token}", summary="[Candidat] Récupérer l'entretien par lien")
def public_get_interview(token: str, db: Session = Depends(get_db)):
    interview = _interview_by_token(db, token)
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    offer = db.query(JobOffer).filter(JobOffer.id == interview.job_offer_id).first()

    answered_ids = {a.question_id for a in interview.answers if a.answer_text}
    questions = [{
        "id": str(q.id),
        "order_index": q.order_index,
        "phase": q.phase.value,
        "question": q.question_text,
        "context_hint": q.intent,
        "answered": q.id in answered_ids,
    } for q in interview.questions]

    return {
        "candidate_name": candidate.nom if candidate else "Candidat",
        "offer_titre": offer.titre if offer else "Poste",
        "domaine": interview.domaine,
        "status": interview.status.value,
        "total_questions": len(questions),
        "answered_count": len(answered_ids),
        "completed": interview.status == InterviewStatus.completed,
        "questions": questions,
    }


# POST /interviews/public/{token}/answer — le candidat répond (score interne, NON renvoyé)
@router.post("/interviews/public/{token}/answer", summary="[Candidat] Soumettre une réponse")
def public_submit_answer(token: str, payload: PublicAnswerPayload, db: Session = Depends(get_db)):
    interview = _interview_by_token(db, token)
    if interview.status == InterviewStatus.completed:
        raise HTTPException(status_code=409, detail="Entretien déjà terminé")

    try:
        q_uuid = UUID(str(payload.question_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="question_id invalide")

    question = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == q_uuid,
        InterviewQuestion.interview_id == interview.id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question non trouvée")

    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    cv = _build_cv(candidate) if candidate else CVSummary(nom="Candidat")
    q_dict = json.loads(question.meta) if question.meta else {"question": question.question_text}

    service = _get_service()
    try:
        analysis = service.score_answer(q_dict, payload.answer_text, cv, interview.domaine or "")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur analyse : {exc}")

    weighted = _weighted_score(analysis.get("scores", {}))

    answer = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == q_uuid).first()
    if answer is None:
        answer = InterviewAnswer(interview_id=interview.id, question_id=q_uuid)
        db.add(answer)
    answer.answer_text = payload.answer_text
    answer.analysis = json.dumps(analysis, ensure_ascii=False)
    answer.score = weighted
    answer.flags = json.dumps(analysis.get("flags", {}), ensure_ascii=False)

    if interview.status == InterviewStatus.created:
        interview.status = InterviewStatus.in_progress
    db.commit()

    # On NE renvoie PAS le score au candidat (il ne doit pas ajuster ses réponses)
    answered = db.query(InterviewAnswer).filter(
        InterviewAnswer.interview_id == interview.id,
        InterviewAnswer.answer_text.isnot(None),
    ).count()
    total = len(interview.questions)
    return {"ok": True, "answered_count": answered, "total_questions": total,
            "done": answered >= total}
