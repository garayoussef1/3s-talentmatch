import uuid
import os
import tempfile
import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.nlp_parser import NLPParser
from app.database import get_db
from app.models.candidate import Candidate, CandidatureStatus
from app.models.job_offer import JobOffer, JobStatus
from app.models.match import Match, MatchStatus
from app.models.user import User, UserRole
from app.dependencies import get_current_user, get_current_recruteur_or_admin, get_current_admin

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Singletons (chargés une seule fois au démarrage)
_nlp_parser: Optional[NLPParser] = None
_cv_extractor: Optional[CVExtractor] = None


def _originals_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    p = repo_root / "data" / "cvs_raw" / "originals"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _find_original_file(cv_id: str) -> Optional[Path]:
    d = _originals_dir()
    matches = list(d.glob(f"{cv_id}.*"))
    return matches[0] if matches else None


def _get_nlp_parser() -> NLPParser:
    """Lazy singleton pour éviter de recharger spaCy à chaque requête."""
    global _nlp_parser
    if _nlp_parser is None:
        _nlp_parser = NLPParser()
    return _nlp_parser


def _get_cv_extractor() -> CVExtractor:
    """Lazy singleton pour éviter de recréer l'extracteur à chaque requête."""
    global _cv_extractor
    if _cv_extractor is None:
        _cv_extractor = CVExtractor()
    return _cv_extractor


# ── Schémas de réponse Swagger ──────────────────────────────────────────
class CVUploadResponse(BaseModel):
    success: bool
    cv_id: str
    filename: str
    method: str
    text_preview: str
    parsed_data: Optional[Dict[str, Any]] = None
    application_id: Optional[str] = None
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "cv_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "filename": "mon_cv.pdf",
                "method": "pypdf",
                "text_preview": "Jean Dupont\nDéveloppeur Full Stack\nParis, France...",
                "parsed_data": {
                    "identite": {"nom_complet": "Jean Dupont"},
                    "competences": [{"name": "Python", "category": "langages"}],
                    "formations": [{"diplome": "Ingénieur", "etablissement": "ESPRIT"}],
                    "experiences": [{"poste": "Développeur", "entreprise": "TechCorp"}],
                },
                "message": "CV reçu, texte extrait, NLP parsing effectué.",
            }
        }
    }


