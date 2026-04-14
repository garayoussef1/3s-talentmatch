from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_recruteur_or_admin, get_current_user
from app.models.job_offer import JobOffer, JobStatus
from app.models.match import Match, MatchStatus
from app.models.user import User
from app.schemas.job_offers import (
    JobOfferCreate,
    JobOfferUpdate,
    JobOfferItem,
    JobOfferListResponse,
    ApplicationListResponse,
)

router = APIRouter()


def _to_item(offer: JobOffer) -> dict:
    return {
        "id": str(offer.id),
        "recruiter_id": str(offer.recruiter_id) if offer.recruiter_id else None,
        "titre": offer.titre,
        "description": offer.description,
        "competences_requises": offer.competences_requises,
        "localisation": offer.localisation,
        "type_contrat": offer.type_contrat,
        "status": offer.status.value if offer.status else "active",
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
    }


@router.get("/offers", response_model=JobOfferListResponse, summary="Lister les offres (recruteur/admin)")
def list_offers(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    query = db.query(JobOffer)
    if current_user.role.value != "admin":
        query = query.filter(JobOffer.recruiter_id == current_user.id)

    total = query.count()
    offers = query.order_by(JobOffer.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "offers": [_to_item(o) for o in offers],
    }


@router.get("/offers/public", response_model=JobOfferListResponse, summary="Lister les offres actives (candidat)")
def list_public_offers(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(JobOffer).filter(JobOffer.status == JobStatus.active)
    total = query.count()
    offers = query.order_by(JobOffer.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "offers": [_to_item(o) for o in offers],
    }


@router.post("/offers", response_model=JobOfferItem, summary="Créer une offre (recruteur/admin)")
def create_offer(
    payload: JobOfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    status = payload.status or "active"
    if status not in {s.value for s in JobStatus}:
        raise HTTPException(status_code=400, detail="Statut invalide")

    offer = JobOffer(
        recruiter_id=current_user.id,
        titre=payload.titre,
        description=payload.description,
        competences_requises=payload.competences_requises or [],
        localisation=payload.localisation,
        type_contrat=payload.type_contrat,
        status=JobStatus(status),
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return _to_item(offer)


@router.patch("/offers/{offer_id}", response_model=JobOfferItem, summary="Mettre à jour une offre (recruteur/admin)")
def update_offer(
    offer_id: UUID,
    payload: JobOfferUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    if current_user.role.value != "admin" and offer.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")

    if payload.titre is not None:
        offer.titre = payload.titre
    if payload.description is not None:
        offer.description = payload.description
    if payload.competences_requises is not None:
        offer.competences_requises = payload.competences_requises
    if payload.localisation is not None:
        offer.localisation = payload.localisation
    if payload.type_contrat is not None:
        offer.type_contrat = payload.type_contrat
    if payload.status is not None:
        if payload.status not in {s.value for s in JobStatus}:
            raise HTTPException(status_code=400, detail="Statut invalide")
        offer.status = JobStatus(payload.status)

    db.commit()
    db.refresh(offer)
    return _to_item(offer)


@router.delete("/offers/{offer_id}", summary="Supprimer une offre (recruteur/admin)")
def delete_offer(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    if current_user.role.value != "admin" and offer.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")

    # Supprime d'abord les candidatures/matchs liés pour éviter les erreurs FK
    # (utile si la contrainte ON DELETE CASCADE n'a pas été appliquée en base).
    try:
        db.query(Match).filter(Match.job_offer_id == offer_id).delete(synchronize_session=False)
        db.delete(offer)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Impossible de supprimer l'offre (dépendances en base).",
        )

    return {"success": True, "message": "Offre supprimée"}


@router.get(
    "/offers/{offer_id}/applications",
    response_model=ApplicationListResponse,
    summary="Lister les candidatures d'une offre (recruteur/admin)",
)
def list_offer_applications(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    if current_user.role.value != "admin" and offer.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")

    matches = (
        db.query(Match)
        .filter(Match.job_offer_id == offer_id)
        .order_by(Match.created_at.desc())
        .all()
    )
    return {
        "total": len(matches),
        "applications": [
            {
                "id": str(m.id),
                "cv_id": m.candidate.cv_id if m.candidate else "",
                "candidate_id": str(m.candidate_id),
                "offer_id": str(m.job_offer_id),
                "offer_title": offer.titre,
                "candidate_name": m.candidate.nom if m.candidate else None,
                "candidate_email": m.candidate.email if m.candidate else None,
                "status": m.status.value,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in matches
        ],
    }


@router.patch(
    "/offers/{offer_id}/applications/{application_id}",
    summary="Mettre a jour une candidature (recruteur/admin)",
)
def update_offer_application(
    offer_id: UUID,
    application_id: UUID,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    if current_user.role.value != "admin" and offer.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")

    match = db.query(Match).filter(Match.id == application_id, Match.job_offer_id == offer_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    try:
        match.status = MatchStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Statut invalide")

    db.commit()
    return {"success": True, "status": match.status.value}
