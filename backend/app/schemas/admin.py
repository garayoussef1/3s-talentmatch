from pydantic import BaseModel
from typing import Optional, List


class AdminUserItem(BaseModel):
    id: str
    nom: str
    prenom: str
    email: str
    role: str
    auth_provider: str
    is_active: bool
    is_email_verified: bool


class AdminUsersListResponse(BaseModel):
    total: int
    users: List[AdminUserItem]


class AdminUserDetail(AdminUserItem):
    pass


class AdminUserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
