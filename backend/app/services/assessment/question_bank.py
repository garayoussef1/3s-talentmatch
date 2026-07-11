"""
Banque de questions à la demande (cache intelligent).

Au lieu d'une banque figée : pour chaque compétence, on vérifie le cache en base ;
si insuffisant, on GÉNÈRE via le LLM local (Ollama) et on stocke. Les compétences
déjà générées sont réutilisées → génération une seule fois.

100% local. Aucune donnée CV n'est envoyée (seul le nom de la compétence l'est).
"""
from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentQuestion, OpenQuestion
from app.services.assessment import question_generator, semantic_scorer

logger = logging.getLogger(__name__)

# Pool plus large que la longueur du test (12) → anti-triche : chaque candidat
# reçoit un sous-ensemble varié (via le RandomesqueSelector du moteur).
MIN_QCM_PER_COMPETENCE = 15
MIN_OPEN_PER_COMPETENCE = 2

# ── Pool PAR OFFRE (génération unique, en arrière-plan) ──────────────────────
# Cibles du pool : assez large pour que chaque candidat reçoive un sous-ensemble
# différent (test = 10 QCM + 3 ouvertes tirés du pool).
POOL_QCM_TARGET = 18
POOL_OPEN_TARGET = 6

# Offres dont la génération est en cours (garde-fou anti-doublon, en mémoire)
_GENERATING: set = set()


def offer_pool_status(db: Session, offer_id) -> dict:
    """État du pool d'une offre : {qcm, open, ready, generating}."""
    n_qcm = db.query(AssessmentQuestion).filter(AssessmentQuestion.job_offer_id == offer_id).count()
    n_open = db.query(OpenQuestion).filter(OpenQuestion.job_offer_id == offer_id).count()
    return {
        "qcm": n_qcm, "open": n_open,
        "ready": n_qcm >= 6 and n_open >= 2,   # seuil minimal pour démarrer un test
        "generating": str(offer_id) in _GENERATING,
    }


def generate_offer_pool(offer_id, offer_titre: str, competences: list[str]) -> None:
    """Génère le pool de questions d'une OFFRE (tâche d'arrière-plan).

    Une seule génération par offre (verrou mémoire). Ouvre sa propre session DB
    car exécutée hors du cycle requête/réponse.
    """
    from app.database import SessionLocal
    key = str(offer_id)
    if key in _GENERATING:
        return
    _GENERATING.add(key)
    db = SessionLocal()
    try:
        status = offer_pool_status(db, offer_id)
        if status["qcm"] >= POOL_QCM_TARGET and status["open"] >= POOL_OPEN_TARGET:
            return
        gen = question_generator.generate_session_questions(
            offer_titre, competences, cv_resume="(pool générique de l'offre)",
            n_qcm=POOL_QCM_TARGET, n_open=POOL_OPEN_TARGET,
        )
        for q in gen["qcm"]:
            db.add(AssessmentQuestion(
                domaine="offre", competence_esco=q["competence"], job_offer_id=offer_id,
                difficulte=q["difficulte"], discrimination=1.0,
                question=q["question"], options=q["options"], bonne_reponse=q["correct"],
            ))
        # Questions ouvertes + embeddings des références (notation locale)
        for q in gen["open"]:
            oq = OpenQuestion(
                domaine="offre", competence_esco=q["competence"], job_offer_id=offer_id,
                question=q["question"], ref_faible=q["ref_faible"],
                ref_correct=q["ref_correct"], ref_expert=q["ref_expert"],
            )
            vecs = semantic_scorer.embed([q["ref_faible"], q["ref_correct"], q["ref_expert"]])
            if vecs is not None:
                oq.emb_faible  = [float(x) for x in vecs[0]]
                oq.emb_correct = [float(x) for x in vecs[1]]
                oq.emb_expert  = [float(x) for x in vecs[2]]
            db.add(oq)
        db.commit()
        logger.info("Pool offre %s généré : %d QCM + %d ouvertes",
                    offer_titre, len(gen["qcm"]), len(gen["open"]))
        # Invitations DIFFÉRÉES : les candidats déjà lancés sur cette offre
        # reçoivent leur email MAINTENANT (questionnaire garanti prêt).
        finalize_pending_sessions(db, offer_id)
    except Exception as exc:
        logger.error("Génération du pool offre %s échouée : %s", offer_titre, exc)
    finally:
        _GENERATING.discard(key)
        db.close()


