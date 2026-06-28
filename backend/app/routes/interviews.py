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
from app.models.user import User, UserRole
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


def _parse_dt(value: Optional[str]):
    """Parse une date ISO 8601 (tolérant au suffixe Z). Retourne datetime ou None."""
    if not value:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _notify_candidate(db: Session, candidate: Candidate, offer: JobOffer,
                      full_link: str, opens_at=None, deadline=None,
                      access_pin=None) -> Dict[str, bool]:
    """Envoie l'email + crée la notification in-app. Best-effort (n'échoue jamais)."""
    prenom = (candidate.nom or "Candidat").split()[0]
    email_sent = False
    notif_created = False

    # Email (si le candidat a une adresse)
    if candidate.email:
        try:
            email_sent = email_service.send_interview_invitation_email(
                candidate.email, prenom, offer.titre or "le poste", full_link,
                opens_at=opens_at, deadline=deadline, access_pin=access_pin,
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
    opens_at: Optional[str] = None   # ISO 8601 (date/heure d'ouverture)
    deadline: Optional[str] = None   # ISO 8601 (date/heure limite)


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

    # ── Anti-doublons : réutiliser un entretien NON terminé déjà créé pour ce
    # couple candidat+offre (évite d'en recréer un à chaque clic + ré-email). ──
    existing = (
        db.query(Interview)
        .filter(
            Interview.candidate_id == cand_uuid,
            Interview.job_offer_id == offer_uuid,
            Interview.status.in_([InterviewStatus.created, InterviewStatus.in_progress]),
        )
        .order_by(Interview.created_at.desc())
        .first()
    )
    if existing and existing.questions:
        reused_q = [{
            "id": str(q.id),
            "order_index": q.order_index,
            "phase": q.phase.value,
            "question": q.question_text,
            "context_hint": q.intent or "",
            "cv_reference": "",
        } for q in sorted(existing.questions, key=lambda x: x.order_index)]
        return {
            "interview_id": str(existing.id),
            "status": existing.status.value,
            "reused": True,
            "domaine": existing.domaine,
            "candidate_name": candidate.nom,
            "candidate_email": candidate.email,
            "offer_titre": offer.titre,
            "total_questions": len(reused_q),
            "questions": reused_q,
            "access_token": existing.access_token,
            "access_pin": existing.access_pin,
            "candidate_link": f"/entretien/{existing.access_token}",
            "full_link": f"{FRONTEND_URL}/entretien/{existing.access_token}",
            "email_sent": False,           # déjà envoyé au 1er lancement
            "notification_created": False,
        }

    cv    = _build_cv(candidate)
    offer_summary = _build_offer(offer)
    service = _get_service()

    try:
        questions = service.generate_questions(cv, offer_summary)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur génération questions : {exc}")

    if not questions:
        raise HTTPException(status_code=502, detail="Aucune question générée")

    # Création de l'entretien (jeton d'accès + PIN candidat à 6 chiffres)
    opens_at = _parse_dt(payload.opens_at)
    deadline = _parse_dt(payload.deadline)
    access_pin = f"{secrets.randbelow(900000) + 100000}"  # 6 chiffres
    interview = Interview(
        candidate_id=cand_uuid,
        job_offer_id=offer_uuid,
        status=InterviewStatus.created,
        domaine=offer_summary.domaine_metier,
        langue=payload.langue,
        llm_model=service.model,
        access_token=secrets.token_urlsafe(24),
        access_pin=access_pin,
        opens_at=opens_at,
        deadline=deadline,
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
    notif = _notify_candidate(db, candidate, offer, full_link, opens_at, deadline, access_pin)
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
        "access_pin": interview.access_pin,
        "candidate_link": f"/entretien/{interview.access_token}",
        "full_link": full_link,
        "email_sent": notif["email_sent"],
        "notification_created": notif["notification_created"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Contrôle d'accès offre : admin = tout ; recruteur = créateur ou assigné
# ─────────────────────────────────────────────────────────────────────────────
def _compute_integrity(interview: Interview) -> Dict[str, Any]:
    """Calcule un score d'intégrité (0-100) à partir des signaux anti-triche."""
    integ = json.loads(interview.integrity) if interview.integrity else {}
    answers = [a for a in interview.answers if a.answer_text]
    n_paste = sum(1 for a in answers if a.paste_detected)
    n_fast = sum(
        1 for a in answers
        if a.response_time and a.response_time < 10 and len(a.answer_text or "") > 200
    )
    tab = int(integ.get("tab_switches", 0))
    fs = int(integ.get("fullscreen_exits", 0))

    score = 100
    score -= min(40, tab * 8)
    score -= min(20, fs * 5)
    score -= min(30, n_paste * 15)
    score -= min(20, n_fast * 10)
    score = max(0, score)

    flags = []
    if tab:
        flags.append(f"A quitté l'onglet {tab} fois")
    if fs:
        flags.append(f"Sorti du plein écran {fs} fois")
    if n_paste:
        flags.append(f"{n_paste} réponse(s) collée(s)")
    if n_fast:
        flags.append(f"{n_fast} réponse(s) anormalement rapide(s)")

    blocked = bool(integ.get("blocked"))
    if blocked:
        score = 0
        flags.insert(0, integ.get("block_reason", "Entretien bloqué pour triche présumée."))

    level = "blocked" if blocked else ("high" if score >= 80 else ("medium" if score >= 50 else "low"))
    return {
        "score": score, "level": level, "blocked": blocked,
        "tab_switches": tab, "fullscreen_exits": fs,
        "paste_count": n_paste, "fast_answers": n_fast,
        "flags": flags,
    }


def _can_access_offer(offer: JobOffer, user: User) -> bool:
    if user.role == UserRole.admin:
        return True
    if offer.recruiter_id == user.id:
        return True
    return any(r.id == user.id for r in (offer.assigned_recruiters or []))


# ─────────────────────────────────────────────────────────────────────────────
# GET /interviews?offer_id=  — liste des entretiens d'une offre (recruteur/admin)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/interviews", summary="Lister les entretiens d'une offre")
def list_interviews(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if not _can_access_offer(offer, current_user):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette offre")

    interviews = (
        db.query(Interview)
        .filter(Interview.job_offer_id == offer_id)
        .order_by(Interview.created_at.desc())
        .all()
    )

    out = []
    for itw in interviews:
        candidate = db.query(Candidate).filter(Candidate.id == itw.candidate_id).first()
        total = len(itw.questions)
        answered = sum(1 for a in itw.answers if a.answer_text)
        out.append({
            "interview_id": str(itw.id),
            "candidate_id": str(itw.candidate_id),
            "candidate_name": candidate.nom if candidate else "—",
            "candidate_email": candidate.email if candidate else None,
            "cv_id": candidate.cv_id if candidate else None,
            "status": itw.status.value,
            "total_questions": total,
            "answered_count": answered,
            "global_score": itw.global_score,
            "recommendation": itw.recommendation.value if itw.recommendation else None,
            "has_report": itw.report is not None,
            "integrity_score": _compute_integrity(itw)["score"] if answered else None,
            "created_at": itw.created_at.isoformat() if itw.created_at else None,
        })

    return {"offer_id": str(offer_id), "offer_titre": offer.titre, "interviews": out}


# ─────────────────────────────────────────────────────────────────────────────
# GET /interviews/compare?offer_id=  — données de comparaison (radar 5 dimensions)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/interviews/compare", summary="Comparer les candidats interviewés")
def compare_interviews(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if not _can_access_offer(offer, current_user):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette offre")

    interviews = (
        db.query(Interview)
        .filter(Interview.job_offer_id == offer_id)
        .order_by(Interview.global_score.desc().nullslast())
        .all()
    )

    candidates = []
    for itw in interviews:
        # Agrège les 5 dimensions depuis les réponses analysées
        dim_totals = {k: [] for k in _WEIGHTS}
        for a in itw.answers:
            if not a.answer_text or not a.analysis:
                continue
            scores = (json.loads(a.analysis) or {}).get("scores", {})
            for k in _WEIGHTS:
                if k in scores:
                    dim_totals[k].append(float(scores[k]))
        if not any(dim_totals.values()):
            continue  # pas de données analysées → on ignore pour la comparaison

        dimensions = {k: round(sum(v) / len(v), 1) if v else 0.0 for k, v in dim_totals.items()}
        candidate = db.query(Candidate).filter(Candidate.id == itw.candidate_id).first()

        report = itw.report
        payload = json.loads(report.full_payload) if (report and report.full_payload) else {}
        candidates.append({
            "interview_id": str(itw.id),
            "candidate_id": str(itw.candidate_id),
            "candidate_name": candidate.nom if candidate else "—",
            "global_score": itw.global_score if itw.global_score is not None else (
                round(sum(dimensions[k] * w for k, w in _WEIGHTS.items()) * 10)
            ),
            "recommendation": itw.recommendation.value if itw.recommendation else None,
            "has_report": report is not None,
            "dimensions": dimensions,
            "points_forts": payload.get("points_forts", [])[:3],
            "points_faibles": payload.get("points_faibles", [])[:3],
        })

    return {
        "offer_id": str(offer_id),
        "offer_titre": offer.titre,
        "dimensions_labels": list(_WEIGHTS.keys()),
        "candidates": candidates,
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

    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()

    answers_by_q = {a.question_id: a for a in interview.answers}
    questions = []
    for q in interview.questions:
        a = answers_by_q.get(q.id)
        analysis = json.loads(a.analysis) if (a and a.analysis) else {}
        questions.append({
            "id": str(q.id),
            "order_index": q.order_index,
            "phase": q.phase.value,
            "question": q.question_text,
            "context_hint": q.intent,
            "answered": a is not None and bool(a.answer_text),
            "answer_text": a.answer_text if a else None,
            "score": a.score if a else None,
            "scores": analysis.get("scores", {}),
            "flags": analysis.get("flags", {}),
            "cv_contradiction": analysis.get("cv_contradiction", False),
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
        "candidate_name": candidate.nom if candidate else "—",
        "candidate_email": candidate.email if candidate else None,
        "global_score": interview.global_score,
        "recommendation": interview.recommendation.value if interview.recommendation else None,
        "integrity": _compute_integrity(interview),
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
    pin: Optional[str] = None
    response_time: Optional[float] = None   # secondes pour répondre
    paste_detected: bool = False            # collage détecté sur la réponse
    tab_switches: int = 0                   # cumul changements d'onglet
    fullscreen_exits: int = 0               # cumul sorties plein écran


def _interview_by_token(db: Session, token: str) -> Interview:
    interview = db.query(Interview).filter(Interview.access_token == token).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Lien d'entretien invalide ou expiré")
    return interview


def _window_status(interview: Interview):
    """Retourne ('open'|'not_open'|'expired', message) selon opens_at/deadline."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    def _aware(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    opens_at = _aware(interview.opens_at)
    deadline = _aware(interview.deadline)
    if opens_at and now < opens_at:
        return "not_open", "Cet entretien n'est pas encore ouvert."
    if deadline and now > deadline:
        return "expired", "La date limite de cet entretien est dépassée."
    return "open", ""


class PinPayload(BaseModel):
    pin: str


class EventPayload(BaseModel):
    pin: Optional[str] = None
    type: str   # "fullscreen_exit" | "tab_switch"


MAX_FULLSCREEN_EXITS = 2   # à la 2ᵉ sortie, l'entretien est bloqué


def _questions_payload(interview: Interview):
    answered_ids = {a.question_id for a in interview.answers if a.answer_text}
    return [{
        "id": str(q.id),
        "order_index": q.order_index,
        "phase": q.phase.value,
        "question": q.question_text,
        "context_hint": q.intent,
        "is_followup": bool(q.meta and '"is_followup": true' in q.meta.lower()),
        "answered": q.id in answered_ids,
    } for q in interview.questions]


# GET /interviews/public/{token} — métadonnées (sans questions ; PIN requis ensuite)
@router.get("/interviews/public/{token}", summary="[Candidat] Infos d'accès à l'entretien")
def public_get_interview(token: str, db: Session = Depends(get_db)):
    interview = _interview_by_token(db, token)
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    offer = db.query(JobOffer).filter(JobOffer.id == interview.job_offer_id).first()

    answered = sum(1 for a in interview.answers if a.answer_text)
    access, access_msg = _window_status(interview)
    return {
        "candidate_name": candidate.nom if candidate else "Candidat",
        "offer_titre": offer.titre if offer else "Poste",
        "domaine": interview.domaine,
        "status": interview.status.value,
        "total_questions": len(interview.questions),
        "answered_count": answered,
        "completed": interview.status == InterviewStatus.completed,
        "requires_pin": bool(interview.access_pin),
        "access": access,                 # open | not_open | expired
        "access_message": access_msg,
        "opens_at": interview.opens_at.isoformat() if interview.opens_at else None,
        "deadline": interview.deadline.isoformat() if interview.deadline else None,
    }


# POST /interviews/public/{token}/verify — vérifie le PIN et délivre les questions
@router.post("/interviews/public/{token}/verify", summary="[Candidat] Vérifier le code d'accès")
def public_verify_pin(token: str, payload: PinPayload, db: Session = Depends(get_db)):
    interview = _interview_by_token(db, token)
    access, access_msg = _window_status(interview)
    if access != "open":
        raise HTTPException(status_code=403, detail=access_msg)
    if interview.access_pin and str(payload.pin).strip() != interview.access_pin:
        raise HTTPException(status_code=401, detail="Code d'accès incorrect.")
    if interview.status == InterviewStatus.completed:
        raise HTTPException(status_code=409, detail="Entretien déjà terminé.")
    return {
        "ok": True,
        "total_questions": len(interview.questions),
        "answered_count": sum(1 for a in interview.answers if a.answer_text),
        "questions": _questions_payload(interview),
    }


# POST /interviews/public/{token}/event — signalement temps réel (anti-triche)
@router.post("/interviews/public/{token}/event", summary="[Candidat] Signaler un événement d'intégrité")
def public_report_event(token: str, payload: EventPayload, db: Session = Depends(get_db)):
    interview = _interview_by_token(db, token)
    if interview.access_pin and str(payload.pin or "").strip() != interview.access_pin:
        raise HTTPException(status_code=401, detail="Code d'accès incorrect.")

    integ = json.loads(interview.integrity) if interview.integrity else {}
    blocked = bool(integ.get("blocked"))
    warning = False

    if not blocked:
        if payload.type == "fullscreen_exit":
            n = int(integ.get("fullscreen_exits", 0)) + 1
            integ["fullscreen_exits"] = n
            if n >= MAX_FULLSCREEN_EXITS:
                integ["blocked"] = True
                integ["block_reason"] = f"Entretien interrompu : {n} sorties du plein écran (triche présumée)."
                interview.status = InterviewStatus.abandoned
                blocked = True
            else:
                warning = True   # 1ʳᵉ sortie → dernier avertissement
        elif payload.type == "tab_switch":
            integ["tab_switches"] = int(integ.get("tab_switches", 0)) + 1

    interview.integrity = json.dumps(integ, ensure_ascii=False)
    db.commit()
    return {
        "blocked": blocked,
        "warning": warning,
        "remaining": max(0, MAX_FULLSCREEN_EXITS - int(integ.get("fullscreen_exits", 0))),
    }


# POST /interviews/public/{token}/answer — le candidat répond (score interne, NON renvoyé)
@router.post("/interviews/public/{token}/answer", summary="[Candidat] Soumettre une réponse")
def public_submit_answer(token: str, payload: PublicAnswerPayload, db: Session = Depends(get_db)):
    interview = _interview_by_token(db, token)
    if interview.status == InterviewStatus.completed:
        raise HTTPException(status_code=409, detail="Entretien déjà terminé")

    access, access_msg = _window_status(interview)
    if access != "open":
        raise HTTPException(status_code=403, detail=access_msg)

    # 2ᵉ facteur : le PIN doit accompagner chaque réponse
    if interview.access_pin and str(payload.pin or "").strip() != interview.access_pin:
        raise HTTPException(status_code=401, detail="Code d'accès incorrect.")

    # Entretien bloqué pour triche → plus aucune réponse acceptée
    _integ = json.loads(interview.integrity) if interview.integrity else {}
    if _integ.get("blocked"):
        raise HTTPException(status_code=423, detail=_integ.get("block_reason",
                            "Entretien bloqué pour non-respect des règles d'intégrité."))

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
    answer.response_time = payload.response_time
    answer.paste_detected = 1 if payload.paste_detected else 0

    # Intégrité : le collage est compté ici ; onglet/plein écran via /event (temps réel)
    integ = json.loads(interview.integrity) if interview.integrity else {}
    integ["paste_count"] = int(integ.get("paste_count", 0)) + (1 if payload.paste_detected else 0)
    interview.integrity = json.dumps(integ, ensure_ascii=False)

    if interview.status == InterviewStatus.created:
        interview.status = InterviewStatus.in_progress
    db.commit()

    # ── Adaptatif : relance dynamique si la réponse est faible ──────────────
    # Bornes : phases techniques/situationnelles, réponse faible mais non vide,
    # question d'origine (pas déjà une relance), max 3 relances par entretien.
    MAX_FOLLOWUPS = 3
    followup_out = None
    q_meta = q_dict if isinstance(q_dict, dict) else {}
    is_followup = bool(q_meta.get("is_followup"))
    nb_followups = sum(
        1 for q in interview.questions
        if q.meta and '"is_followup": true' in q.meta.lower()
    )
    if (not is_followup
            and question.phase in (InterviewPhase.technical, InterviewPhase.situational)
            and 0.0 < weighted < 0.5
            and nb_followups < MAX_FOLLOWUPS):
        fu = service.generate_followup(q_meta, payload.answer_text, cv, interview.domaine or "")
        if fu:
            fu_meta = {**fu, "is_followup": True, "parent_id": str(q_uuid)}
            fu_q = InterviewQuestion(
                interview_id=interview.id,
                order_index=question.order_index,   # adjacent à la question parente
                phase=question.phase,
                question_text=fu.get("question", ""),
                target_competence=(fu.get("skill_targeted") or "")[:150] or None,
                intent=(fu.get("context_hint") or "")[:255] or None,
                meta=json.dumps(fu_meta, ensure_ascii=False),
            )
            db.add(fu_q)
            db.commit()
            followup_out = {
                "id": str(fu_q.id),
                "phase": fu_q.phase.value,
                "question": fu_q.question_text,
                "context_hint": fu_q.intent or "",
                "is_followup": True,
            }

    # On NE renvoie PAS le score au candidat (il ne doit pas ajuster ses réponses)
    answered = db.query(InterviewAnswer).filter(
        InterviewAnswer.interview_id == interview.id,
        InterviewAnswer.answer_text.isnot(None),
    ).count()
    total = len(interview.questions)
    return {"ok": True, "answered_count": answered, "total_questions": total,
            "done": answered >= total and followup_out is None,
            "followup": followup_out}