class CandidateItem(BaseModel):
    cv_id: str
    filename: str
    nom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    offer_titles: List[str] = Field(default_factory=list)
    extraction_method: Optional[str] = None
    candidature_status: Optional[str] = None
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
    summary="Uploader un CV (PDF, DOCX ou Image)",
    description=(
        "Reçoit un fichier CV au format **PDF**, **DOCX** ou **Image** (PNG/JPG) — taille max 10\u00a0Mo.\n\n"
        "Le fichier est automatiquement analysé :\n"
        "- PDF textuel → extraction via **PyPDF**\n"
        "- PDF scanné → extraction via **EasyOCR**\n"
        "- DOCX → extraction via **python-docx**\n"
        "- Image (PNG/JPG) → extraction via **EasyOCR**\n\n"
        "Le candidat est ensuite persisté en base de données PostgreSQL."
    ),
    responses={
        200: {"description": "CV traité avec succès", "model": CVUploadResponse},
        400: {"description": "Format de fichier non supporté (accepte .pdf, .docx, .png, .jpg)"},
        413: {"description": "Fichier trop volumineux (max 10\u00a0Mo)"},
        500: {"description": "Erreur interne lors de l'extraction"},
    },
)
async def upload_cv(
    file: UploadFile = File(..., description="Fichier CV au format PDF, DOCX, PNG ou JPG (max 10 Mo)"),
    offer_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.candidat and offer_id is None:
        raise HTTPException(status_code=400, detail="Une offre est requise pour postuler")
    # Validation extension
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{ext}' non supporté. Formats acceptés : PDF, DOCX, PNG, JPG.",
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

    # Sauvegarde du fichier original (pour téléchargement/visualisation ATS)
    try:
        original_path = _originals_dir() / f"{cv_id}{ext}"
        original_path.write_bytes(contents)
    except Exception:
        # Ne doit pas bloquer le pipeline; on pourra toujours fonctionner sans fichier original.
        original_path = None

    try:
        # Extraction du texte (singleton — évite de recréer l'extracteur à chaque requête)
        extractor = _get_cv_extractor()
        result = extractor.extract(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur extraction : {str(e)}")
    finally:
        os.unlink(tmp_path)

    raw_text = result.get("text", "")
    method = result.get("method", "unknown")

    # ── NLP Parsing complet ──────────────────────────────────────
    parsed_data = None
    nom_extrait = None
    email_extrait = None
    telephone_extrait = None
    linkedin_extrait = None
    github_extrait = None

    if raw_text and len(raw_text.strip()) >= 50:
        try:
            parser = _get_nlp_parser()
            nlp_result = parser.parse(raw_text, cv_id=cv_id)
            if nlp_result.get("success"):
                parsed_data = nlp_result["parsed_data"]
                identite = parsed_data.get("identite", {})
                contacts = parsed_data.get("contacts", {})
                nom_extrait = identite.get("nom_complet")
                email_extrait = contacts.get("email")
                telephone_extrait = contacts.get("telephone")
                linkedin_extrait = contacts.get("linkedin")
                github_extrait = contacts.get("github")
        except Exception as e:
            # Le parsing NLP ne doit pas bloquer l'upload
            import logging
            logging.getLogger(__name__).warning(f"NLP parsing failed: {e}")

    # Sauvegarde en base de données
    candidate = Candidate(
        cv_id=cv_id,
        filename=file.filename,
        raw_text=raw_text,
        extraction_method=method,
        nom=nom_extrait,
        email=email_extrait,
        telephone=telephone_extrait,
        linkedin=linkedin_extrait,
        github=github_extrait,
        parsed_data=parsed_data,
        user_id=current_user.id,
        candidature_status=CandidatureStatus.en_attente,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    application_id = None
    if offer_id:
        if current_user.role != UserRole.candidat:
            raise HTTPException(status_code=403, detail="Seuls les candidats peuvent postuler")

        offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
        if not offer or offer.status != JobStatus.active:
            raise HTTPException(status_code=404, detail="Offre non trouvée ou inactive")

        existing = (
            db.query(Match)
            .filter(Match.candidate_id == candidate.id, Match.job_offer_id == offer_id)
            .first()
        )
        if not existing:
            match = Match(
                candidate_id=candidate.id,
                job_offer_id=offer_id,
                score=0.0,
                details=None,
                status=MatchStatus.pending,
            )
            db.add(match)
            db.commit()
            db.refresh(match)
            application_id = str(match.id)
        else:
            application_id = str(existing.id)

    return {
        "success": True,
        "cv_id": cv_id,
        "filename": file.filename,
        "method": method,
        "text_preview": raw_text[:300],
        "parsed_data": parsed_data,
        "application_id": application_id,
        "message": "CV reçu, texte extrait et parsing NLP effectué." if parsed_data else "CV reçu, texte extrait (parsing NLP non disponible).",
    }


@router.get(
    "/candidates",
    response_model=CandidatesListResponse,
    summary="Lister les candidats (recruteur/admin uniquement)",
    description=(
        "Retourne la liste paginée des candidats enregistrés en base de données,\n"
        "triés par date d'upload décroissante.\n\n"
        "**Accès : recruteur ou admin uniquement.**\n\n"
        "Paramètres de pagination :\n"
        "- **skip** : nombre d'enregistrements à ignorer (défaut 0)\n"
        "- **limit** : nombre maximum de résultats (défaut 20)"
    ),
    responses={
        200: {"description": "Liste des candidats", "model": CandidatesListResponse},
        403: {"description": "Accès interdit (candidat)"},
    },
)
def get_candidates(skip: int = 0, limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_recruteur_or_admin)):
    """Retourne la liste des candidats enregistrés en BDD."""
    # IMPORTANT (PostgreSQL): faire DISTINCT / COUNT sur l'entité Candidate (qui contient
    # parsed_data en JSON) peut générer du SQL qui compare des colonnes JSON, ce qui casse
    # sur Postgres (pas d'opérateur d'égalité pour json).
    # Stratégie robuste: paginer sur des IDs (UUID) uniquement, puis recharger les candidats.

    candidates_by_id: Dict[UUID, Candidate] = {}
    candidate_ids: List[UUID] = []
    total: int = 0

    if current_user.role.value != "admin":
        base_ids_query = (
            db.query(Candidate.id, Candidate.created_at)
            .join(Match, Match.candidate_id == Candidate.id)
            .join(JobOffer, Match.job_offer_id == JobOffer.id)
            .filter(JobOffer.recruiter_id == current_user.id)
            .distinct()
        )

        total = (
            db.query(func.count(func.distinct(Candidate.id)))
            .select_from(Candidate)
            .join(Match, Match.candidate_id == Candidate.id)
            .join(JobOffer, Match.job_offer_id == JobOffer.id)
            .filter(JobOffer.recruiter_id == current_user.id)
            .scalar()
            or 0
        )

        candidate_ids = [row[0] for row in base_ids_query.order_by(Candidate.created_at.desc()).offset(skip).limit(limit).all()]
    else:
        total = db.query(func.count(Candidate.id)).scalar() or 0
        candidate_ids = [row[0] for row in db.query(Candidate.id).order_by(Candidate.created_at.desc()).offset(skip).limit(limit).all()]

    candidates: List[Candidate] = []
    if candidate_ids:
        fetched = (
            db.query(Candidate)
            .options(selectinload(Candidate.matches).selectinload(Match.job_offer))
            .filter(Candidate.id.in_(candidate_ids))
            .all()
        )
        candidates_by_id = {c.id: c for c in fetched}
        candidates = [candidates_by_id[cid] for cid in candidate_ids if cid in candidates_by_id]

    def _pick_display_name(candidate: Candidate) -> Optional[str]:
        def _norm_letters(s: str) -> str:
            return re.sub(r"[^a-zà-öø-ÿ]+", "", (s or "").lower())

        def _is_name_suspicious(n: Optional[str]) -> bool:
            if not n:
                return True
            n = " ".join(str(n).split()).strip()
            if len(n) < 3 or len(n) > 80:
                return True
            if any(ch.isdigit() for ch in n):
                return True
            if "@" in n or ":" in n:
                return True
            words = n.split()
            if len(words) < 2 or len(words) > 5:
                return True

            joined = _norm_letters("".join(words))
            banned_joined = {
                "formation", "competences", "compétences", "experience", "expérience",
                "profil", "contact", "langues", "languages", "skills", "education",
                "projets", "projects", "certifications", "references", "références",
                "objective", "objectif", "resume", "résumé", "curriculumvitae",
                "devops", "fullstack",
            }
            banned_norm = {_norm_letters(x) for x in banned_joined}
            if joined in banned_norm:
                return True

            jobish = {
                "dev", "ops", "devops", "engineer", "developer", "architect", "manager",
                "analyst", "consultant", "designer", "fullstack", "frontend", "backend",
                "data", "scientist", "lead", "senior", "junior",
            }
            for w in words:
                wl = _norm_letters(w)
                if wl in banned_norm or wl in jobish:
                    return True
            return False

        def _derive_name_from_email(email: Optional[str]) -> Optional[str]:
            if not email or "@" not in email:
                return None
            local = email.split("@", 1)[0].strip().lower()
            local = local.split("+", 1)[0]
            local = re.sub(r"\d+$", "", local)
            parts = [p for p in re.split(r"[._\-]+", local) if p]
            if len(parts) < 2:
                return None
            first, last = parts[0], parts[1]
            if len(first) < 2 or len(last) < 2:
                return None
            banned = {"contact", "support", "hr", "recrutement", "recruitment", "jobs", "career", "admin"}
            if first in banned or last in banned:
                return None
            first = re.sub(r"[^a-zà-öø-ÿ']+", "", first)
            last = re.sub(r"[^a-zà-öø-ÿ']+", "", last)
            if not first or not last:
                return None
            return f"{first.capitalize()} {last.capitalize()}"

        name = candidate.nom
        parsed_name = None
        parsed_email = None
        try:
            parsed = candidate.parsed_data or {}
            parsed_name = (parsed.get("identite") or {}).get("nom_complet")
            parsed_email = (parsed.get("contacts") or {}).get("email")
        except Exception:
            parsed_name = None
            parsed_email = None

        email = candidate.email or parsed_email
        derived_name = _derive_name_from_email(email)

        for n in (name, parsed_name, derived_name):
            if n and not _is_name_suspicious(n):
                return n

        # Fallback best-effort (même si suspect)
        return parsed_name or name or derived_name

    def _offer_titles(candidate: Candidate) -> List[str]:
        titles = []
        for m in (candidate.matches or []):
            if not m.job_offer:
                continue
            if current_user.role.value != "admin" and m.job_offer.recruiter_id != current_user.id:
                continue
            titles.append(m.job_offer.titre)
        # Deduplicate while preserving order
        seen = set()
        result = []
        for t in titles:
            if t in seen:
                continue
            seen.add(t)
            result.append(t)
        return result

    def _candidature_status_from_offers(candidate: Candidate) -> str:
        """Statut affiché côté recruteur/admin: dérivé du statut des candidatures (Match)."""
        relevant_matches: List[Match] = []
        for m in (candidate.matches or []):
            if not m.job_offer:
                continue
            if current_user.role.value != "admin" and m.job_offer.recruiter_id != current_user.id:
                continue
            relevant_matches.append(m)

        if not relevant_matches:
            return candidate.candidature_status.value if candidate.candidature_status else "en_attente"

        # Règle simple et robuste (agrégée):
        # - si au moins une candidature est acceptée => candidat "Accepté"
        # - sinon si au moins une est refusée => "Refusé"
        # - sinon => "En attente"
        statuses = {m.status for m in relevant_matches}
        if MatchStatus.accepted in statuses:
            return "accepte"
        if MatchStatus.rejected in statuses:
            return "refuse"
        return "en_attente"
    return {
        "total": total,
        "candidates": [
            {
                "cv_id": c.cv_id,
                "filename": c.filename,
                "nom": _pick_display_name(c),
                "email": c.email,
                "telephone": c.telephone,
                "linkedin": c.linkedin,
                "github": c.github,
                "offer_titles": _offer_titles(c),
                "extraction_method": c.extraction_method,
                "candidature_status": _candidature_status_from_offers(c),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in candidates
        ],
    }


@router.get(
    "/candidates/{cv_id}",
    summary="Détail d'un candidat (recruteur/admin)",
    description="Retourne toutes les données extraites par le pipeline NLP pour un CV donné.",
    responses={
        200: {"description": "Données complètes du candidat"},
        403: {"description": "Accès interdit"},
        404: {"description": "Candidat non trouvé"},
    },
)
def get_candidate_detail(cv_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_recruteur_or_admin)):
    """Retourne le détail complet d'un candidat (infos parsées incluses)."""
    candidate = (
        db.query(Candidate)
        .options(selectinload(Candidate.matches).selectinload(Match.job_offer))
        .filter(Candidate.cv_id == cv_id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")
    raw_text = candidate.raw_text or ""
    original_file = _find_original_file(cv_id)

    relevant_matches: List[Match] = []
    for m in (candidate.matches or []):
        if not m.job_offer:
            continue
        if current_user.role.value != "admin" and m.job_offer.recruiter_id != current_user.id:
            continue
        relevant_matches.append(m)

    candidature_status = candidate.candidature_status.value if candidate.candidature_status else "en_attente"
    if relevant_matches:
        statuses = {m.status for m in relevant_matches}
        if MatchStatus.accepted in statuses:
            candidature_status = "accepte"
        elif MatchStatus.rejected in statuses:
            candidature_status = "refuse"
        else:
            candidature_status = "en_attente"
    return {
        "cv_id": candidate.cv_id,
        "filename": candidate.filename,
        "nom": candidate.nom,
        "email": candidate.email,
        "telephone": candidate.telephone,
        "linkedin": candidate.linkedin,
        "github": candidate.github,
        "extraction_method": candidate.extraction_method,
        "parsed_data": candidate.parsed_data,
        "raw_text_preview": raw_text[:1500] if raw_text else "",
        "raw_text_length": len(raw_text) if raw_text else 0,
        "candidature_status": candidature_status,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "original_file_available": original_file is not None,
    }


@router.get(
    "/candidates/{cv_id}/original",
    summary="Télécharger/voir le CV original (recruteur/admin)",
    description="Retourne le fichier CV original uploadé (si disponible).",
    responses={
        200: {"description": "Fichier original"},
        403: {"description": "Accès interdit"},
        404: {"description": "Fichier non trouvé"},
    },
)
def download_original_cv(cv_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_recruteur_or_admin)):
    candidate = db.query(Candidate).filter(Candidate.cv_id == cv_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")

    original_file = _find_original_file(cv_id)
    if not original_file or not original_file.exists():
        raise HTTPException(status_code=404, detail="Fichier original indisponible")

    filename = candidate.filename or original_file.name
    return FileResponse(path=str(original_file), filename=filename)


@router.patch(
    "/candidates/{cv_id}/status",
    summary="Modifier le statut d'une candidature (recruteur/admin)",
    description="Met à jour le statut : en_attente, accepte, refuse.",
    responses={
        200: {"description": "Statut mis à jour"},
        403: {"description": "Accès interdit"},
        404: {"description": "Candidat non trouvé"},
    },
)
def update_candidature_status(
    cv_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_recruteur_or_admin),
):
    """Met à jour le statut de candidature d'un candidat."""
    candidate = db.query(Candidate).filter(Candidate.cv_id == cv_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")

    valid_statuses = [s.value for s in CandidatureStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Statut invalide. Valeurs possibles : {valid_statuses}")

    candidate.candidature_status = CandidatureStatus(status)
    db.commit()
    db.refresh(candidate)
    return {
        "success": True,
        "cv_id": cv_id,
        "candidature_status": candidate.candidature_status.value,
        "message": f"Statut mis à jour : {status}",
    }


@router.delete(
    "/candidates/{cv_id}",
    summary="Supprimer un candidat (recruteur/admin)",
    description="Supprime un candidat et toutes ses données de la base.",
    responses={
        200: {"description": "Candidat supprimé"},
        403: {"description": "Accès interdit"},
        404: {"description": "Candidat non trouvé"},
    },
)
def delete_candidate(cv_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_recruteur_or_admin)):
    """Supprime un candidat par son cv_id."""
    candidate = db.query(Candidate).filter(Candidate.cv_id == cv_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")

    original_file = _find_original_file(cv_id)
    if original_file and original_file.exists():
        try:
            original_file.unlink()
        except Exception:
            pass
    db.delete(candidate)
    db.commit()
    return {"success": True, "message": f"Candidat {cv_id} supprimé."}


@router.delete(
    "/candidates",
    summary="Supprimer tous les candidats (admin uniquement)",
    description="Supprime tous les candidats de la base de données. Action irréversible.",
    responses={
        200: {"description": "Tous les candidats supprimés"},
        403: {"description": "Accès interdit"},
    },
)
def delete_all_candidates(db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    """Supprime tous les candidats."""
    count = db.query(Candidate).count()
    db.query(Candidate).delete()
    db.commit()
    return {"success": True, "deleted": count, "message": f"{count} candidat(s) supprimé(s)."}


# ══════════════════════════════════════════════════════════════════════════
# Routes spécifiques au candidat — « Mon espace »
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/my-applications",
    summary="Mes candidatures (candidat)",
    description="Le candidat connecté voit la liste de ses CVs uploadés avec leur statut.",
    responses={
        200: {"description": "Liste des candidatures du candidat connecté"},
    },
)
def get_my_applications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retourne les candidatures (CVs) du candidat connecté."""
    candidates = (
        db.query(Candidate)
        .filter(Candidate.user_id == current_user.id)
        .order_by(Candidate.created_at.desc())
        .all()
    )
    return {
        "total": len(candidates),
        "applications": [
            {
                "cv_id": c.cv_id,
                "filename": c.filename,
                "nom": c.nom,
                "email": c.email,
                "candidature_status": c.candidature_status.value if c.candidature_status else "en_attente",
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in candidates
        ],
    }


@router.get(
    "/my-applications/offers",
    summary="Mes candidatures par offre (candidat)",
    description="Le candidat voit ses candidatures associees aux offres.",
)
def get_my_applications_by_offer(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    matches = (
        db.query(Match)
        .join(Candidate, Match.candidate_id == Candidate.id)
        .join(JobOffer, Match.job_offer_id == JobOffer.id)
        .filter(Candidate.user_id == current_user.id)
        .order_by(Match.created_at.desc())
        .all()
    )

    return {
        "total": len(matches),
        "applications": [
            {
                "application_id": str(m.id),
                "cv_id": m.candidate.cv_id if m.candidate else "",
                "offer_id": str(m.job_offer_id),
                "offer_title": m.job_offer.titre if m.job_offer else None,
                "offer_type": m.job_offer.type_contrat if m.job_offer else None,
                "offer_location": m.job_offer.localisation if m.job_offer else None,
                "status": m.status.value,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in matches
        ],
    }
