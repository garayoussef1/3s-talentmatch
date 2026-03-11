"""
Dependency FastAPI pour récupérer l'utilisateur courant à partir du JWT.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import decode_access_token, get_user_by_id
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extrait et valide le JWT, retourne l'utilisateur correspondant."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Vérifie que l'utilisateur courant est admin."""
    if user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return user


async def get_current_recruteur_or_admin(user: User = Depends(get_current_user)) -> User:
    """Vérifie que l'utilisateur courant est recruteur ou admin (pas candidat)."""
    if user.role.value not in ("recruteur", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux recruteurs et administrateurs",
        )
    return user
