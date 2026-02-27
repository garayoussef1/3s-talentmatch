# Scénario de Démonstration — 3S TalentMatch

**Date** : Sprint 1 Review  
**Durée estimée** : 10–15 minutes  
**Présenté par** : Youssef Gara  

---

## Prérequis avant la démo

Vérifier que les services sont démarrés :

```powershell
# 1. Backend FastAPI
cd backend
uvicorn app.main:app --reload --port 8000

# 2. Frontend React
cd frontend
npm run dev
```

Vérifier les URLs :
- Backend API : http://localhost:8000
- Frontend    : http://localhost:3000
- Swagger     : http://localhost:8000/docs

---

## Étape 1 — Présenter l'architecture (2 min)

**Message** :  
> "3S TalentMatch est une plateforme de matching CV/offres d'emploi. Le Sprint 1 couvre l'upload et l'extraction automatique de CVs."

Montrer rapidement :
- Dossier `backend/` → FastAPI + PostgreSQL
- Dossier `frontend/` → React + Vite
- Schéma : `Navigateur → React (port 3000) → FastAPI (port 8000) → PostgreSQL (port 5433)`

---

## Étape 2 — Démonstration Swagger (3 min)

1. Ouvrir http://localhost:8000/docs
2. Montrer les **2 endpoints documentés** :
   - `POST /api/upload-cv` — description complète, exemple de réponse, codes d'erreur 400/413/500
   - `GET /api/candidates` — pagination, exemple de réponse
3. Tester `GET /health` directement dans Swagger → cliquer **Try it out** → **Execute**

---

## Étape 3 — Upload d'un CV PDF (3 min)

1. Ouvrir http://localhost:3000/upload
2. **Glisser-déposer** un fichier PDF dans la zone de dépôt
3. Observer le **spinner animé** pendant le traitement
4. Montrer la **carte résultat** :
   - `cv_id` UUID unique
   - Méthode d'extraction (`pypdf` ou `ocr`)
   - Aperçu du texte extrait (300 premiers caractères)

**Message** :  
> "Le système détecte automatiquement si le PDF est textuel (PyPDF) ou scanné (OCR via EasyOCR)."

---

## Étape 4 — Upload d'un CV Word (1 min)

1. Uploader un fichier `.docx`
2. Montrer que la méthode est `docx` (python-docx)
3. Tester un format invalide (ex: `.jpg`) → affichage message d'erreur rouge

---

## Étape 5 — Consulter la liste des candidats (2 min)

1. Naviguer vers http://localhost:3000/candidates
2. Montrer le **tableau des candidats** avec les CVs uploadés
3. Retourner à la **page d'accueil** → statistique "CVs uploadés" mise à jour en temps réel

---

## Étape 6 — Résultats des tests (2 min)

Ouvrir un terminal et exécuter :

```powershell
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

Montrer :
- **33 tests passés**
- **Couverture : 82%** (objectif > 70% ✅)
- Tests US-016 (validation), US-017 (extraction), US-018 (endpoints), US-032 (E2E)

---

## Étape 7 — Base de données PostgreSQL (1 min)

Ouvrir pgAdmin ou exécuter :

```powershell
cd backend
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.database import SessionLocal
from app.models.candidate import Candidate
db = SessionLocal()
print('Candidats en BDD:', db.query(Candidate).count())
db.close()
"
```

Montrer le nombre de candidats stockés en base.

---

## Récapitulatif Sprint 1

| Catégorie | Résultat |
|---|---|
| Story points livrés | ~90 pts |
| Tables PostgreSQL | 5 tables (candidates, users, cv_documents, job_offers, matches) |
| Endpoints API | 3 (health, upload-cv, candidates) |
| Tests Pytest | 33 tests · couverture 82% |
| Pages frontend | 3 (Home, Upload, Candidats) |
| Git commits | 5 commits sur `master` |

---

## Questions fréquentes

**Q: Comment gérez-vous les PDFs scannés ?**  
R: Détection automatique via `needs_ocr` dans PDFExtractor. Si le texte extrait < 100 caractères, on bascule sur EasyOCR.

**Q: La base de données est-elle sécurisée ?**  
R: Le mot de passe est dans `.env` (hors git). Sprint 2 ajoutera l'authentification JWT.

**Q: Quels sont les prochains sprints ?**  
R: Sprint 2 → parsing NLP (spaCy) + matching CV/offres. Sprint 3 → authentification + interface complète.
