"""
Service d'authentification — hashing, JWT, OAuth Google/LinkedIn, vérification email.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import httpx

from app.models.user import User, UserRole, AuthProvider
from app.services.email_service import (
    generate_otp, send_verification_email, send_password_reset_email,
    VERIFICATION_CODE_EXPIRE_MINUTES,
)

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# LinkedIn OAuth
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")

# ── Password hashing ────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── CRUD utilisateur ─────────────────────────────────────────
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    *,
    nom: str,
    prenom: str,
    email: str,
    password: Optional[str] = None,
    role: UserRole = UserRole.recruteur,
    auth_provider: AuthProvider = AuthProvider.local,
    oauth_id: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> User:
    user = User(
        nom=nom,
        prenom=prenom,
        email=email,
        hashed_password=hash_password(password) if password else None,
        role=role,
        auth_provider=auth_provider,
        oauth_id=oauth_id,
        avatar_url=avatar_url,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Utilisateur créé : %s (%s via %s)", email, role, auth_provider)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def user_to_token_response(user: User) -> dict:
    """Crée un TokenResponse dict à partir d'un User."""
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "nom": user.nom,
            "prenom": user.prenom,
            "email": user.email,
            "role": user.role.value,
            "auth_provider": user.auth_provider.value if user.auth_provider else "local",
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "is_email_verified": user.is_email_verified,
        },
    }


# ── Vérification email ──────────────────────────────────────
def send_verification_code(db: Session, user: User) -> bool:
    """Génère un code OTP et l'envoie par email. Retourne True si envoyé."""
    code = generate_otp()
    user.verification_code = code
    user.verification_code_expires = datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_EXPIRE_MINUTES
    )
    db.commit()
    logger.info("Code de vérification généré pour %s : %s", user.email, code)
    sent = send_verification_email(user.email, user.prenom, code)
    if not sent:
        # Fallback : le code est quand même en BDD, on le log pour le dev
        logger.warning(
            "Email non envoyé — code de vérification pour %s : %s (vérifiez SMTP_PASSWORD)",
            user.email, code,
        )
    return sent


def verify_email_code(db: Session, user: User, code: str) -> bool:
    """Vérifie le code OTP. Retourne True si le code est valide."""
    if not user.verification_code or not user.verification_code_expires:
        return False
    if datetime.now(timezone.utc) > user.verification_code_expires:
        return False
    if user.verification_code != code:
        return False
    # Succès → marquer comme vérifié
    user.is_email_verified = True
    user.verification_code = None
    user.verification_code_expires = None
    db.commit()
    logger.info("Email vérifié avec succès pour %s", user.email)
    return True


# ── Reset mot de passe ───────────────────────────────────────
def send_reset_code(db: Session, user: User) -> bool:
    """Génère un code de reset et l'envoie par email."""
    code = generate_otp()
    user.reset_code = code
    user.reset_code_expires = datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_EXPIRE_MINUTES
    )
    db.commit()
    logger.info("Code de reset généré pour %s : %s", user.email, code)
    sent = send_password_reset_email(user.email, user.prenom, code)
    if not sent:
        logger.warning(
            "Email non envoyé — code de reset pour %s : %s (vérifiez SMTP_PASSWORD)",
            user.email, code,
        )
    return sent


def verify_reset_code_and_change_password(
    db: Session, user: User, code: str, new_password: str
) -> bool:
    """Vérifie le code de reset et change le mot de passe. Retourne True si OK."""
    if not user.reset_code or not user.reset_code_expires:
        return False
    if datetime.now(timezone.utc) > user.reset_code_expires:
        return False
    if user.reset_code != code:
        return False
    # Succès → changer le mot de passe
    user.hashed_password = hash_password(new_password)
    user.reset_code = None
    user.reset_code_expires = None
    db.commit()
    logger.info("Mot de passe réinitialisé pour %s", user.email)
    return True


# ── OAuth Google ─────────────────────────────────────────────
async def google_oauth_callback(code: str, redirect_uri: str, db: Session) -> dict:
    """Échange le code Google contre un token, récupère le profil, crée/connecte l'utilisateur."""
    # 1. Échanger le code contre un access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s", token_resp.text)
            raise ValueError(f"Google OAuth error: {token_resp.text}")
        token_data = token_resp.json()

        # 2. Récupérer le profil utilisateur
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise ValueError("Failed to fetch Google user info")
        profile = userinfo_resp.json()

    # 3. Trouver ou créer l'utilisateur
    email = profile.get("email", "")
    user = get_user_by_email(db, email)
    if not user:
        user = create_user(
            db,
            nom=profile.get("family_name", ""),
            prenom=profile.get("given_name", ""),
            email=email,
            auth_provider=AuthProvider.google,
            oauth_id=profile.get("id", ""),
            avatar_url=profile.get("picture", ""),
        )
        # OAuth = email déjà vérifié par Google
        user.is_email_verified = True
        db.commit()
    else:
        # Mettre à jour l'avatar si nécessaire
        if profile.get("picture") and not user.avatar_url:
            user.avatar_url = profile["picture"]
        if not user.is_email_verified:
            user.is_email_verified = True
        db.commit()

    return user_to_token_response(user)


# ── OAuth LinkedIn ───────────────────────────────────────────
async def linkedin_oauth_callback(code: str, redirect_uri: str, db: Session) -> dict:
    """Échange le code LinkedIn contre un token, récupère le profil, crée/connecte l'utilisateur."""
    async with httpx.AsyncClient() as client:
        # 1. Échanger le code
        token_resp = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": LINKEDIN_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            logger.error("LinkedIn token exchange failed: %s", token_resp.text)
            raise ValueError(f"LinkedIn OAuth error: {token_resp.text}")
        access_token = token_resp.json().get("access_token")

        # 2. Récupérer le profil (OpenID Connect userinfo)
        profile_resp = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code != 200:
            raise ValueError("Failed to fetch LinkedIn user info")
        profile = profile_resp.json()

    email = profile.get("email", "")
    user = get_user_by_email(db, email)
    if not user:
        user = create_user(
            db,
            nom=profile.get("family_name", ""),
            prenom=profile.get("given_name", ""),
            email=email,
            auth_provider=AuthProvider.linkedin,
            oauth_id=profile.get("sub", ""),
            avatar_url=profile.get("picture", ""),
        )
        # OAuth = email déjà vérifié par LinkedIn
        user.is_email_verified = True
        db.commit()
    else:
        if profile.get("picture") and not user.avatar_url:
            user.avatar_url = profile["picture"]
        if not user.is_email_verified:
            user.is_email_verified = True
        db.commit()

    return user_to_token_response(user)
