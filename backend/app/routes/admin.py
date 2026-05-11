import re
import uuid as _uuid
from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User, UserRole
from app.models.access_log import AccessLog
from app.models.candidate import Candidate, CandidatureStatus
from app.models.job_offer import JobOffer, JobStatus
from app.models.match import Match, MatchStatus
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


class AdminCandidateCreate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    competences: Optional[List[str]] = None   # liste de compétences saisies à la main
    note: Optional[str] = None                # texte libre (résumé du profil)
    offer_id: Optional[str] = None            # lier directement à une offre


@router.post("/admin/candidates", summary="Créer un candidat manuellement (admin)")
def admin_create_candidate(
    payload: AdminCandidateCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    cv_id = str(_uuid.uuid4())
    nom_complet = " ".join(filter(None, [payload.prenom, payload.nom])) or "Candidat"
    filename = f"manuel_{cv_id[:8]}.txt"

    # Construit un parsed_data minimal pour que le matching fonctionne
    parsed_data = {
        "identite": {"nom_complet": nom_complet},
        "contacts": {
            "email": payload.email or "",
            "telephone": payload.telephone or "",
            "linkedin": payload.linkedin or "",
            "github": payload.github or "",
        },
        "competences": [{"name": c, "category": "manuel"} for c in (payload.competences or [])],
        "ia_analyse": {"resume": payload.note or ""},
        "metadata": {"source": "admin_manual"},
    }

    raw_text = "\n".join(filter(None, [
        nom_complet,
        payload.email,
        payload.telephone,
        "Compétences : " + ", ".join(payload.competences or []) if payload.competences else None,
        payload.note,
    ]))

    candidate = Candidate(
        cv_id=cv_id,
        filename=filename,
        nom=nom_complet,
        email=payload.email,
        telephone=payload.telephone,
        linkedin=payload.linkedin,
        github=payload.github,
        parsed_data=parsed_data,
        raw_text=raw_text,
        extraction_method="manual",
        candidature_status=CandidatureStatus.en_attente,
        information_acknowledged=True,
    )
    db.add(candidate)
    db.flush()

    # Lier à une offre si fournie
    if payload.offer_id:
        offer = db.query(JobOffer).filter(
            JobOffer.id == payload.offer_id,
            JobOffer.status == JobStatus.active,
        ).first()
        if offer:
            match = Match(
                candidate_id=candidate.id,
                job_offer_id=offer.id,
                status=MatchStatus.pending,
            )
            db.add(match)

    db.commit()
    db.refresh(candidate)
    return {
        "success": True,
        "cv_id": cv_id,
        "nom": candidate.nom,
        "email": candidate.email,
        "message": f"Candidat « {nom_complet} » créé avec succès.",
    }


@router.get("/admin/access-logs", summary="Journal des accès RGPD (admin)")
def get_access_logs(
    action: Optional[str] = None,
    user_email: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    query = db.query(AccessLog)
    if action:
        query = query.filter(AccessLog.action == action)
    if user_email:
        query = query.filter(AccessLog.user_email.ilike(f"%{user_email}%"))

    total = query.count()
    logs = query.order_by(AccessLog.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "logs": [
            {
                "id": str(log.id),
                "user_email": log.user_email,
                "user_role": log.user_role,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


@router.post(
    "/admin/sync-matches",
    summary="Lier tous les CVs existants aux offres actives (migration admin)",
)
def sync_existing_candidates_to_offers(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Crée des entrées Match (score=0, pending) pour chaque candidat
    qui n'est pas encore lié à chaque offre active.
    Permet d'avoir un candidate_count correct sur la page des offres.
    """
    candidates   = db.query(Candidate).all()
    active_offers = db.query(JobOffer).filter(JobOffer.status == JobStatus.active).all()

    created = 0
    for candidate in candidates:
        for offer in active_offers:
            exists = (
                db.query(Match)
                .filter(Match.candidate_id == candidate.id, Match.job_offer_id == offer.id)
                .first()
            )
            if not exists:
                db.add(Match(
                    candidate_id=candidate.id,
                    job_offer_id=offer.id,
                    score=0.0,
                    details=None,
                    status=MatchStatus.pending,
                ))
                created += 1

    db.commit()
    return {
        "success": True,
        "candidates": len(candidates),
        "offers": len(active_offers),
        "matches_created": created,
        "message": f"{created} lien(s) créé(s) entre {len(candidates)} candidat(s) et {len(active_offers)} offre(s) active(s).",
    }
