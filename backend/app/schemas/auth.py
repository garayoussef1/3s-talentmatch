"""Schémas Pydantic pour l'authentification."""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum


class UserRole(str, Enum):
    recruteur = "recruteur"
    admin = "admin"
    candidat = "candidat"


# ── Inscription ──────────────────────────────────────────────
class RegisterRequest(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    role: UserRole = UserRole.recruteur


# ── Connexion classique ──────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Réponse token ────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


# ── Réponse utilisateur ──────────────────────────────────────
class UserResponse(BaseModel):
    id: str
    nom: str
    prenom: str
    email: str
    role: str
    auth_provider: str = "local"
    avatar_url: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


# ── OAuth ────────────────────────────────────────────────────
class OAuthCallbackRequest(BaseModel):
    """Code d'autorisation reçu du frontend après le redirect OAuth."""
    code: str
    redirect_uri: Optional[str] = None


# Résolution forward ref
TokenResponse.model_rebuild()
