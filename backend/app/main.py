from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.routes import cv, auth
from app.routes import admin, job_offers, matching
from app.services.nlp.hf_camembert import camembert_runtime_config

tags_metadata = [
    {
        "name": "Auth",
        "description": "Inscription, connexion (email/password), OAuth Google et LinkedIn.",
    },
    {
        "name": "CV",
        "description": "Upload de CVs (PDF/DOCX/PNG/JPG), extraction de texte et consultation des candidats.",
    },
    {
        "name": "Sant\u00e9",
        "description": "Endpoints de monitoring et statut du service.",
    },
]

app = FastAPI(
    title="3S TalentMatch API",
    description=(
        "## Plateforme intelligente de matching CV / offres d'emploi\n\n"
        "Cette API permet de :\n"
        "- **Uploader** des CVs au format PDF, DOCX ou Image PNG/JPG (max 10\u00a0Mo)\n"
        "- **Extraire** automatiquement le texte brut (PDF textuel, DOCX, PDF scann\u00e9 via OCR)\n"
        "- **Stocker** les candidats en base PostgreSQL\n"
        "- **Consulter** la liste des candidats enregistr\u00e9s\n\n"
        "### Authentification\n"
        "JWT Bearer token. Inscription / connexion via email ou OAuth (Google, LinkedIn).\n"
    ),
    version="1.0.0",
    contact={
        "name": "Youssef Gara",
        "email": "garayoussef0@gmail.com",
    },
    license_info={
        "name": "Projet acad\u00e9mique — 3S",
    },
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS (autorise le frontend React sur localhost:3000) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(cv.router, prefix="/api", tags=["CV"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])
app.include_router(job_offers.router, prefix="/api", tags=["Offres"])
app.include_router(matching.router, prefix="/api", tags=["Matching"])


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Santé"], summary="Vérifier l'état du service")
def health_check():
    """Retourne le statut courant de l'API. Utilisé pour les health-checks de monitoring."""
    return {"status": "ok", "service": "3S TalentMatch API"}


@app.get("/api/nlp/status", tags=["Santé"], summary="Diagnostic pipeline NLP (spaCy + CamemBERT)")
def nlp_status():
    """
    Retourne l'état exact du pipeline NLP en cours d'exécution :
    - spaCy : modèle chargé, NER actif, mode fallback
    - CamemBERT : activé ou non, token présent, modèle cible
    - huggingface_hub : bibliothèque disponible
    """
    # ── spaCy ────────────────────────────────────────────────────────────────
    spacy_info: dict = {"status": "unknown"}
    try:
        import spacy as _spacy
        spacy_info["version"] = getattr(_spacy, "__version__", None)
        try:
            _nlp = _spacy.load("fr_core_news_md")
            spacy_info["model"] = "fr_core_news_md"
            spacy_info["fallback"] = False
            spacy_info["has_ner"] = _nlp.has_pipe("ner")
            spacy_info["pipes"] = list(_nlp.pipe_names)
            spacy_info["status"] = "ok"
        except Exception as e:
            spacy_info["model"] = "blank:fr (fallback)"
            spacy_info["fallback"] = True
            spacy_info["has_ner"] = False
            spacy_info["pipes"] = []
            spacy_info["status"] = "degraded"
            spacy_info["error"] = str(e)
    except ImportError:
        spacy_info["status"] = "not_installed"

    # ── CamemBERT / HuggingFace ──────────────────────────────────────────────
    hf_info: dict = {}
    try:
        hf_info = camembert_runtime_config()
        hf_info["status"] = "enabled" if hf_info.get("enabled") else "disabled"
        if not hf_info.get("token_present"):
            hf_info["hint"] = "Ajoutez HF_TOKEN dans .env pour activer CamemBERT"
    except Exception as e:
        hf_info = {"status": "error", "error": str(e)}

    # ── huggingface_hub lib ──────────────────────────────────────────────────
    try:
        import huggingface_hub as _hf_hub
        hf_hub_info = {"available": True, "version": getattr(_hf_hub, "__version__", None)}
    except ImportError:
        hf_hub_info = {"available": False, "hint": "pip install huggingface_hub>=0.24.0"}

    return {
        "spacy": spacy_info,
        "camembert": hf_info,
        "huggingface_hub": hf_hub_info,
    }
