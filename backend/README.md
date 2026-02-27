# 3S TalentMatch — Backend

API REST FastAPI pour la plateforme de matching CV/offres d'emploi.

## Stack technique

- **Python 3.11+**
- **FastAPI** — framework API
- **SQLAlchemy 2** + **Alembic** — ORM + migrations
- **PostgreSQL 16** — base de données
- **pypdf** + **python-docx** — extraction texte PDF/DOCX
- **pytest** — tests unitaires

---

## Prérequis

- Python 3.11 ou supérieur
- PostgreSQL 16 installé et démarré (port **5433**)
- Git

---

## Installation

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd 3s-talentmatch
```

### 2. Créer l'environnement virtuel

```bash
python -m venv .venv
```

### 3. Activer l'environnement virtuel

**Windows (PowerShell) :**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS :**
```bash
source .venv/bin/activate
```

### 4. Installer les dépendances

```bash
cd backend
pip install -r requirements.txt
```

---

## Variables d'environnement

Copier le fichier exemple et l'adapter :

```bash
cp .env.example .env
```

Contenu de `.env` :

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/talentmatch
API_HOST=0.0.0.0
API_PORT=8000
```

> ⚠️ Ne jamais commiter le fichier `.env` (déjà dans `.gitignore`)

---

## Créer la base de données

```sql
-- Dans psql ou pgAdmin :
CREATE DATABASE talentmatch;
```

---

## Lancer les migrations

```bash
alembic upgrade head
```

---

## Démarrer le serveur

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

L'API est accessible sur : http://localhost:8000

Documentation Swagger : http://localhost:8000/docs

---

## Lancer les tests

```bash
pytest tests/ -v
```

Avec rapport de couverture :

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Endpoints disponibles

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Statut de l'API |
| POST | `/api/upload-cv` | Upload + extraction d'un CV |
| GET | `/api/candidates` | Liste tous les candidats |

---

## Structure du projet

```
backend/
├── app/
│   ├── main.py              # Point d'entrée FastAPI
│   ├── database.py          # Config SQLAlchemy
│   ├── models/              # Modèles SQLAlchemy
│   │   ├── candidate.py
│   │   ├── user.py
│   │   ├── cv_document.py
│   │   ├── job_offer.py
│   │   └── match.py
│   ├── routes/
│   │   └── cv.py            # Endpoints CV
│   ├── schemas/             # Schémas Pydantic
│   └── services/
│       └── extraction/      # Extracteurs PDF/DOCX/OCR
├── alembic/                 # Migrations BDD
├── tests/                   # Tests Pytest
├── .env.example
├── requirements.txt
└── README.md
```
