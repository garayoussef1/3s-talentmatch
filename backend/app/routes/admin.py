import re
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User, UserRole
from app.schemas.admin import AdminUsersListResponse, AdminUserDetail, AdminUserUpdateRequest
from app.services.auth_service import get_user_by_id, send_reset_code

router = APIRouter()


def _user_to_item(user: User) -> dict:
    return {
        "id": str(user.id),
        "nom": user.nom,
        "prenom": user.prenom,
        "email": user.email,
        "role": user.role.value,
        "auth_provider": user.auth_provider.value if user.auth_provider else "local",
        "is_active": bool(user.is_active),
        "is_email_verified": bool(user.is_email_verified),
    }


@router.get("/admin/users", response_model=AdminUsersListResponse, summary="Lister les utilisateurs (admin)")
def list_users(
    q: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    query = db.query(User)
    if role:
        try:
            query = query.filter(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(status_code=400, detail="Rôle invalide")
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (User.email.ilike(like))
            | (User.nom.ilike(like))
            | (User.prenom.ilike(like))
        )

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "users": [_user_to_item(u) for u in users],
    }


@router.get("/admin/users/{user_id}", response_model=AdminUserDetail, summary="Détail utilisateur (admin)")
def get_user_detail(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return _user_to_item(user)


@router.patch("/admin/users/{user_id}", response_model=AdminUserDetail, summary="Mettre à jour un utilisateur (admin)")
def update_user(
    user_id: UUID,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return _user_to_item(user)


@router.delete("/admin/users/{user_id}", summary="Supprimer un utilisateur (admin)")
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    db.delete(user)
    db.commit()
    return {"success": True, "message": "Utilisateur supprimé"}


@router.post("/admin/users/{user_id}/reset-password", summary="Forcer reset mot de passe (admin)")
def admin_reset_password(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    send_reset_code(db, user)
    return {"success": True, "message": "Code de reset envoyé"}
