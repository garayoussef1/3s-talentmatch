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
