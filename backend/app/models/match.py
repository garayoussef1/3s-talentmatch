from sqlalchemy import Column, Float, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class MatchStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    accepted = "accepted"
    rejected = "rejected"


class Match(Base):
    """Table matches — résultats du matching CV ↔ offre d'emploi."""

    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_offer_id = Column(UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), nullable=False, index=True)

    score = Column(Float, nullable=False)             # Score de 0.0 à 1.0
    details = Column(Text, nullable=True)             # Explication du score (JSON string)
    status = Column(SAEnum(MatchStatus), default=MatchStatus.pending, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    candidate = relationship("Candidate", back_populates="matches")
    job_offer = relationship("JobOffer", back_populates="matches")

    def __repr__(self):
        return f"<Match score={self.score} status={self.status}>"
