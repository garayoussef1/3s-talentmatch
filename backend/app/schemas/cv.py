from pydantic import BaseModel
from typing import Optional


class CVUploadResponse(BaseModel):
    success: bool
    cv_id: str
    filename: str
    method: str
    text_preview: str
    message: str


class ErrorResponse(BaseModel):
    detail: str
