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

import hashlib
import random
import secrets
import os
from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.models.match import Match
from app.models.assessment import (
    AssessmentQuestion, AssessmentSession, AssessmentStatus, OpenQuestion,
    RealityGapResult,
)
from app.services.assessment import cat_engine, reality_gap, question_bank

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


class OpenAnswerPayload(BaseModel):
    question_id: str   # id d'une OpenQuestion
    answer: str


class SessionOpenAnswerPayload(BaseModel):
    session_id: str
    question_id: str   # id d'une OpenQuestion
    answer: str


class RealityGapPayload(BaseModel):
    candidate_id: str
    offer_id: str
    session_id: str


class PreparePayload(BaseModel):
    offer_id: Optional[str] = None
    competences: Optional[List[str]] = None   # sinon, celles de l'offre


# ── Helpers ──────────────────────────────────────────────────────────────────
def _pool(db: Session, domaine: str) -> List[AssessmentQuestion]:
    """Banque de questions du domaine, ordre déterministe (= index catsim)."""
    return (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.domaine == domaine)
        .order_by(AssessmentQuestion.created_at, AssessmentQuestion.id)
        .all()
    )


def _pool_for_competences(db: Session, competences: List[str]) -> List[AssessmentQuestion]:
    """Banque = questions (en cache) des compétences ciblées par l'offre."""
    if not competences:
        return []
    lowered = {c.lower() for c in competences}
    rows = (
        db.query(AssessmentQuestion)
        .filter(func.lower(AssessmentQuestion.competence_esco).in_(lowered))
        .order_by(AssessmentQuestion.competence_esco, AssessmentQuestion.difficulte, AssessmentQuestion.id)
        .all()
    )
    return rows


def _option_permutation(session_id: str, question_id: str, n: int) -> List[int]:
    """Permutation déterministe des options pour (session, question).

    Anti-triche : chaque candidat voit les options dans un ordre différent.
    Déterministe (hash) → reproductible côté serveur sans stockage.
    perm[position_affichée] = index_original.
    """
    seed = int(hashlib.md5(f"{session_id}:{question_id}".encode()).hexdigest(), 16)
    r = random.Random(seed)
    perm = list(range(n))
    r.shuffle(perm)
    return perm


def _question_public(q: AssessmentQuestion, session_id: str) -> dict:
    """Question renvoyée au candidat — options MÉLANGÉES, sans la bonne réponse."""
    opts = q.options or []
    perm = _option_permutation(session_id, str(q.id), len(opts))
    shuffled = [opts[perm[i]] for i in range(len(opts))]
    return {
        "question_id": str(q.id),
        "competence": q.competence_esco,
        "difficulte": q.difficulte,
        "question": q.question,
        "options": shuffled,
    }


def _session_pool(db: Session, session: AssessmentSession) -> List[AssessmentQuestion]:
    """Banque UNIFIÉE d'une session : compétences de l'offre, sinon repli seed IT.

    Garantit que /answer et /public utilisent EXACTEMENT le même pool
    (donc le même arrêt à TEST_LENGTH questions).
    """
    competences = []
    if session.job_offer_id:
        offer = db.query(JobOffer).filter(JobOffer.id == session.job_offer_id).first()
        if offer and offer.competences_requises:
            competences = list(offer.competences_requises)
    pool = _pool_for_competences(db, competences)
    if len(pool) < 3:
        dom = session.domaine if session.domaine and session.domaine != "auto" else "IT"
        pool = _pool(db, dom)
    if len(pool) < 3:
        pool = _pool(db, "IT")
    return pool


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


