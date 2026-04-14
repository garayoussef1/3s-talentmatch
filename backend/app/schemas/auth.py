"""Schémas Pydantic pour l'authentification."""

from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing import Optional, Annotated
from enum import Enum


def _validate_email_allow_test_domains(value: str) -> str:
    """Valide un email sans rejeter les domaines "special-use" (ex: .test).

    Pydantic/EmailStr s'appuie sur `email-validator` qui, par défaut, rejette les
    domaines réservés. En dev, on utilise souvent `@local.test`.
    """

    if value is None:
        raise ValueError("email requis")

    raw = str(value).strip()

    # Validation minimale + allowlist dev pour domaines "special-use".
    # Objectif: permettre admin@local.test / user@localhost en dev.
    if "@" not in raw:
        raise ValueError("email invalide")
    local, _, domain = raw.partition("@")
    local = local.strip()
    domain = domain.strip().lower()
    if not local or not domain:
        raise ValueError("email invalide")

    dev_allowed_domains = {
        "localhost",
    }
    dev_allowed_suffixes = (".test", ".local")

    try:
        from email_validator import validate_email
    except Exception:
        # Fallback minimal si email-validator n'est pas dispo.
        if domain in dev_allowed_domains or domain.endswith(dev_allowed_suffixes):
            return f"{local}@{domain}"
        if "." not in domain:
            raise ValueError("email invalide")
        return f"{local}@{domain}"

    try:
        result = validate_email(
            raw,
            check_deliverability=False,
            test_environment=True,
        )
        return result.normalized
    except Exception:
        # Certains environnements/version d'email-validator rejettent quand même
        # les domaines réservés (.test). On autorise explicitement en dev.
        if domain in dev_allowed_domains or domain.endswith(dev_allowed_suffixes):
            return f"{local}@{domain}"
        raise


DevEmailStr = Annotated[str, BeforeValidator(_validate_email_allow_test_domains)]


class UserRole(str, Enum):
    recruteur = "recruteur"
    admin = "admin"
    candidat = "candidat"


# ── Inscription ──────────────────────────────────────────────
class RegisterRequest(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    email: DevEmailStr
    password: str = Field(..., min_length=6, max_length=128)
    # Sécurité/produit : l'inscription publique ne doit créer que des candidats.
    # Les recruteurs/admins doivent être créés par un admin (seed / backoffice).
    role: UserRole = UserRole.candidat


# ── Connexion classique ──────────────────────────────────────
class LoginRequest(BaseModel):
    email: DevEmailStr
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
    is_email_verified: bool = False

    class Config:
        from_attributes = True


# ── Vérification email ──────────────────────────────────────
class VerifyEmailRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class ResendCodeRequest(BaseModel):
    pass  # pas de body nécessaire, on utilise le token JWT


# ── Mot de passe oublié ─────────────────────────────────────
class ForgotPasswordRequest(BaseModel):
    email: DevEmailStr


class ResetPasswordRequest(BaseModel):
    email: DevEmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6, max_length=128)


# ── Administration ───────────────────────────────────────────
class AdminCreateRecruiterRequest(BaseModel):
    """Création d'un compte recruteur par un admin (backoffice / Swagger)."""

    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    email: DevEmailStr
    password: str = Field(..., min_length=6, max_length=128)


# ── OAuth ────────────────────────────────────────────────────
class OAuthCallbackRequest(BaseModel):
    """Code d'autorisation reçu du frontend après le redirect OAuth."""
    code: str
    redirect_uri: Optional[str] = None


# Résolution forward ref
TokenResponse.model_rebuild()
