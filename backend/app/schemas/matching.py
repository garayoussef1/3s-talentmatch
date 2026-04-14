from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class MatchCandidateItem(BaseModel):
    candidate_id: str
    cv_id: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None

    score: float
    details: Optional[Dict[str, Any]] = None


class MatchCandidatesResponse(BaseModel):
    job_offer_id: str
    total: int
    results: List[MatchCandidateItem]
