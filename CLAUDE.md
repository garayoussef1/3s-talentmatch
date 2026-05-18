# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**3S TalentMatch** — CV-to-job-offer matching platform. Pipeline: upload CV → extract text (PDF/DOCX/OCR) → NLP parse into structured JSON (spaCy + optional CamemBERT) → store as `Candidate` → match against `JobOffer` with multi-scorer engine.

Project documentation, design notes, and reports are in `docs/` and `GUIDE_PROJET.md` / `CONTEXTE_PROJET_POUR_IA.txt` (largely in French).

## Stack

- **Backend** (`backend/`): FastAPI · SQLAlchemy 2 + Alembic · PostgreSQL 16 (port **5433** locally) · spaCy (`fr_core_news_md`) · EasyOCR · sentence-transformers · pypdf / PyMuPDF / python-docx · pytest
- **Frontend** (`frontend/`): React 18 · Vite 5 · React Router 6 · Axios · Tailwind
- **Deployment**: Railway (Dockerfile builder, see `*/railway.toml`)

## Commands

### Backend (run from `backend/`)

```bash
# Setup (Linux/macOS — Windows uses .venv-10\Scripts\python.exe; see dev.ps1)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download fr_core_news_md   # NOT installable from PyPI line in requirements
cp .env.example .env                        # then create DB: CREATE DATABASE talentmatch;
alembic upgrade head

# Dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Swagger: http://localhost:8000/docs · health: /health · NLP diag: /api/nlp/status

# Tests
pytest tests/ -v
pytest tests/test_match_engine_semantic.py -v        # single file
pytest tests/test_sprint2_unit.py::TestClassName::test_fn -v   # single test
pytest tests/ --cov=app --cov-report=term-missing    # coverage

# Migrations
alembic revision --autogenerate -m "msg"
alembic upgrade head

# Seed / admin helpers (backend/scripts/)
python -m scripts.seed_dev_admin
python -m scripts.reset_db_and_seed_admin
# Matching-sandbox model training pipeline:
python -m scripts.sandbox_build_dataset
python -m scripts.sandbox_train_model
python -m scripts.sandbox_eval_model
```

### Frontend (run from `frontend/`)

```bash
npm install
npm run dev       # http://localhost:3000, proxies /api/* → http://localhost:8000
npm run build     # → dist/
npm run preview
```

The proxy target is overridable via `VITE_API_TARGET` env var. OAuth client IDs live in `frontend/.env` (`VITE_GOOGLE_CLIENT_ID`, `VITE_LINKEDIN_CLIENT_ID`).

### Run both (Windows only, from repo root)

`./dev.ps1` starts backend + frontend in background, writes PIDs/URLs to `logs/.dev-pids.json`; `./stop-dev.ps1` kills them. Logs land in `logs/`. The script expects a venv at `./.venv-10/` (Python 3.10).

### CamemBERT toggle (optional NLP enrichment)

CamemBERT NER is **off by default**. Toggle via env vars `HF_ENABLE_CAMEMBERT_NAME` + `HF_TOKEN`. Helper scripts at repo root: `dev-camembert-off.ps1`, `dev-camembert-status.ps1`. Diagnose via `GET /api/nlp/status`.

## Architecture

### Backend: pipeline-shaped, not CRUD-shaped

`backend/app/main.py` mounts routers under `/api`: `auth`, `cv`, `admin`, `job_offers`, `matching`, `dashboard`, `notifications`. The **lifespan handler pre-warms the BERT matching model** to avoid cold-start latency on the first match request — keep this in mind when modifying startup.

Two pipelines drive the core value:

**1. CV ingestion** (`POST /api/upload-cv`)
- `services/extraction/` — `CVExtractor` dispatches by file type:
  - PDF textual → `pdf_extractor.py` (pypdf / PyMuPDF)
  - DOCX → `word_extractor.py` (python-docx)
  - Image / scanned PDF → `ocr_extractor.py` (EasyOCR)
- `services/nlp/nlp_parser.py` — `NLPParser.parse(text)` is the orchestrator. It loads spaCy (falls back to `spacy.blank('fr')` if `fr_core_news_md` is missing, recorded in `parsed_data.metadata.spacy_fallback`) and calls extractors in order: `ContactExtractor` → `EntityExtractor` (+ optional `HFCamembertNameExtractor`) → `SkillsExtractor` → `FormationExtractor` → `ExperienceExtractor` → `_extract_langues`.
- Each NLP extractor is **one class per domain** with a single `extract(...)` entry point. Section detection and shared regex live in `nlp/utils.py` + `nlp/config.py` (`SECTION_PATTERNS`).
- Result is persisted on `Candidate.parsed_data` (JSON). Schemas are in `app/schemas/cv_data.py`.

**2. Matching** (`/api/matching/*`)
- `services/matching/match_engine.py` — primary engine.
- `services/matching_sandbox/` — experimental multi-scorer stack (TF-IDF, BERT, ML, decision-tree). `bert_scorer.BERTMatchingScorer` is the one warmed at startup. `report_generator.py` produces explainable match reports.
- Training/eval data and scripts: `services/matching_sandbox/{datasets,models}/` and `backend/scripts/sandbox_*.py`.

### Models / schemas / routes layout

- `app/models/` — SQLAlchemy ORM: `user`, `candidate`, `cv_document`, `job_offer`, `match`, `notification`, `access_log`.
- `app/schemas/` — Pydantic DTOs (mirrors routes, plus `cv_data.py` for the parsed-CV JSON shape including spaCy provenance fields).
- `app/routes/` — one file per resource; all share `dependencies.py` (DB session, current-user JWT extraction).
- `app/services/auth_service.py`, `email_service.py`, `access_logger.py` — cross-cutting concerns. Auth is JWT-Bearer with OTP email verification, password reset, and Google/LinkedIn OAuth (config in `.env`).

### Frontend

Standard Vite SPA. `src/services/api.js` is the **single axios instance** — it injects the JWT from `localStorage`, has an 8s timeout, and on `401` clears storage and redirects to `/login`. Always import from here rather than calling axios directly. Routes live in `src/App.jsx`; `components/ProtectedRoute.jsx` gates authenticated pages.

## Conventions worth knowing

- **Languages**: code identifiers are mostly English; comments, docstrings, commit messages, and docs are in French. Match the local style of the file you're editing.
- **spaCy provenance**: when adding NLP extractors, surface model/version/fallback info via `parsed_data.metadata` so the `/api/nlp/status` endpoint and A/B comparison scripts in `tests/compare_spacy_impact_batch.py` continue to work.
- **`fr-core-news-md` is not pip-installable from PyPI** despite being listed in `requirements.txt` — install via `python -m spacy download fr_core_news_md` (the Dockerfile already does this; local installs need it manually).
- **Postgres port is 5433**, not the default 5432 — match `.env.example` when configuring local DBs.
- **Don't bypass the API axios instance** on the frontend; the 401-redirect interceptor is the auth invariant.
