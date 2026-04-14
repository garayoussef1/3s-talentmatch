"""
Routes d'authentification — inscription, connexion, vérification email,
reset mot de passe, OAuth Google/LinkedIn.
"""

import os
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    UserResponse, OAuthCallbackRequest,
    VerifyEmailRequest, ResendCodeRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    AdminCreateRecruiterRequest,
)
from app.services.auth_service import (
    get_user_by_email, create_user, authenticate_user,
    user_to_token_response, google_oauth_callback, linkedin_oauth_callback,
    GOOGLE_CLIENT_ID, LINKEDIN_CLIENT_ID,
    send_verification_code, verify_email_code,
    send_reset_code, verify_reset_code_and_change_password,
)
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserRole, AuthProvider

logger = logging.getLogger(__name__)

router = APIRouter()

# ══════════════════════════════════════════════════════════════
# Inscription classique
# ══════════════════════════════════════════════════════════════

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Créer un nouveau compte (email + mot de passe). Envoie un code de vérification."""
    existing = get_user_by_email(db, req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà",
        )

    # Sécurité: l'inscription publique ne doit pas permettre de choisir un rôle privilégié.
    # Même si le frontend envoie un rôle, on refuse recruteur/admin.
    if getattr(req, "role", None) is not None and getattr(req.role, "value", None) != "candidat":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inscription recruteur/admin interdite. Contactez un administrateur.",
        )

    user = create_user(
        db,
        nom=req.nom,
        prenom=req.prenom,
        email=req.email,
        password=req.password,
        role=UserRole.candidat,
    )
    # Envoyer le code de vérification email
    send_verification_code(db, user)
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
    # Si email non vérifié, renvoyer quand même le token
    # mais le frontend redirigera vers la page de vérification
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
        is_email_verified=current_user.is_email_verified,
    )


# ══════════════════════════════════════════════════════════════
# Vérification email
# ══════════════════════════════════════════════════════════════

@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Vérifie le code OTP envoyé par email."""
    if current_user.is_email_verified:
        return {"message": "Email déjà vérifié", "verified": True}

    if not verify_email_code(db, current_user, req.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code invalide ou expiré",
        )
    return {"message": "Email vérifié avec succès !", "verified": True}


@router.post("/resend-code")
def resend_code(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Renvoie un nouveau code de vérification par email."""
    if current_user.is_email_verified:
        return {"message": "Email déjà vérifié"}

    send_verification_code(db, current_user)
    return {"message": "Nouveau code envoyé à votre adresse email"}


# ══════════════════════════════════════════════════════════════
# Mot de passe oublié
# ══════════════════════════════════════════════════════════════

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Envoie un code de reset par email (pas besoin d'être connecté)."""
    user = get_user_by_email(db, req.email)
    if not user:
        # On retourne toujours 200 pour ne pas révéler si l'email existe
        return {"message": "Si un compte existe avec cet email, un code de réinitialisation a été envoyé."}
    if user.auth_provider != AuthProvider.local:
        return {"message": "Ce compte utilise l'authentification OAuth. Connectez-vous via Google ou LinkedIn."}

    send_reset_code(db, user)
    return {"message": "Si un compte existe avec cet email, un code de réinitialisation a été envoyé."}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Réinitialise le mot de passe avec le code reçu par email."""
    user = get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")

    if not verify_reset_code_and_change_password(db, user, req.code, req.new_password):
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")

    return {"message": "Mot de passe réinitialisé avec succès. Vous pouvez vous connecter."}


# ══════════════════════════════════════════════════════════════
# Administration (admin-only)
# ══════════════════════════════════════════════════════════════


@router.post(
    "/admin/create-recruteur",
    response_model=UserResponse,
    status_code=201,
    summary="Créer un compte recruteur (admin uniquement)",
)
def admin_create_recruteur(
    req: AdminCreateRecruiterRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Crée un compte recruteur via backoffice/Swagger.

    - Accès: admin uniquement (JWT Bearer)
    - Le compte est activé et marqué email-vérifié pour éviter le blocage OTP en local.
    """

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
        role=UserRole.recruteur,
    )

    # Backoffice: on rend le compte utilisable immédiatement
    user.is_active = True
    user.is_email_verified = True
    user.verification_code = None
    user.verification_code_expires = None
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=str(user.id),
        nom=user.nom,
        prenom=user.prenom,
        email=user.email,
        role=user.role.value,
        auth_provider=user.auth_provider.value if user.auth_provider else "local",
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
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
    if not GOOGLE_CLIENT_ID or not os.getenv("GOOGLE_CLIENT_SECRET", ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth non configuré (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)",
        )
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
    if not LINKEDIN_CLIENT_ID or not os.getenv("LINKEDIN_CLIENT_SECRET", ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LinkedIn OAuth non configuré (LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET)",
        )
    redirect_uri = req.redirect_uri or os.getenv(
        "LINKEDIN_REDIRECT_URI", "http://localhost:3000/auth/callback/linkedin"
    )
    try:
        return await linkedin_oauth_callback(req.code, redirect_uri, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
