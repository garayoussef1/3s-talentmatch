from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class CVStatus(str, enum.Enum):
    uploaded = "uploaded"
    extracted = "extracted"
    parsed = "parsed"
    error = "error"


class CVDocument(Base):
    """Table cv_documents — fichiers CV uploadés, liés à un candidat."""

    __tablename__ = "cv_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)

    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)   # pdf, docx, image
    extraction_method = Column(String(50), nullable=True)  # pypdf, ocr, docx
    raw_text = Column(Text, nullable=True)
    status = Column(SAEnum(CVStatus), default=CVStatus.uploaded, nullable=False)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relation vers Candidate
    candidate = relationship("Candidate", back_populates="cv_documents")

    def __repr__(self):
        return f"<CVDocument filename={self.filename} status={self.status}>"