# ── POST /assessment/prepare ─────────────────────────────────────────────────
@router.post("/assessment/prepare", summary="Générer/mettre en cache les questions d'une offre")
def prepare_assessment(payload: PreparePayload, db: Session = Depends(get_db)):
    """Génère (via LLM local) et met en cache les questions des compétences ciblées.

    Étape recruteur, potentiellement longue (génération Ollama) mais faite UNE
    fois par compétence puis réutilisée. N'envoie que le nom des compétences.
    """
    competences = list(payload.competences or [])
    if payload.offer_id and not competences:
        try:
            offer = db.query(JobOffer).filter(JobOffer.id == UUID(str(payload.offer_id))).first()
        except (ValueError, AttributeError):
            offer = None
        if not offer:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        competences = list(offer.competences_requises or [])
    if not competences:
        raise HTTPException(status_code=400, detail="Aucune compétence à préparer")

    recap = question_bank.prepare_competences(db, competences)
    total_qcm = sum(r["qcm"] for r in recap.values())
    return {"competences": recap, "total_qcm": total_qcm, "pret": total_qcm >= 3}


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

    # Le test cible en priorité les compétences REQUISES de l'offre (cache).
    offer_uuid = None
    pool: List[AssessmentQuestion] = []
    if payload.offer_id:
        try:
            offer_uuid = UUID(str(payload.offer_id))
            offer = db.query(JobOffer).filter(JobOffer.id == offer_uuid).first()
            if offer and offer.competences_requises:
                pool = _pool_for_competences(db, list(offer.competences_requises))
        except (ValueError, AttributeError):
            offer_uuid = None

    # Repli : banque par domaine (compat / démo)
    if len(pool) < 3:
        pool = _pool(db, payload.domaine)
    if len(pool) < 3:
        raise HTTPException(
            status_code=400,
            detail="Questions non préparées pour cette offre. Lancez d'abord /assessment/prepare.",
        )

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
        "question": _question_public(question, str(session.id)),
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

    pool = _session_pool(db, session)
    id_to_index = {str(q.id): i for i, q in enumerate(pool)}
    if str(q_uuid) not in id_to_index:
        raise HTTPException(status_code=404, detail="Question hors banque")
    question = pool[id_to_index[str(q_uuid)]]

    # Éviter le double comptage d'une même question
    administered = list(session.administered or [])
    if any(it["question_id"] == str(q_uuid) for it in administered):
        raise HTTPException(status_code=409, detail="Question déjà répondue")

    # Les options ont été mélangées à l'affichage → on remappe l'index choisi
    perm = _option_permutation(str(session.id), str(q_uuid), len(question.options or []))
    try:
        original_choice = perm[int(payload.reponse)]
    except (IndexError, ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Réponse hors options")
    correct = original_choice == int(question.bonne_reponse)
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

    # Fin de la phase QCM ? (le test complet n'est "completed" qu'au /finish,
    # car il reste éventuellement les questions ouvertes de raisonnement)
    if cat_engine.is_finished(len(administered), len(pool)):
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
        "question": _question_public(next_q, str(session.id)),
    }


# ── GET /assessment/open-questions ───────────────────────────────────────────
@router.get("/assessment/open-questions", summary="Lister les questions ouvertes d'un domaine")
def list_open_questions(domaine: str = "IT", db: Session = Depends(get_db)):
    qs = db.query(OpenQuestion).filter(OpenQuestion.domaine == domaine).all()
    return {"domaine": domaine, "questions": [
        {"question_id": str(q.id), "competence": q.competence_esco, "question": q.question}
        for q in qs
    ]}


