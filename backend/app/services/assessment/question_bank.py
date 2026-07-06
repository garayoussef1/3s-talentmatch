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
