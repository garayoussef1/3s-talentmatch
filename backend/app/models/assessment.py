"""
Modèles — Évaluation "Reality Gap Score".

Objectif : mesurer l'écart entre ce que le candidat DÉCLARE (CV) et ce qu'il
DÉMONTRE réellement dans un test d'évaluation. Deux volets :

  • Module 1 — Test technique adaptatif (IRT/CAT via catsim) : QCM dont la
    difficulté s'ajuste aux réponses, converge vers un niveau estimé (theta).
  • Module 2 — Questions ouvertes notées par similarité sémantique (BGE-M3)
    contre des réponses de référence (experte / correcte / faible).

Le tout est 100% LOCAL (aucune API externe) — contrainte de confidentialité.
"""
from sqlalchemy import (
    Column, Float, Integer, DateTime, ForeignKey, Text, String, JSON,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class AssessmentStatus(str, enum.Enum):
    in_progress = "in_progress"   # test en cours
    completed   = "completed"     # test terminé (theta estimé)
    abandoned   = "abandoned"


# ─────────────────────────────────────────────────────────────────────────────
# Banque de questions QCM (Module 1 — test adaptatif IRT)
# ─────────────────────────────────────────────────────────────────────────────
class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    domaine         = Column(String(80), nullable=False, index=True)   # ex: "IT"
    competence_esco = Column(String(150), nullable=False, index=True)  # ex: "Python"
    # Pool par OFFRE : questions générées une fois pour l'offre, chaque candidat
    # en reçoit un sous-ensemble différent (lancements instantanés).
    job_offer_id    = Column(UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), nullable=True, index=True)

    # Paramètres IRT (modèle logistique)
    difficulte    = Column(Integer, nullable=False)   # 1-10 (mappé sur b ∈ [-3, 3])
    discrimination = Column(Float, default=1.0, nullable=False)  # paramètre a (pouvoir discriminant)

    question      = Column(Text, nullable=False)
    options       = Column(JSON, nullable=False)      # liste de choix (ex: ["A", "B", "C", "D"])
    bonne_reponse = Column(Integer, nullable=False)   # index de la bonne option (0-based)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AssessmentQuestion {self.competence_esco} diff={self.difficulte}>"


# ─────────────────────────────────────────────────────────────────────────────
# Session de test d'un candidat (déroulé adaptatif)
# ─────────────────────────────────────────────────────────────────────────────
class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_offer_id = Column(UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="SET NULL"), nullable=True, index=True)

    domaine = Column(String(80), nullable=False)
    status  = Column(SAEnum(AssessmentStatus), default=AssessmentStatus.in_progress, nullable=False)

    # Jeton d'accès candidat (test autonome via lien, sans compte)
    access_token = Column(String(64), unique=True, index=True, nullable=True)
    # Code PIN (2ᵉ facteur) envoyé par email, saisi avant de démarrer
    access_pin = Column(String(12), nullable=True)

    # Fenêtre de passation définie par le recruteur
    opens_at = Column(DateTime(timezone=True), nullable=True)   # date d'ouverture
    deadline = Column(DateTime(timezone=True), nullable=True)   # date limite

    theta = Column(Float, nullable=True)   # niveau estimé (échelle IRT, ~[-3, 3])

    # Historique des items administrés : [{question_id, difficulte, reponse, correct}]
    administered = Column(JSON, default=list, nullable=True)
    # Niveau démontré agrégé par compétence (0-10) : {"Python": 7.2, ...}
    competence_scores = Column(JSON, default=dict, nullable=True)
    # Réponses ouvertes (raisonnement) : [{question_id, competence, question, answer,
    #   score, similarites}] — sert au rapport IA.
    open_answers = Column(JSON, default=list, nullable=True)

    # Signaux d'intégrité anti-triche (JSON) : sorties plein écran, changements
    # d'onglet, collages, blocage 2-strikes → score d'intégrité pour le recruteur.
    integrity = Column(JSON, default=dict, nullable=True)

    # Questions générées À LA VOLÉE pour CETTE session (uniques par entretien,
    # à partir de l'offre + du CV — pas de banque partagée) :
    #   session_qcm  : [{qid, competence, difficulte, question, options, correct}]
    #   session_open : [{qid, competence, question, ref_faible, ref_correct,
    #                    ref_expert, emb_*, source: "ia"|"recruteur"}]
    session_qcm  = Column(JSON, default=list, nullable=True)
    session_open = Column(JSON, default=list, nullable=True)

    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AssessmentSession {self.domaine} status={self.status} theta={self.theta}>"


# ─────────────────────────────────────────────────────────────────────────────
# Questions ouvertes (Module 2 — scoring sémantique BGE-M3)
# ─────────────────────────────────────────────────────────────────────────────
class OpenQuestion(Base):
    __tablename__ = "open_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    domaine         = Column(String(80), nullable=False, index=True)
    competence_esco = Column(String(150), nullable=True)
    job_offer_id    = Column(UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), nullable=True, index=True)
    question        = Column(Text, nullable=False)

    # Réponses de référence (3 niveaux) + leurs embeddings BGE-M3 pré-calculés.
    # Embeddings stockés en JSON (liste de floats) → cosinus calculé en Python.
    ref_expert  = Column(Text, nullable=False)
    ref_correct = Column(Text, nullable=False)
    ref_faible  = Column(Text, nullable=False)
    emb_expert  = Column(JSON, nullable=True)
    emb_correct = Column(JSON, nullable=True)
    emb_faible  = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<OpenQuestion {self.domaine} {self.competence_esco}>"


# ─────────────────────────────────────────────────────────────────────────────
# Résultat "Reality Gap" (Module 3 — écart déclaré vs démontré)
# ─────────────────────────────────────────────────────────────────────────────
class RealityGapResult(Base):
    __tablename__ = "reality_gap_results"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_offer_id = Column(UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id   = Column(UUID(as_uuid=True), ForeignKey("assessment_sessions.id", ondelete="SET NULL"), nullable=True)

    reality_gap_score  = Column(Float, nullable=False)   # 0-1 (moyenne pondérée des écarts)
    fiabilite_cv       = Column(Float, nullable=False)   # 0-100 (= 100 - gap*100)
    score_final_ajuste = Column(Float, nullable=True)    # matching_score * (0.7 + 0.3*fiab/100)

    # Détail par compétence : [{competence, niveau_declare, niveau_demontre, gap, poids}]
    details      = Column(JSON, nullable=True)
    niveau_label = Column(String(30), nullable=True)     # "fiable" | "a_verifier" | "ecart_important"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<RealityGapResult gap={self.reality_gap_score} fiab={self.fiabilite_cv}>"