# ── POST /assessment/open-question ───────────────────────────────────────────
@router.post("/assessment/open-question", summary="Noter une réponse ouverte (sémantique)")
def score_open_question(payload: OpenAnswerPayload, db: Session = Depends(get_db)):
    try:
        q_uuid = UUID(str(payload.question_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="question_id invalide")

    q = db.query(OpenQuestion).filter(OpenQuestion.id == q_uuid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question ouverte non trouvée")
    if not (q.emb_faible and q.emb_correct and q.emb_expert):
        raise HTTPException(status_code=503, detail="Embeddings non calculés pour cette question")

    # Import local : évite de charger BGE-M3 au démarrage de l'app
    from app.services.assessment import semantic_scorer
    result = semantic_scorer.score_open_answer(
        payload.answer, q.emb_faible, q.emb_correct, q.emb_expert
    )
    return {
        "question_id": str(q.id),
        "competence": q.competence_esco,
        **result,
    }


# ── POST /assessment/open-answer ─────────────────────────────────────────────
@router.post("/assessment/open-answer", summary="Répondre à une question ouverte (liée à la session)")
def submit_open_answer(payload: SessionOpenAnswerPayload, db: Session = Depends(get_db)):
    try:
        sess_uuid = UUID(str(payload.session_id))
        q_uuid = UUID(str(payload.question_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Identifiant invalide")

    session = db.query(AssessmentSession).filter(AssessmentSession.id == sess_uuid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    q = db.query(OpenQuestion).filter(OpenQuestion.id == q_uuid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question ouverte non trouvée")
    if not (q.emb_faible and q.emb_correct and q.emb_expert):
        raise HTTPException(status_code=503, detail="Embeddings non calculés")

    from app.services.assessment import semantic_scorer
    result = semantic_scorer.score_open_answer(payload.answer, q.emb_faible, q.emb_correct, q.emb_expert)

    # Stockage dans la session (pour le rapport IA) — pas de score renvoyé au candidat
    answers = list(session.open_answers or [])
    answers = [a for a in answers if a.get("question_id") != str(q_uuid)]  # remplace si déjà répondu
    answers.append({
        "question_id": str(q_uuid),
        "competence": q.competence_esco,
        "question": q.question,
        "answer": payload.answer,
        "score": result.get("score"),
        "similarites": result.get("similarites", {}),
    })
    session.open_answers = answers
    db.commit()
    return {"ok": True, "answered": len(answers)}


# ── POST /assessment/report/{session_id} ─────────────────────────────────────
@router.post("/assessment/report/{session_id}", summary="Générer le rapport IA (local)")
def generate_assessment_report(session_id: UUID, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    offer = db.query(JobOffer).filter(JobOffer.id == session.job_offer_id).first() if session.job_offer_id else None

    # Reality Gap (le plus récent pour ce couple, s'il existe)
    rg = None
    if session.job_offer_id:
        rg_row = (
            db.query(RealityGapResult)
            .filter(RealityGapResult.candidate_id == session.candidate_id,
                    RealityGapResult.job_offer_id == session.job_offer_id)
            .order_by(RealityGapResult.created_at.desc())
            .first()
        )
        if rg_row:
            rg = {
                "reality_gap_score": rg_row.reality_gap_score,
                "fiabilite_cv": rg_row.fiabilite_cv,
                "niveau_label": rg_row.niveau_label,
                "details": rg_row.details,
            }

    from app.services.assessment import report_generator
    try:
        report = report_generator.generate_report(
            candidate.nom if candidate else "Candidat",
            offer.titre if offer else "le poste",
            session.competence_scores or {},
            session.open_answers or [],
            rg,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur génération rapport : {exc}")

    return {"session_id": str(session_id), "report": report}


# ── POST /assessment/reality-gap ─────────────────────────────────────────────
@router.post("/assessment/reality-gap", summary="Calculer le Reality Gap Score")
def compute_reality_gap_endpoint(payload: RealityGapPayload, db: Session = Depends(get_db)):
    try:
        cand_uuid  = UUID(str(payload.candidate_id))
        offer_uuid = UUID(str(payload.offer_id))
        sess_uuid  = UUID(str(payload.session_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Identifiant invalide")

    candidate = db.query(Candidate).filter(Candidate.id == cand_uuid).first()
    offer     = db.query(JobOffer).filter(JobOffer.id == offer_uuid).first()
    session   = db.query(AssessmentSession).filter(AssessmentSession.id == sess_uuid).first()
    if not candidate or not offer or not session:
        raise HTTPException(status_code=404, detail="Candidat, offre ou session introuvable")

    demonstrated = session.competence_scores or {}
    if not demonstrated:
        raise HTTPException(status_code=400, detail="Test non terminé : aucun niveau démontré")

    # Poids = importance de la compétence dans l'offre (requise 1.0 · appréciée 0.5)
    requises   = {s.lower() for s in (offer.competences_requises or [])}
    appreciees = {s.lower() for s in (offer.competences_appreciees or [])}
    weights = {}
    for comp in demonstrated:
        cl = comp.lower()
        weights[comp] = 1.0 if cl in requises else (0.5 if cl in appreciees else 1.0)

    # Calcul du gap (déclaré CV vs démontré test)
    result = reality_gap.compute_reality_gap(candidate.parsed_data or {}, demonstrated, weights)

    # Score final ajusté (si un match existe pour ce couple)
    match = (
        db.query(Match)
        .filter(Match.candidate_id == cand_uuid, Match.job_offer_id == offer_uuid)
        .first()
    )
    score_final = None
    if match and match.score is not None:
        score_final = reality_gap.adjust_matching_score(match.score, result["fiabilite_cv"])

    # Persistance (on remplace un éventuel résultat précédent)
    db.query(RealityGapResult).filter(
        RealityGapResult.candidate_id == cand_uuid,
        RealityGapResult.job_offer_id == offer_uuid,
    ).delete()
    rg = RealityGapResult(
        candidate_id=cand_uuid, job_offer_id=offer_uuid, session_id=sess_uuid,
        reality_gap_score=result["reality_gap_score"],
        fiabilite_cv=result["fiabilite_cv"],
        score_final_ajuste=score_final,
        details=result["details"],
        niveau_label=result["niveau_label"],
    )
    db.add(rg)
    db.commit()

    return {
        "candidate_id": str(cand_uuid),
        "offer_id": str(offer_uuid),
        "matching_score": round(match.score, 4) if match and match.score is not None else None,
        "score_final_ajuste": score_final,
        **result,
    }


# ── GET /assessment/reality-gap/{candidate_id}/{offer_id} ────────────────────
@router.get("/assessment/reality-gap/{candidate_id}/{offer_id}", summary="Récupérer un Reality Gap")
def get_reality_gap(candidate_id: UUID, offer_id: UUID, db: Session = Depends(get_db)):
    rg = (
        db.query(RealityGapResult)
        .filter(RealityGapResult.candidate_id == candidate_id,
                RealityGapResult.job_offer_id == offer_id)
        .order_by(RealityGapResult.created_at.desc())
        .first()
    )
    if not rg:
        raise HTTPException(status_code=404, detail="Aucun Reality Gap calculé")
    return {
        "reality_gap_score": rg.reality_gap_score,
        "fiabilite_cv": rg.fiabilite_cv,
        "score_final_ajuste": rg.score_final_ajuste,
        "niveau_label": rg.niveau_label,
        "details": rg.details,
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


# ═════════════════════════════════════════════════════════════════════════════
# LANCEMENT RECRUTEUR + ACCÈS CANDIDAT PAR JETON (test autonome via lien)
# ═════════════════════════════════════════════════════════════════════════════
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


class LaunchPayload(BaseModel):
    candidate_id: str
    offer_id: str
    recruiter_questions: Optional[List[str]] = None   # questions ajoutées par le recruteur


def _session_by_token(db: Session, token: str) -> AssessmentSession:
    s = db.query(AssessmentSession).filter(AssessmentSession.access_token == token).first()
    if not s:
        raise HTTPException(status_code=404, detail="Lien d'évaluation invalide")
    return s


def _session_qcm_pool_rows(session: AssessmentSession):
    """Adapte session_qcm (dicts) au format attendu par cat_engine (a/b/c/d)."""
    class _Q:  # objet léger compatible build_item_bank
        def __init__(self, d):
            self.discrimination = 1.0
            self.difficulte = d["difficulte"]
    return [_Q(d) for d in (session.session_qcm or [])]


# Taille du questionnaire servi à CHAQUE candidat (tiré du pool de l'offre)
SESSION_QCM_COUNT = 10
SESSION_OPEN_COUNT = 3


def _fill_session_from_pool(db: Session, session: AssessmentSession) -> bool:
    """Remplit le questionnaire du candidat depuis le pool de l'OFFRE.

    Tirage aléatoire seedé par la session → chaque candidat reçoit un
    sous-ensemble DIFFÉRENT du pool. Retourne False si le pool n'est pas prêt.
    """
    status = question_bank.offer_pool_status(db, session.job_offer_id)
    if not status["ready"]:
        return False

    rng = random.Random(str(session.id))
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
    # Conserver les questions RECRUTEUR déjà posées au launch
    recruiter_qs = [o for o in (session.session_open or []) if o.get("source") == "recruteur"]
    session.session_open = generated_open + recruiter_qs
    db.commit()
    return True


# ── POST /assessment/launch (recruteur) ──────────────────────────────────────
@router.post("/assessment/launch", summary="[Recruteur] Lancer une évaluation (instantané)")
def launch_assessment(payload: LaunchPayload, background_tasks: BackgroundTasks,
                      db: Session = Depends(get_db)):
    """INSTANTANÉ : crée la session + le lien candidat immédiatement.

    Le pool de questions de l'OFFRE est généré UNE seule fois, en ARRIÈRE-PLAN
    (Ollama local). Les lancements suivants sur la même offre sont immédiats.
    Chaque candidat recevra un sous-ensemble différent du pool (anti-triche).
    """
    try:
        cand_uuid = UUID(str(payload.candidate_id))
        offer_uuid = UUID(str(payload.offer_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Identifiant invalide")

    candidate = db.query(Candidate).filter(Candidate.id == cand_uuid).first()
    offer = db.query(JobOffer).filter(JobOffer.id == offer_uuid).first()
    if not candidate or not offer:
        raise HTTPException(status_code=404, detail="Candidat ou offre introuvable")

    # Questions personnalisées du recruteur (stockées dès maintenant)
    session_open = []
    for k, rq in enumerate(payload.recruiter_questions or []):
        rq = (rq or "").strip()
        if rq:
            session_open.append({
                "qid": f"r{k}", "source": "recruteur",
                "competence": "question recruteur", "question": rq,
            })

    session = AssessmentSession(
        candidate_id=cand_uuid, job_offer_id=offer_uuid,
        domaine=offer.domaine_metier or "IT",
        status=AssessmentStatus.in_progress,
        access_token=secrets.token_urlsafe(24),
        theta=0.0, administered=[], competence_scores={}, open_answers=[],
        session_qcm=[], session_open=session_open,
    )
    db.add(session)
    db.commit()

    # Pool de l'offre : prêt ? sinon génération en arrière-plan (une seule fois)
    status = question_bank.offer_pool_status(db, offer_uuid)
    if not status["ready"] and not status["generating"]:
        background_tasks.add_task(
            question_bank.generate_offer_pool,
            offer_uuid, offer.titre or "le poste", list(offer.competences_requises or []),
        )

    # Si le pool est déjà prêt, on remplit le questionnaire tout de suite
    if status["ready"]:
        _fill_session_from_pool(db, session)

    return {
        "session_id": str(session.id),
        "access_token": session.access_token,
        "candidate_link": f"/evaluation/{session.access_token}",
        "full_link": f"{FRONTEND_URL}/evaluation/{session.access_token}",
        "candidate_name": candidate.nom,
        "offer_titre": offer.titre,
        "pool_ready": status["ready"],
        "pool_generating": (not status["ready"]),
    }


# ── GET /assessment/public/{token} (candidat) ────────────────────────────────
@router.get("/assessment/public/{token}", summary="[Candidat] État + question courante")
def public_get(token: str, db: Session = Depends(get_db)):
    session = _session_by_token(db, token)
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    offer = db.query(JobOffer).filter(JobOffer.id == session.job_offer_id).first() if session.job_offer_id else None

    # Questionnaire pas encore rempli → tenter depuis le pool de l'offre ;
    # si le pool est en cours de génération, le candidat patiente.
    if not (session.session_qcm or []) and session.status != AssessmentStatus.completed:
        if not _fill_session_from_pool(db, session):
            return {
                "candidate_name": candidate.nom if candidate else "Candidat",
                "offer_titre": offer.titre if offer else "Poste",
                "status": session.status.value,
                "completed": False,
                "phase": "preparing",
                "message": "Votre questionnaire est en cours de préparation. Revenez dans quelques minutes.",
            }

    qcm = session.session_qcm or []
    administered = session.administered or []
    total_qcm = min(cat_engine.TEST_LENGTH, len(qcm))
    qcm_done = len(administered) >= total_qcm

    base = {
        "candidate_name": candidate.nom if candidate else "Candidat",
        "offer_titre": offer.titre if offer else "Poste",
        "status": session.status.value,
        "total_qcm": total_qcm,
        "answered_qcm": len(administered),
        "completed": session.status == AssessmentStatus.completed,
    }
    if session.status == AssessmentStatus.completed:
        return {**base, "phase": "done"}

    if qcm and not qcm_done:
        # Sélection adaptative sur les questions DE CETTE SESSION
        bank = cat_engine.build_item_bank(_session_qcm_pool_rows(session))
        idx = cat_engine.select_next_index(bank, [a["index"] for a in administered], session.theta)
        if idx is not None:
            q = qcm[idx]
            perm = _option_permutation(str(session.id), q["qid"], len(q["options"]))
            return {**base, "phase": "qcm", "question": {
                "question_id": q["qid"],
                "competence": q["competence"],
                "difficulte": q["difficulte"],
                "question": q["question"],
                "options": [q["options"][perm[i]] for i in range(len(q["options"]))],
            }}

    # Phase questions ouvertes (IA + recruteur) de cette session
    answered_open = {a["question_id"] for a in (session.open_answers or [])}
    open_qs = [
        {"question_id": o["qid"], "competence": o.get("competence", ""),
         "question": o["question"], "source": o.get("source", "ia")}
        for o in (session.session_open or [])
        if o["qid"] not in answered_open
    ]
    return {**base, "phase": "open", "open_questions": open_qs}


# ── POST /assessment/public/{token}/answer (candidat, QCM) ───────────────────
@router.post("/assessment/public/{token}/answer", summary="[Candidat] Répondre à un QCM")
def public_answer(token: str, payload: AnswerPayload, db: Session = Depends(get_db)):
    session = _session_by_token(db, token)
    if session.status == AssessmentStatus.completed:
        raise HTTPException(status_code=409, detail="Évaluation déjà terminée")

    qcm = session.session_qcm or []
    by_qid = {q["qid"]: (i, q) for i, q in enumerate(qcm)}
    if payload.question_id not in by_qid:
        raise HTTPException(status_code=404, detail="Question hors session")
    idx, q = by_qid[payload.question_id]

    administered = list(session.administered or [])
    if any(a["question_id"] == payload.question_id for a in administered):
        raise HTTPException(status_code=409, detail="Question déjà répondue")

    # Remap de l'option choisie (options mélangées à l'affichage)
    perm = _option_permutation(str(session.id), q["qid"], len(q["options"]))
    try:
        original = perm[int(payload.reponse)]
    except (IndexError, ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Réponse hors options")
    correct = original == int(q["correct"])

    administered.append({
        "question_id": q["qid"], "index": idx,
        "competence": q["competence"], "difficulte": q["difficulte"],
        "reponse": original, "correct": correct,
    })

    bank = cat_engine.build_item_bank(_session_qcm_pool_rows(session))
    session.theta = cat_engine.estimate_theta(
        bank, [a["index"] for a in administered], [a["correct"] for a in administered], session.theta)
    session.administered = administered
    session.competence_scores = cat_engine.competence_scores(administered)
    db.commit()

    total_qcm = min(cat_engine.TEST_LENGTH, len(qcm))
    return {"done": len(administered) >= total_qcm, "progression": len(administered)}


# ── POST /assessment/public/{token}/open-answer (candidat) ───────────────────
@router.post("/assessment/public/{token}/open-answer", summary="[Candidat] Répondre à une question ouverte")
def public_open_answer(token: str, payload: SessionOpenAnswerPayload, db: Session = Depends(get_db)):
    session = _session_by_token(db, token)
    if session.status == AssessmentStatus.completed:
        raise HTTPException(status_code=409, detail="Évaluation déjà terminée")

    target = next((o for o in (session.session_open or []) if o["qid"] == payload.question_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Question hors session")

    # Notation sémantique locale (questions IA uniquement — celles du recruteur
    # sont jugées par lui à la lecture des réponses)
    score, sims = None, {}
    if target.get("emb_expert"):
        from app.services.assessment import semantic_scorer
        res = semantic_scorer.score_open_answer(
            payload.answer, target["emb_faible"], target["emb_correct"], target["emb_expert"])
        score, sims = res.get("score"), res.get("similarites", {})

    answers = [a for a in (session.open_answers or []) if a.get("question_id") != payload.question_id]
    answers.append({
        "question_id": payload.question_id,
        "competence": target.get("competence", ""),
        "question": target["question"],
        "source": target.get("source", "ia"),
        "answer": payload.answer,
        "score": score,
        "similarites": sims,
    })
    session.open_answers = answers
    db.commit()
    return {"ok": True, "answered": len(answers)}


# ── GET /assessment/detail/{session_id} (recruteur : vérifier les réponses) ──
@router.get("/assessment/detail/{session_id}", summary="[Recruteur] Toutes les questions/réponses")
def assessment_detail(session_id: UUID, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    qcm_map = {q["qid"]: q for q in (session.session_qcm or [])}
    qcm_detail = []
    for a in (session.administered or []):
        q = qcm_map.get(a["question_id"], {})
        qcm_detail.append({
            "competence": a.get("competence"),
            "difficulte": a.get("difficulte"),
            "question": q.get("question", ""),
            "options": q.get("options", []),
            "bonne_reponse": q.get("correct"),
            "reponse_candidat": a.get("reponse"),
            "correct": a.get("correct"),
        })

    return {
        "session_id": str(session.id),
        "status": session.status.value,
        "niveau_global": cat_engine.theta_to_niveau(session.theta),
        "competence_scores": session.competence_scores or {},
        "qcm": qcm_detail,
        "open_answers": session.open_answers or [],
    }


# ── POST /assessment/public/{token}/finish (candidat) ────────────────────────
@router.post("/assessment/public/{token}/finish", summary="[Candidat] Terminer l'évaluation")
def public_finish(token: str, db: Session = Depends(get_db)):
    session = _session_by_token(db, token)
    session.status = AssessmentStatus.completed
    session.completed_at = func.now()
    db.commit()
    # Calcul du Reality Gap (best-effort)
    if session.job_offer_id and session.competence_scores:
        try:
            compute_reality_gap_endpoint(
                RealityGapPayload(candidate_id=str(session.candidate_id),
                                  offer_id=str(session.job_offer_id),
                                  session_id=str(session.id)), db)
        except Exception:
            pass
    return {"ok": True, "completed": True}
