from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


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
    description = Column(Text, nullable=True)
    competences_requises = Column(JSON, nullable=True)   # liste de compétences
    localisation = Column(String(255), nullable=True)
    type_contrat = Column(String(50), nullable=True)     # CDI, CDD, Stage...
    status = Column(SAEnum(JobStatus), default=JobStatus.active, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    recruiter = relationship("User")
    matches = relationship("Match", back_populates="job_offer")

    def __repr__(self):
        return f"<JobOffer titre={self.titre} status={self.status}>"