def _count_qcm(db: Session, competence: str) -> int:
    return (
        db.query(AssessmentQuestion)
        .filter(func.lower(AssessmentQuestion.competence_esco) == competence.lower())
        .count()
    )


def ensure_qcm(db: Session, competence: str, min_count: int = MIN_QCM_PER_COMPETENCE) -> int:
    """Garantit ≥ min_count QCM en cache pour la compétence (génère si besoin)."""
    existing = _count_qcm(db, competence)
    if existing >= min_count:
        return existing
    try:
        generated = question_generator.generate_qcm(competence, n=min_count)
    except Exception as exc:
        logger.warning("Génération QCM échouée pour %s : %s", competence, exc)
        return existing
    for g in generated:
        db.add(AssessmentQuestion(
            domaine="auto", competence_esco=competence,
            difficulte=g["difficulte"], discrimination=1.0,
            question=g["question"], options=g["options"], bonne_reponse=g["correct"],
        ))
    db.commit()
    return _count_qcm(db, competence)


def ensure_open(db: Session, competence: str, min_count: int = MIN_OPEN_PER_COMPETENCE) -> int:
    """Garantit ≥ min_count question(s) ouverte(s) (générées + embeddings calculés)."""
    existing = (
        db.query(OpenQuestion)
        .filter(func.lower(OpenQuestion.competence_esco) == competence.lower())
        .count()
    )
    if existing >= min_count:
        return existing
    try:
        generated = question_generator.generate_open_questions(competence, n=min_count)
    except Exception as exc:
        logger.warning("Génération question ouverte échouée pour %s : %s", competence, exc)
        return existing

    for g in generated:
        oq = OpenQuestion(
            domaine="auto", competence_esco=competence, question=g["question"],
            ref_faible=g["ref_faible"], ref_correct=g["ref_correct"], ref_expert=g["ref_expert"],
        )
        # Embeddings BGE-M3 (local) pour la notation sémantique
        vecs = semantic_scorer.embed([g["ref_faible"], g["ref_correct"], g["ref_expert"]])
        if vecs is not None:
            oq.emb_faible  = [float(x) for x in vecs[0]]
            oq.emb_correct = [float(x) for x in vecs[1]]
            oq.emb_expert  = [float(x) for x in vecs[2]]
        db.add(oq)
    db.commit()
    return existing + len(generated)


def prepare_competences(db: Session, competences: list[str]) -> dict:
    """Prépare (génère + cache) les questions pour une liste de compétences.

    Retourne un récap {competence: {qcm, open, genere}}.
    """
    recap = {}
    for comp in competences:
        comp = (comp or "").strip()
        if not comp:
            continue
        before = _count_qcm(db, comp)
        nb_qcm = ensure_qcm(db, comp)
        nb_open = ensure_open(db, comp)
        recap[comp] = {"qcm": nb_qcm, "open": nb_open, "genere": before < nb_qcm}
    return recap


# ─────────────────────────────────────────────────────────────────────────────
# Remplissage du questionnaire d'une session + invitation différée
# ─────────────────────────────────────────────────────────────────────────────
SESSION_QCM_COUNT = 10
SESSION_OPEN_COUNT = 3


