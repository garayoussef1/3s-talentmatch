from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    recruteur = "recruteur"
    admin = "admin"
    candidat = "candidat"


class AuthProvider(str, enum.Enum):
    local = "local"
    google = "google"
    linkedin = "linkedin"


class User(Base):
    """Table users — recruteurs, admins et candidats."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # nullable pour OAuth
    role = Column(SAEnum(UserRole, name="userrole", create_constraint=False),
                  default=UserRole.recruteur, nullable=False)
    is_active = Column(Boolean, default=True)

    # OAuth
    auth_provider = Column(
        SAEnum(AuthProvider, name="authprovider", create_constraint=False),
        default=AuthProvider.local, nullable=False,
    )
    oauth_id = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User email={self.email} role={self.role} provider={self.auth_provider}>"
