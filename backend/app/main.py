from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.routes import cv, auth

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


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Santé"], summary="Vérifier l'état du service")
def health_check():
    """Retourne le statut courant de l'API. Utilisé pour les health-checks de monitoring."""
    return {"status": "ok", "service": "3S TalentMatch API"}