def fill_session_from_pool(db: Session, session) -> bool:
    """Remplit le questionnaire d'un candidat depuis le pool de l'OFFRE.

    Tirage aléatoire seedé par la session → chaque candidat reçoit un
    sous-ensemble DIFFÉRENT. Les questions du RECRUTEUR (déjà stockées dans
    session_open) sont conservées. Retourne False si le pool n'est pas prêt.
    """
    import random as _random

    status = offer_pool_status(db, session.job_offer_id)
    if not status["ready"]:
        return False

    rng = _random.Random(str(session.id))
    qcm_rows = (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.job_offer_id == session.job_offer_id)
        .all()
    )
    open_rows = (
        db.query(OpenQuestion)
        .filter(OpenQuestion.job_offer_id == session.job_offer_id,
                OpenQuestion.emb_expert.isnot(None))
        .all()
    )
    qcm_pick = rng.sample(qcm_rows, min(SESSION_QCM_COUNT, len(qcm_rows)))
    open_pick = rng.sample(open_rows, min(SESSION_OPEN_COUNT, len(open_rows)))

    session.session_qcm = [{
        "qid": f"q{i}", "competence": r.competence_esco, "difficulte": r.difficulte,
        "question": r.question, "options": r.options, "correct": r.bonne_reponse,
    } for i, r in enumerate(qcm_pick)]

    generated_open = [{
        "qid": f"o{i}", "source": "ia", "competence": r.competence_esco,
        "question": r.question,
        "emb_faible": r.emb_faible, "emb_correct": r.emb_correct, "emb_expert": r.emb_expert,
    } for i, r in enumerate(open_pick)]
    recruiter_qs = [o for o in (session.session_open or []) if o.get("source") == "recruteur"]
    session.session_open = generated_open + recruiter_qs
    db.commit()
    return True


def send_invitation(db: Session, session) -> bool:
    """Envoie l'email d'invitation + la notification in-app pour une session.

    Appelé au launch si le questionnaire est prêt, sinon en DIFFÉRÉ à la fin
    de la génération du pool — le candidat ne reçoit JAMAIS un lien vers un
    questionnaire pas prêt.
    """
    import os as _os
    from app.models.candidate import Candidate
    from app.models.job_offer import JobOffer
    from app.models.notification import Notification
    from app.services import email_service

    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    offer = db.query(JobOffer).filter(JobOffer.id == session.job_offer_id).first()
    if not candidate or not offer:
        return False

    frontend = _os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    full_link = f"{frontend}/evaluation/{session.access_token}"
    prenom = (candidate.nom or "Candidat").split()[0]

    email_sent = False
    if candidate.email:
        try:
            email_sent = email_service.send_assessment_invitation_email(
                candidate.email, prenom, offer.titre or "le poste", full_link,
                opens_at=session.opens_at, deadline=session.deadline,
                access_pin=session.access_pin,
            )
        except Exception:
            email_sent = False
    if candidate.user_id:
        try:
            db.add(Notification(
                user_id=candidate.user_id,
                type="interview_invite",
                title="Invitation à une évaluation technique",
                message=f"Vous êtes invité(e) à une évaluation pour « {offer.titre} ».",
                link=f"/evaluation/{session.access_token}",
            ))
            db.commit()
        except Exception:
            pass
    return email_sent


def finalize_pending_sessions(db: Session, offer_id) -> int:
    """Après génération du pool : remplit les sessions en attente de cette offre
    et envoie LEURS invitations (email différé). Retourne le nb finalisé."""
    from app.models.assessment import AssessmentSession, AssessmentStatus
    pending = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.job_offer_id == offer_id,
                AssessmentSession.status == AssessmentStatus.in_progress)
        .all()
    )
    done = 0
    for s in pending:
        if s.session_qcm:      # déjà rempli → invitation déjà envoyée
            continue
        if fill_session_from_pool(db, s):
            send_invitation(db, s)
            done += 1
    if done:
        logger.info("Pool prêt : %d invitation(s) différée(s) envoyée(s)", done)
    return done
