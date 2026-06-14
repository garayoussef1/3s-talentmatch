from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, ForeignKey, Enum as SAEnum, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base

# Table de jonction offre ↔ recruteur (accès)
offer_recruiters = Table(
    "offer_recruiters",
    Base.metadata,
    Column("offer_id", UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id",  UUID(as_uuid=True), ForeignKey("users.id",      ondelete="CASCADE"), primary_key=True),
)


class JobStatus(str, enum.Enum):
    active = "active"
    closed = "closed"
    draft = "draft"


class JobOffer(Base):
    """Table job_offers — offres d'emploi publiées par les recruteurs."""

    __tablename__ = "job_offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    titre = Column(String(255), nullable=False)
    entreprise = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    competences_requises  = Column(JSON, nullable=True)
    competences_appreciees = Column(JSON, nullable=True)
    localisation = Column(String(255), nullable=True)
    type_contrat = Column(String(50), nullable=True)     # CDI, CDD, Stage...
    nb_postes    = Column(Integer, default=1, nullable=False)
    experience_requise = Column(Integer, nullable=True)  # années minimum requises
    formation_requise_niveau = Column(Integer, nullable=True)  # 0=non spécifié, 2=Bac+2, 3=Bac+3, 4=Bac+4, 5=Bac+5, 8=Bac+8
    domaine_metier   = Column(String(100), nullable=True)   # ex: "IT", "Santé", "Finance"
    niveau_seniorite = Column(String(50),  nullable=True)   # ex: "Junior", "Senior", "Stage"
    status = Column(SAEnum(JobStatus), default=JobStatus.active, nullable=False)
    date_limite = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    recruiter = relationship("User", foreign_keys=[recruiter_id])
    assigned_recruiters = relationship("User", secondary="offer_recruiters", lazy="selectin")
    matches = relationship(
        "Match",
        back_populates="job_offer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<JobOffer titre={self.titre} status={self.status}>"
