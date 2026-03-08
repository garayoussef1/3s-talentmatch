# Guide du code — Sprint 1 (3S TalentMatch)

Ce document explique :
1. L’architecture du projet
2. Les fichiers importants et leur rôle
3. Le déroulement fonctionnel de Sprint 1
4. Les User Stories réalisées

---

## 1) Architecture globale

Le projet est séparé en 2 blocs :

- **Backend** : API FastAPI + extraction CV + base PostgreSQL
- **Frontend** : interface React (upload, dashboard, liste candidats)

Flux global :

1. L’utilisateur envoie un CV depuis le frontend
2. Le backend valide format/taille
3. Le backend extrait le texte (PDF/DOCX/OCR)
4. Le backend sauvegarde les données en PostgreSQL
5. Le frontend récupère les candidats via API et les affiche

---

## 2) Structure et rôle des fichiers (Sprint 1)

## Backend

### Entrée API
- `backend/app/main.py`
  - Initialise FastAPI
  - Configure CORS (frontend `localhost:3000`)
  - Expose les routes `/api/*`
  - Expose `/health`
  - Swagger disponible sur `/docs`

### Connexion base de données
- `backend/app/database.py`
  - Charge `DATABASE_URL` depuis `.env`
  - Configure SQLAlchemy (`engine`, `SessionLocal`, `Base`)
  - Fournit `get_db()` pour injecter la session dans les routes

### Routes CV
- `backend/app/routes/cv.py`
  - `POST /api/upload-cv` :
    - vérifie extension (`.pdf`, `.docx`)
    - vérifie taille max (10 MB)
    - lance extraction via `CVExtractor`
    - sauvegarde un candidat en BDD
    - retourne JSON (id, méthode, aperçu texte)
  - `GET /api/candidates` :
    - retourne les candidats avec pagination (`skip`, `limit`)

### Services d’extraction
- `backend/app/services/extraction/cv_extractor.py`
  - Orchestrateur : choisit le bon extracteur selon le type de fichier
- `backend/app/services/extraction/pdf_extractor.py`
  - Extraction PDF textuel multi-pages (PyPDF)
  - Détection PDF scanné (fallback OCR)
- `backend/app/services/extraction/word_extractor.py`
  - Extraction DOCX (python-docx)
- `backend/app/services/extraction/ocr_extractor.py`
  - OCR pour PDF/images scannés

### Modèles SQLAlchemy
- `backend/app/models/candidate.py` : table `candidates`
- `backend/app/models/user.py` : table `users`
- `backend/app/models/cv_document.py` : table `cv_documents`
- `backend/app/models/job_offer.py` : table `job_offers`
- `backend/app/models/match.py` : table `matches`
- `backend/app/models/__init__.py` : centralise les imports modèles

### Migrations
- `backend/alembic/env.py`
  - Relie Alembic à `Base.metadata`
  - Permet de générer/appliquer les migrations

### Tests
- `backend/tests/test_api_endpoints.py` : tests endpoints API
- `backend/tests/test_us017_extraction.py` : tests extraction PDF/DOCX
- `backend/tests/test_us018_validation.py` : tests validation format/taille
- `backend/tests/test_e2e_demo.py` : scénarios E2E (upload + candidates + erreurs)
- `backend/pytest.ini` : configuration des tests exécutés

### Dépendances backend
- `backend/requirements.txt`
  - FastAPI, SQLAlchemy, Alembic, psycopg2, extraction libs, pytest

---

## Frontend

### Entrée React
- `frontend/src/main.jsx` : point d’entrée React
- `frontend/src/App.jsx` : routes principales (`/`, `/upload`, `/candidates`)

### Pages
- `frontend/src/pages/Home.jsx` :
  - dashboard
  - récupère le nombre de CV via API
- `frontend/src/pages/UploadCV.jsx` :
  - drag & drop
  - upload fichier vers `/api/upload-cv`
  - affiche succès/erreur + aperçu texte
- `frontend/src/pages/Candidates.jsx` :
  - appelle `/api/candidates`
  - affiche le tableau des candidats

### Composants
- `frontend/src/components/Navbar.jsx` : navigation entre pages

### Styles
- `frontend/src/index.css` : styles globaux + responsive global
- `frontend/src/pages/*.css` : styles des pages (spinner, responsive, alertes…)
- Tailwind installé/configuré :
  - `frontend/tailwind.config.js`
  - `frontend/postcss.config.js`

### Build/front config
- `frontend/vite.config.js`
  - port frontend : `3000`
  - proxy `/api` vers backend `http://localhost:8000`

---

## 3) Comment ça se passe en Sprint 1 (workflow réel)

### Cas principal : upload d’un CV

1. L’utilisateur va sur `/upload`
2. Il dépose un fichier PDF ou DOCX
3. Frontend envoie `multipart/form-data` sur `POST /api/upload-cv`
4. Backend valide :
   - extension autorisée
   - taille ≤ 10 MB
5. Backend extrait le texte :
   - PDF textuel → PyPDF
   - PDF scanné → OCR
   - DOCX → python-docx
6. Backend sauvegarde le candidat en base `candidates`
7. Backend renvoie JSON de résultat
8. Frontend affiche la carte résultat

### Cas liste candidats

1. Frontend appelle `GET /api/candidates`
2. Backend lit en BDD et renvoie `{ total, candidates[] }`
3. Frontend affiche le tableau

---

## 4) User Stories Sprint 1 — état

### Réalisées
- Backend API upload + validation
- Extraction PDF/DOCX + fallback OCR
- Détection type fichier
- Schéma BDD + modèles SQLAlchemy + migrations Alembic
- Setup React/Vite + pages principales
- Tests unitaires + E2E
- Documentation Swagger enrichie

### Résultats techniques mesurés
- **Tests** : 45 passés
- **Couverture** : 83%
- **Base de données** : PostgreSQL (5 tables principales)

---

## 5) Commandes utiles (Sprint 1)

### Backend
```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm run dev
```

### Tests backend
```powershell
cd backend
pytest --cov=app --cov-report=term-missing
```

---

## 6) Ce document sert à quoi ?

Tu peux l’utiliser pour :
- préparer ta présentation de Sprint 1
- expliquer rapidement le projet à une encadrante
- onboarder un nouveau membre dans l’équipe

