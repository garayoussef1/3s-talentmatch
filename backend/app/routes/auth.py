"""
Routes d'authentification — inscription, connexion, OAuth Google/LinkedIn.
"""

import os
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    UserResponse, OAuthCallbackRequest,
)
from app.services.auth_service import (
    get_user_by_email, create_user, authenticate_user,
    user_to_token_response, google_oauth_callback, linkedin_oauth_callback,
    GOOGLE_CLIENT_ID, LINKEDIN_CLIENT_ID,
)
from app.dependencies import get_current_user
from app.models.user import User, UserRole, AuthProvider

logger = logging.getLogger(__name__)

router = APIRouter()

# ══════════════════════════════════════════════════════════════
# Inscription classique
# ══════════════════════════════════════════════════════════════

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Créer un nouveau compte (email + mot de passe)."""
    existing = get_user_by_email(db, req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà",
        )
    user = create_user(
        db,
        nom=req.nom,
        prenom=req.prenom,
        email=req.email,
        password=req.password,
        role=UserRole(req.role.value),
    )
    return user_to_token_response(user)


# ══════════════════════════════════════════════════════════════
# Connexion classique
# ══════════════════════════════════════════════════════════════

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Connexion par email + mot de passe."""
    user = authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé",
        )
    return user_to_token_response(user)


# ══════════════════════════════════════════════════════════════
# Utilisateur courant
# ══════════════════════════════════════════════════════════════

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retourne le profil de l'utilisateur connecté."""
    return UserResponse(
        id=str(current_user.id),
        nom=current_user.nom,
        prenom=current_user.prenom,
        email=current_user.email,
        role=current_user.role.value,
        auth_provider=current_user.auth_provider.value if current_user.auth_provider else "local",
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
    )


# ══════════════════════════════════════════════════════════════
# OAuth Config (pour le frontend)
# ══════════════════════════════════════════════════════════════

@router.get("/oauth/config")
def oauth_config():
    """Retourne les client IDs OAuth pour le frontend (pas les secrets)."""
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "linkedin_client_id": LINKEDIN_CLIENT_ID,
    }


# ══════════════════════════════════════════════════════════════
# OAuth Google
# ══════════════════════════════════════════════════════════════

@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(req: OAuthCallbackRequest, db: Session = Depends(get_db)):
    """Échange le code d'autorisation Google contre un JWT."""
    redirect_uri = req.redirect_uri or os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback/google"
    )
    try:
        return await google_oauth_callback(req.code, redirect_uri, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════
# OAuth LinkedIn
# ══════════════════════════════════════════════════════════════

@router.post("/oauth/linkedin", response_model=TokenResponse)
async def oauth_linkedin(req: OAuthCallbackRequest, db: Session = Depends(get_db)):
    """Échange le code d'autorisation LinkedIn contre un JWT."""
    redirect_uri = req.redirect_uri or os.getenv(
        "LINKEDIN_REDIRECT_URI", "http://localhost:3000/auth/callback/linkedin"
    )
    try:
        return await linkedin_oauth_callback(req.code, redirect_uri, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
