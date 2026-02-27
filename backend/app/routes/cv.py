import uuid
import os
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from app.services.extraction.cv_extractor import CVExtractor
from app.database import get_db
from app.models.candidate import Candidate

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    US-012 : Reçoit un fichier CV (PDF ou DOCX), extrait le texte brut,
    sauvegarde le candidat en BDD et retourne un JSON avec cv_id + texte extrait.
    """
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


@router.get("/candidates")
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
