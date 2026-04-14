from pydantic import BaseModel, Field
from typing import Optional, List


class JobOfferBase(BaseModel):
    titre: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    competences_requises: Optional[List[str]] = None
    localisation: Optional[str] = None
    type_contrat: Optional[str] = None
    status: Optional[str] = None


class JobOfferCreate(JobOfferBase):
    status: Optional[str] = "active"


class JobOfferUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    competences_requises: Optional[List[str]] = None
    localisation: Optional[str] = None
    type_contrat: Optional[str] = None
    status: Optional[str] = None


class JobOfferItem(JobOfferBase):
    id: str
    recruiter_id: Optional[str] = None
    created_at: Optional[str] = None


class JobOfferListResponse(BaseModel):
    total: int
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
