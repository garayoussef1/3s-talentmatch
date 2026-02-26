import uuid
import os
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.extraction.cv_extractor import CVExtractor

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...)):
    """
    US-012 : Reçoit un fichier CV (PDF ou DOCX), extrait le texte brut
    et retourne un JSON avec cv_id + texte extrait.
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

    return {
        "success": True,
        "cv_id": cv_id,
        "filename": file.filename,
        "method": result.get("method", "unknown"),
        "text_preview": result.get("text", "")[:300],
        "message": "CV reçu et texte extrait avec succès.",
    }
