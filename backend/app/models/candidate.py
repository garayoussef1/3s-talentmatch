from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Candidate(Base):
    """Table candidates — stocke le profil extrait de chaque CV."""

    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(String(36), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)

    # Informations personnelles extraites
    nom = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    telephone = Column(String(50), nullable=True)
    linkedin = Column(String(255), nullable=True)
    github = Column(String(255), nullable=True)

    # Données structurées complètes (JSON brut du parser NLP)
    parsed_data = Column(JSON, nullable=True)

    # Texte brut extrait
    raw_text = Column(Text, nullable=True)

    # Méthode d'extraction utilisée (pypdf, ocr, docx)
    extraction_method = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    cv_documents = relationship("CVDocument", back_populates="candidate", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="candidate", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Candidate cv_id={self.cv_id} nom={self.nom}>"
