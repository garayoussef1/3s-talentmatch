# 3S TalentMatch — Vue d’ensemble

## Objectif
Plateforme web qui **ingère des CV**, en **extrait** du texte (PDF/DOCX/images), applique un **parsing NLP** (spaCy) pour obtenir des données structurées, puis permet le **suivi des candidatures** (statuts) et, à terme, le **matching** CV ↔ offres.

## Architecture (simple)
- **Frontend**: React + Vite (dossier `frontend/`)
  - Appelle l’API via `axios` avec `baseURL: "/api"` et un proxy Vite vers `http://localhost:8000`.
- **Backend**: FastAPI + SQLAlchemy (dossier `backend/`)
  - Expose des routes Auth (`/api/auth/*`) et CV (`/api/*`).
  - Stockage PostgreSQL via SQLAlchemy/Alembic.

## Rôles & Auth
- Rôles principaux: **candidat**, **recruteur**, **admin**.
- Auth: JWT Bearer, OTP vérif email, reset mot de passe, OAuth Google/LinkedIn.

## Flux principal “Upload CV → Données structurées”
1. Frontend envoie un fichier vers `POST /api/upload-cv`.
2. Backend valide extension + taille, sauve temporairement le fichier.
3. Extraction texte via `CVExtractor`:
   - PDF textuel → PyPDF
   - DOCX → python-docx
   - PDF scanné / image → EasyOCR
4. Parsing NLP via `NLPParser`:
   - Extraction d’identité/contacts/compétences/formations/expériences/langues.
5. Sauvegarde en base (`Candidate`) avec `parsed_data` (JSON) + `candidature_status`.

## Dossiers importants
- `backend/app/routes/`: endpoints (auth, CV, etc.)
- `backend/app/services/extraction/`: extraction texte (PDF/DOCX/OCR)
- `backend/app/services/nlp/`: parsing NLP (spaCy)
- `frontend/src/`: pages + services API
- `data/cvs_raw/`: exemples de CV pour tests
- `docs/`: documents et diagrammes

## Endpoints clés (actuels)
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `POST /api/upload-cv`
- `GET /api/candidates`, `GET /api/candidates/{cv_id}`

## Démarrage (un seul terminal)
- Lancer: `./dev.ps1`
- Stopper: `./stop-dev.ps1`
- Logs: `logs/backend.out.log`, `logs/backend.err.log`, `logs/frontend.out.log`, `logs/frontend.err.log`
