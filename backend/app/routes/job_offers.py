from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_recruteur_or_admin, get_current_user, get_current_admin
from app.models.job_offer import JobOffer, JobStatus, offer_recruiters
from app.models.match import Match, MatchStatus
from app.models.candidate import Candidate, CandidatureStatus
from app.models.user import User, UserRole
from app.schemas.job_offers import (
    JobOfferCreate,
    JobOfferUpdate,
    JobOfferItem,
    JobOfferListResponse,
    ApplicationListResponse,
)

router = APIRouter()


def _auto_close_expired(db: Session) -> None:
    """Ferme automatiquement les offres dont la date limite est dépassée."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(JobOffer)
        .filter(
            JobOffer.status == JobStatus.active,
            JobOffer.date_limite != None,
            JobOffer.date_limite < now,
        )
        .all()
    )
    if expired:
        for offer in expired:
            offer.status = JobStatus.closed
        db.commit()


def _to_item(offer: JobOffer, candidate_count: int = None) -> dict:
    count = candidate_count if candidate_count is not None else len(offer.matches or [])
    return {
        "id": str(offer.id),
        "recruiter_id": str(offer.recruiter_id) if offer.recruiter_id else None,
        "titre": offer.titre,
        "entreprise": offer.entreprise,
        "description": offer.description,
        "competences_requises":   offer.competences_requises,
        "competences_appreciees": offer.competences_appreciees,
        "localisation": offer.localisation,
        "type_contrat": offer.type_contrat,
        "nb_postes": offer.nb_postes or 1,
        "experience_requise": offer.experience_requise,
        "status": offer.status.value if offer.status else "active",
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
        "date_limite": offer.date_limite.isoformat() if offer.date_limite else None,
        "candidate_count": count,
        "assigned_recruiter_ids": [str(r.id) for r in (offer.assigned_recruiters or [])],
    }


class SelectionPayload(BaseModel):
    cv_ids: List[str]  # cv_id des candidats sélectionnés (max nb_postes)


@router.get("/offers", response_model=JobOfferListResponse, summary="Lister les offres (recruteur/admin)")
def list_offers(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    # Sous-requête : nombre de matchs par offre (= candidats)
    candidate_count_sq = (
        db.query(func.count(Match.id))
        .filter(Match.job_offer_id == JobOffer.id)
        .correlate(JobOffer)
        .scalar_subquery()
    )

    # Admin voit tout ; recruteur voit seulement les offres qui lui sont assignées
    if current_user.role == UserRole.admin:
        query = db.query(JobOffer, candidate_count_sq.label("cnt"))
    else:
        query = (
            db.query(JobOffer, candidate_count_sq.label("cnt"))
            .join(offer_recruiters, offer_recruiters.c.offer_id == JobOffer.id)
            .filter(offer_recruiters.c.user_id == current_user.id)
        )

    _auto_close_expired(db)
    total = query.count()
    rows = query.order_by(candidate_count_sq.desc()).offset(skip).limit(limit).all()
    total_pool = db.query(func.count(Candidate.id)).scalar() or 0
    return {
        "total": total,
        "total_pool": total_pool,
        "offers": [_to_item(o, cnt) for o, cnt in rows],
    }


@router.get("/offers/public", response_model=JobOfferListResponse, summary="Lister les offres actives (candidat)")
def list_public_offers(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _auto_close_expired(db)
    query = db.query(JobOffer).filter(JobOffer.status == JobStatus.active)
    total = query.count()
    offers = query.order_by(JobOffer.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "offers": [_to_item(o) for o in offers],
    }


@router.get(
    "/offers/public/{offer_id}",
    response_model=JobOfferItem,
    summary="Consulter une offre active (candidat)",
)
def get_public_offer(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offer = (
        db.query(JobOffer)
        .filter(JobOffer.id == offer_id, JobOffer.status == JobStatus.active)
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvee")
    return _to_item(offer)


@router.post("/offers", response_model=JobOfferItem, summary="Créer une offre (admin uniquement)")
def create_offer(
    payload: JobOfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
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
        nb_postes=max(1, payload.nb_postes or 1),
        status=JobStatus(status),
        date_limite=payload.date_limite,
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
    if payload.nb_postes is not None:
        offer.nb_postes = max(1, payload.nb_postes)
    if "date_limite" in payload.model_fields_set:
        offer.date_limite = payload.date_limite

    db.commit()
    db.refresh(offer)
    return _to_item(offer)


@router.get("/offers/{offer_id}/recruiters", summary="Recruteurs assignés à une offre (admin)")
def get_offer_recruiters(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    return {
        "offer_id": str(offer_id),
        "recruiters": [
            {"id": str(r.id), "nom": r.nom, "prenom": r.prenom, "email": r.email}
            for r in offer.assigned_recruiters
        ],
    }


class RecruiterAssignPayload(BaseModel):
    recruiter_ids: List[str]


@router.put("/offers/{offer_id}/recruiters", summary="Assigner des recruteurs à une offre (admin)")
def set_offer_recruiters(
    offer_id: UUID,
    payload: RecruiterAssignPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    recruiters = db.query(User).filter(
        User.id.in_(payload.recruiter_ids),
        User.role == UserRole.recruteur,
    ).all()

    offer.assigned_recruiters = recruiters
    db.commit()
    return {
        "offer_id": str(offer_id),
        "assigned": [str(r.id) for r in recruiters],
    }


@router.delete("/offers/{offer_id}", summary="Supprimer une offre (admin)")
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


@router.post(
    "/offers/{offer_id}/select",
    summary="Sélectionner les candidats retenus pour une offre (recruteur/admin)",
)
def select_candidates(
    offer_id: UUID,
    payload: SelectionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    nb_postes = offer.nb_postes or 1
    if len(payload.cv_ids) > nb_postes:
        raise HTTPException(
            status_code=400,
            detail=f"Cette offre a {nb_postes} poste(s) — vous avez sélectionné {len(payload.cv_ids)} candidat(s).",
        )

    # Tous les candidats matchés pour cette offre
    matches = (
        db.query(Match)
        .join(Candidate, Match.candidate_id == Candidate.id)
        .filter(Match.job_offer_id == offer_id)
        .all()
    )

    accepted_count = 0
    refused_count  = 0
    notifications_to_send = []  # (cand_user, candidate, new_status)

    for match in matches:
        candidate = db.query(Candidate).filter(Candidate.id == match.candidate_id).first()
        if not candidate:
            continue
        if candidate.cv_id in payload.cv_ids:
            candidate.candidature_status = CandidatureStatus.accepte
            match.status = MatchStatus.accepted
            accepted_count += 1
            new_status = "accepte"
        else:
            candidate.candidature_status = CandidatureStatus.refuse
            match.status = MatchStatus.rejected
            refused_count += 1
            new_status = "refuse"

        if candidate.user_id:
            cand_user = db.query(User).filter(User.id == candidate.user_id).first()
            if cand_user:
                notifications_to_send.append((cand_user, candidate, new_status))

    # Fermer l'offre si tous les postes sont pourvus
    if accepted_count >= nb_postes:
        offer.status = JobStatus.closed

    db.commit()

    # Envoyer notifications in-app + email (best-effort, après commit)
    try:
        from app.routes.notifications import create_notification
        from app.services.email_service import send_status_change_email
        for cand_user, candidate, new_status in notifications_to_send:
            cv_name = candidate.filename or candidate.nom or "votre CV"
            if new_status == "accepte":
                title = "Candidature acceptée ✓"
                message = f"Votre CV « {cv_name} » pour le poste « {offer.titre} » a été accepté."
            else:
                title = "Candidature refusée"
                message = f"Votre CV « {cv_name} » pour le poste « {offer.titre} » n'a pas été retenu."
            create_notification(db, cand_user.id, "status_change", title, message, link="/my-applications")
            if cand_user.email:
                send_status_change_email(
                    to_email=cand_user.email,
                    prenom=cand_user.prenom or cand_user.nom or "Candidat",
                    offer_title=offer.titre,
                    new_status=new_status,
                    cv_name=cv_name,
                )
        db.commit()
    except Exception:
        pass

    return {
        "success": True,
        "accepted": accepted_count,
        "refused": refused_count,
        "offer_closed": accepted_count >= nb_postes,
        "message": f"{accepted_count} candidat(s) accepté(s), {refused_count} refusé(s)."
        + (" L'offre est maintenant fermée." if accepted_count >= nb_postes else ""),
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
