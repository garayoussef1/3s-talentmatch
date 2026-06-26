"""
Modèles — Entretien IA conversationnel.

Un Interview est lancé pour un candidat sélectionné sur une offre. Il contient
une série de questions (InterviewQuestion) générées par l'IA, les réponses du
candidat (InterviewAnswer) avec leur analyse, et un rapport final
(InterviewReport) destiné au recruteur pour l'aider à décider.

Méthodologie : ESCO + STAR + CBI + Competency-Based Assessment.
"""
from sqlalchemy import (
    Column, Float, Integer, DateTime, ForeignKey, Text, String,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class InterviewStatus(str, enum.Enum):
    created     = "created"       # entretien initialisé, questions générées
    in_progress = "in_progress"   # le candidat répond
    completed   = "completed"     # terminé, rapport généré
    abandoned   = "abandoned"     # interrompu


class InterviewPhase(str, enum.Enum):
    profile     = "profile"       # Phase 1 — validation du profil
    technical   = "technical"     # Phase 2 — compétences techniques
    situational = "situational"   # Phase 3 — mises en situation
    soft_skills = "soft_skills"   # Phase 4 — soft skills (STAR)
    motivation  = "motivation"    # Phase 5 — motivation & fit
    closing     = "closing"       # Phase 6 — clôture


class Recommendation(str, enum.Enum):
    recruit  = "recruit"          # Recruter
    hesitate = "hesitate"         # Hésiter / approfondir
    reject   = "reject"           # Rejeter


# ─────────────────────────────────────────────────────────────────────────────
# Interview — un entretien
# ─────────────────────────────────────────────────────────────────────────────
class Interview(Base):
    __tablename__ = "interviews"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_offer_id = Column(UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), nullable=False, index=True)

    status  = Column(SAEnum(InterviewStatus), default=InterviewStatus.created, nullable=False)
    domaine = Column(String(100), nullable=True)        # domaine métier détecté (IT, Finance…)
    langue  = Column(String(10), default="fr", nullable=True)

    # Renseignés à la clôture
    global_score   = Column(Float, nullable=True)        # 0–100
    recommendation = Column(SAEnum(Recommendation), nullable=True)

    # Modèle LLM utilisé (traçabilité)
    llm_model = Column(String(80), nullable=True)        # ex: "llama-3.3-70b" / "mistral"

    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    started_at   = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relations internes au module entretien
    questions = relationship("InterviewQuestion", back_populates="interview",
                             cascade="all, delete-orphan", order_by="InterviewQuestion.order_index")
    answers   = relationship("InterviewAnswer", back_populates="interview",
                             cascade="all, delete-orphan")
    report    = relationship("InterviewReport", back_populates="interview",
                             uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Interview status={self.status} score={self.global_score}>"


# ─────────────────────────────────────────────────────────────────────────────
# InterviewQuestion — une question générée par l'IA
# ─────────────────────────────────────────────────────────────────────────────
class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)

    order_index = Column(Integer, nullable=False)        # ordre dans l'entretien (0..N)
    phase       = Column(SAEnum(InterviewPhase), nullable=False)
    question_text = Column(Text, nullable=False)

    target_competence = Column(String(150), nullable=True)  # compétence évaluée (ESCO)
    intent            = Column(String(255), nullable=True)  # ce que la question cherche à évaluer

    # Métadonnées de génération (JSON string) : cv_reference, green_flag_keywords,
    # red_flag_indicators, context_hint — réutilisées pour scorer la réponse.
    meta = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interview = relationship("Interview", back_populates="questions")
    answer    = relationship("InterviewAnswer", back_populates="question",
                             uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Q[{self.order_index}] {self.phase} {self.question_text[:40]!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# InterviewAnswer — réponse du candidat + analyse IA
# ─────────────────────────────────────────────────────────────────────────────
class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id  = Column(UUID(as_uuid=True), ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False, index=True)

    answer_text = Column(Text, nullable=True)

    # Analyse multi-critères (JSON string) — calculée par le code + le LLM.
    # Ex: {"contenu_technique": 0.8, "structure": 0.6, "coherence_cv": 0.9,
    #      "specificite": 0.7, "communication": 0.8}
    analysis = Column(Text, nullable=True)
    score    = Column(Float, nullable=True)              # score pondéré de la réponse (0–1)

    # Signaux détectés (JSON string) — ex: {"green": [...], "red": [...], "yellow": [...]}
    flags = Column(Text, nullable=True)

    # Sécurité : flag si tentative d'injection de prompt détectée
    injection_detected = Column(Integer, default=0, nullable=False)  # 0/1

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interview = relationship("Interview", back_populates="answers")
    question  = relationship("InterviewQuestion", back_populates="answer")

    def __repr__(self):
        return f"<Answer score={self.score}>"


# ─────────────────────────────────────────────────────────────────────────────
# InterviewReport — rapport final pour le recruteur
# ─────────────────────────────────────────────────────────────────────────────
class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    global_score   = Column(Float, nullable=False)        # 0–100
    recommendation = Column(SAEnum(Recommendation), nullable=False)

    summary = Column(Text, nullable=True)                 # synthèse exécutive (rédigée par le LLM)

    # Sections structurées (JSON string)
    validated_competences = Column(Text, nullable=True)   # validées / partielles / non validées
    soft_skills           = Column(Text, nullable=True)   # soft skills détectés + citations
    cross_check           = Column(Text, nullable=True)   # écarts CV vs entretien (différenciant)
    next_steps            = Column(Text, nullable=True)   # prochaines étapes actionnables
    full_payload          = Column(Text, nullable=True)   # rapport complet structuré (JSON)

    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    interview = relationship("Interview", back_populates="report")

    def __repr__(self):
        return f"<Report score={self.global_score} reco={self.recommendation}>"
