from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import cv

app = FastAPI(
    title="3S TalentMatch API",
    description="Plateforme intelligente de parsing de CVs",
    version="1.0.0",
)

# --- CORS (autorise le frontend React sur localhost:3000) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
app.include_router(cv.router, prefix="/api", tags=["CV"])


@app.get("/health", tags=["Santé"])
def health_check():
    return {"status": "ok", "service": "3S TalentMatch API"}
