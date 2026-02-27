import uuid
import os
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.services.extraction.cv_extractor import CVExtractor
from app.database import get_db
from app.models.candidate import Candidate

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Schémas de réponse Swagger ──────────────────────────────────────────
class CVUploadResponse(BaseModel):
    success: bool
    cv_id: str
    filename: str
    method: str
    text_preview: str
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "cv_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "filename": "mon_cv.pdf",
                "method": "pypdf",
                "text_preview": "Jean Dupont\nDéveloppeur Full Stack\nParis, France...",
                "message": "CV reçu, texte extrait et candidat sauvegardé.",
            }
        }
    }


class CandidateItem(BaseModel):
    cv_id: str
    filename: str
    nom: Optional[str] = None
    email: Optional[str] = None
    extraction_method: Optional[str] = None
    created_at: Optional[str] = None


class CandidatesListResponse(BaseModel):
    total: int
    candidates: List[CandidateItem]

    model_config = {
        "json_schema_extra": {
            "example": {
                "total": 1,
                "candidates": [{
                    "cv_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "filename": "mon_cv.pdf",
                    "nom": None,
                    "email": None,
                    "extraction_method": "pypdf",
                    "created_at": "2026-02-27T10:00:00",
                }]
            }
        }
    }


@router.post(
    "/upload-cv",
    response_model=CVUploadResponse,
    summary="Uploader un CV (PDF ou DOCX)",
    description=(
        "Reçoit un fichier CV au format **PDF** ou **DOCX** (taille max\u00a010\u00a0Mo).\n\n"
        "Le fichier est automatiquement analysé :\n"
        "- PDF textuel → extraction via **PyPDF**\n"
        "- PDF scanné → extraction via **EasyOCR**\n"
        "- DOCX → extraction via **python-docx**\n\n"
        "Le candidat est ensuite persisté en base de données PostgreSQL."
    ),
    responses={
        200: {"description": "CV traité avec succès", "model": CVUploadResponse},
        400: {"description": "Format de fichier non supporté (accepte .pdf et .docx uniquement)"},
        413: {"description": "Fichier trop volumineux (max 10\u00a0Mo)"},
        500: {"description": "Erreur interne lors de l'extraction"},
    },
)
async def upload_cv(file: UploadFile = File(..., description="Fichier CV au format PDF ou DOCX (max 10 Mo)"), db: Session = Depends(get_db)):
    # Validation extension
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{ext}' non supporté. Formats acceptés : PDF, DOCX.",
        )

    # Lecture et validation taille
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Fichier trop volumineux. Taille maximale : 10 Mo.",
        )

    # Sauvegarde temporaire
    cv_id = str(uuid.uuid4())
    suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Extraction du texte
        extractor = CVExtractor()
        result = extractor.extract(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur extraction : {str(e)}")
    finally:
        os.unlink(tmp_path)

    raw_text = result.get("text", "")
    method = result.get("method", "unknown")

    # Sauvegarde en base de données
    candidate = Candidate(
        cv_id=cv_id,
        filename=file.filename,
        raw_text=raw_text,
        extraction_method=method,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return {
        "success": True,
        "cv_id": cv_id,
        "filename": file.filename,
        "method": method,
        "text_preview": raw_text[:300],
        "message": "CV reçu, texte extrait et candidat sauvegardé.",
    }


@router.get(
    "/candidates",
    response_model=CandidatesListResponse,
    summary="Lister les candidats",
    description=(
        "Retourne la liste paginée des candidats enregistrés en base de données,\n"
        "triés par date d'upload décroissante.\n\n"
        "Paramètres de pagination :\n"
        "- **skip** : nombre d'enregistrements à ignorer (défaut 0)\n"
        "- **limit** : nombre maximum de résultats (défaut 20)"
    ),
    responses={
        200: {"description": "Liste des candidats", "model": CandidatesListResponse},
    },
)
def get_candidates(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Retourne la liste des candidats enregistrés en BDD."""
    candidates = db.query(Candidate).order_by(Candidate.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Candidate).count()
    return {
        "total": total,
        "candidates": [
            {
                "cv_id": c.cv_id,
                "filename": c.filename,
                "nom": c.nom,
                "email": c.email,
                "extraction_method": c.extraction_method,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in candidates
        ],
    }
