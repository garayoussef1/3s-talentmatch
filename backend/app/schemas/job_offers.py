from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class JobOfferBase(BaseModel):
    titre: str = Field(..., min_length=2, max_length=255)
    entreprise: Optional[str] = None
    description: Optional[str] = None
    competences_requises:  Optional[List[str]] = None
    competences_appreciees: Optional[List[str]] = None
    localisation: Optional[str] = None
    type_contrat: Optional[str] = None
    nb_postes: Optional[int] = 1
    experience_requise: Optional[int] = None
    formation_requise_niveau: Optional[int] = None
    domaine_metier: Optional[str] = None
    niveau_seniorite: Optional[str] = None
    status: Optional[str] = None
    date_limite: Optional[datetime] = None


class JobOfferCreate(JobOfferBase):
    status: Optional[str] = "active"


class JobOfferUpdate(BaseModel):
    titre: Optional[str] = None
    entreprise: Optional[str] = None
    description: Optional[str] = None
    competences_requises:  Optional[List[str]] = None
    competences_appreciees: Optional[List[str]] = None
    localisation: Optional[str] = None
    type_contrat: Optional[str] = None
    nb_postes: Optional[int] = None
    experience_requise: Optional[int] = None
    formation_requise_niveau: Optional[int] = None
    domaine_metier: Optional[str] = None
    niveau_seniorite: Optional[str] = None
    status: Optional[str] = None
    date_limite: Optional[datetime] = None


class JobOfferItem(JobOfferBase):
    id: str
    recruiter_id: Optional[str] = None
    created_at: Optional[str] = None
    date_limite: Optional[str] = None
    candidate_count: Optional[int] = 0
    assigned_recruiter_ids: Optional[List[str]] = None

    model_config = {"extra": "allow"}


class JobOfferListResponse(BaseModel):
    total: int
    total_pool: Optional[int] = 0
    offers: List[JobOfferItem]


class ApplicationItem(BaseModel):
    id: str
    cv_id: str
    candidate_id: str
    offer_id: str
    offer_title: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    status: str
    created_at: Optional[str] = None


class ApplicationListResponse(BaseModel):
    total: int
    applications: List[ApplicationItem]
