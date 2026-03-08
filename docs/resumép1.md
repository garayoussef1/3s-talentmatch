# Résumé Partie 1 — Projet 3S TalentMatch

**Projet** : 3S TalentMatch — Plateforme intelligente de matching CV / Offres d'emploi  
**Étudiant** : Youssef Gara — ESPRIT  
**Sprint** : Sprint 2  
**Périmètre Sprint 2** : OCR (EasyOCR), Pipeline NLP (spaCy), Stockage BDD (PostgreSQL), Tests unitaires (Pytest)  
**Date** : Mars 2026

---

## 1. Architecture globale du projet

Le projet est structuré en deux parties principales :

- **Backend** : API REST en Python avec FastAPI, base de données PostgreSQL, pipeline d'extraction et de parsing NLP
- **Frontend** : Application React (Vite) avec interface d'upload CV, affichage des résultats parsés, et liste des candidats

### Arborescence principale

```
3s-talentmatch/
├── backend/
│   ├── app/
│   │   ├── main.py                          → Point d'entrée FastAPI
│   │   ├── database.py                      → Connexion PostgreSQL (SQLAlchemy)
│   │   ├── models/                          → Modèles BDD (ORM)
│   │   ├── routes/                          → Endpoints API
│   │   ├── schemas/                         → Schémas Pydantic
│   │   └── services/
│   │       ├── extraction/                  → Extracteurs de texte (PDF, DOCX, OCR)
│   │       └── nlp/                         → Pipeline NLP complet
│   ├── tests/                               → Tests unitaires Pytest
│   ├── alembic/                             → Migrations BDD
│   ├── requirements.txt                     → Dépendances Python
│   └── pytest.ini                           → Configuration Pytest
├── frontend/
│   └── src/
│       ├── App.jsx                          → Routage React
│       ├── components/                      → Composants réutilisables
│       └── pages/                           → Pages de l'application
└── data/
    ├── cvs_raw/                             → CVs bruts pour tests
    └── cvs_processed/                       → CVs traités
```

---

## 2. Configuration et infrastructure

### 2.1 Point d'entrée de l'API  
Configuration de l'application FastAPI avec CORS, documentation Swagger, routes et tags  
(`backend/app/main.py`)

### 2.2 Connexion base de données  
Connexion PostgreSQL via SQLAlchemy sur le port 5433, avec session factory et dependency injection pour FastAPI  
(`backend/app/database.py`)

### 2.3 Migrations base de données  
Gestion des migrations avec Alembic pour créer et modifier les tables PostgreSQL  
(`backend/alembic/`, `backend/alembic.ini`)

### 2.4 Variables d'environnement  
Configuration de la connexion BDD et des paramètres d'exécution  
(`backend/.env`, `backend/.env.example`)

### 2.5 Dépendances Python  
Toutes les librairies nécessaires : FastAPI, SQLAlchemy, spaCy, EasyOCR, PyPDF, python-docx, pdf2image, Pillow, etc.  
(`backend/requirements.txt`)

---

## 3. Modèles de base de données (ORM)

### 3.1 Modèle Candidate  
Table `candidates` — stocke les informations personnelles extraites du CV (nom, email, téléphone, LinkedIn, GitHub), le texte brut, la méthode d'extraction utilisée, et les données parsées complètes en JSON  
(`backend/app/models/candidate.py`)

### 3.2 Modèle CVDocument  
Table `cv_documents` — fichiers CV uploadés liés à un candidat, avec statut de traitement (uploaded → extracted → parsed → error)  
(`backend/app/models/cv_document.py`)

### 3.3 Modèle JobOffer  
Table pour les offres d'emploi (prévu pour le matching Sprint 3)  
(`backend/app/models/job_offer.py`)

### 3.4 Modèle Match  
Table de matching candidat/offre (prévu Sprint 3)  
(`backend/app/models/match.py`)

### 3.5 Modèle User  
Table utilisateurs pour l'authentification  
(`backend/app/models/user.py`)

---

## 4. Routes API (Endpoints)

### 4.1 Upload CV — `POST /api/upload-cv`  
Endpoint principal qui reçoit un fichier CV (PDF, DOCX, PNG ou JPG), valide le format et la taille (max 10 Mo), extrait le texte via le bon extracteur, exécute le parsing NLP complet, et sauvegarde le candidat en base de données PostgreSQL  
(`backend/app/routes/cv.py`)

### 4.2 Liste des candidats — `GET /api/candidates`  
Retourne la liste paginée des candidats enregistrés en BDD, triés par date d'upload décroissante  
(`backend/app/routes/cv.py`)

### 4.3 Détail d'un candidat — `GET /api/candidates/{cv_id}`  
Retourne toutes les données extraites par le pipeline NLP pour un CV donné, y compris les données parsées complètes  
(`backend/app/routes/cv.py`)

### 4.4 Health Check — `GET /health`  
Endpoint de monitoring qui vérifie que l'API est opérationnelle  
(`backend/app/main.py`)

---

## 5. Couche extraction de texte

### 5.1 Extracteur unifié (Point d'entrée)  
Point d'entrée qui détecte automatiquement le format du fichier et route vers le bon extracteur : PDF textuel → PyPDF, PDF scanné → EasyOCR (fallback), DOCX → python-docx, Images → EasyOCR. C'est lui qui contient la logique de basculement automatique entre PyPDF et OCR  
(`backend/app/services/extraction/cv_extractor.py`)

### 5.2 Extracteur PDF (PyPDF)  
Extraction de texte pour les PDFs textuels. Si le texte extrait fait moins de 100 caractères, il renvoie `needs_ocr=True` pour signaler que le PDF est probablement scanné → l'extracteur unifié bascule alors sur l'OCR  
(`backend/app/services/extraction/pdf_extractor.py`)

### 5.3 Extracteur OCR (EasyOCR)  
Extraction de texte par reconnaissance optique de caractères. Supporte les images directes (PNG, JPG, TIFF, BMP, WEBP) et les PDFs scannés (conversion en images via pdf2image + Poppler, puis OCR page par page). Utilise EasyOCR en langues français et anglais avec fallback Surya OCR  
(`backend/app/services/extraction/ocr_extractor.py`)

### 5.4 Extracteur Word (python-docx)  
Extraction de texte depuis les fichiers DOCX en parcourant les paragraphes et tableaux du document Word  
(`backend/app/services/extraction/word_extractor.py`)

### 5.5 Logique de détection PDF scanné vs PDF textuel  
Quand un fichier `.pdf` arrive :  
1. PyPDF essaie d'extraire le texte (`pdf_extractor.py`)  
2. Si le texte < 100 caractères → `needs_ocr = True` (PDF scanné)  
3. L'extracteur unifié détecte `needs_ocr` et bascule sur EasyOCR (`cv_extractor.py`)  
4. La méthode finale est `pypdf+ocr` pour indiquer qu'on a d'abord essayé PyPDF puis utilisé l'OCR

---

## 6. Pipeline NLP (Parsing de CV)

### 6.1 Orchestrateur NLP (Parser principal)  
Point d'entrée du pipeline NLP v2.1.0 qui orchestre les 5 extracteurs dans l'ordre : contacts → entités nommées → compétences → formations → expériences. Chaque extracteur est encapsulé dans un try/except individuel pour qu'une erreur dans un module ne bloque pas les autres. Calcule un score de confiance global  
(`backend/app/services/nlp/nlp_parser.py`)

### 6.2 Extracteur de contacts  
Extrait l'email, téléphone (format tunisien XX XXX XXX, international), LinkedIn, GitHub, site web et adresse postale (18 villes tunisiennes). Détecte les labels associés (Tél, Mobile, Portable) et nettoie les URL  
(`backend/app/services/nlp/contact_extractor.py`)

### 6.3 Extracteur d'entités nommées (NER)  
Extraction du nom complet via 3 passes successives : (1) détection par préfixe (M., Mme, Dr.), (2) NER spaCy pour les entités PERSON, (3) analyse de la première ligne du CV. Filtre les faux positifs (noms de villes, entreprises) grâce à une liste de mots-clés de localisation  
(`backend/app/services/nlp/entity_extractor.py`)

### 6.4 Extracteur de compétences  
Base de données de 300+ compétences techniques organisées en catégories (langages, frameworks, bases de données, DevOps, etc.). Extraction en 4 phases : (1) isolation de la section Compétences, (2) recherche dans la section, (3) recherche dans le texte complet, (4) fusion et enrichissement. Protection contre les faux positifs pour les mots ambigus (C, R, Go) avec confirmation contextuelle  
(`backend/app/services/nlp/skills_extractor.py`)

### 6.5 Extracteur de formations  
Extraction des diplômes, spécialités, établissements, années, mentions. Supporte les formats français et internationaux (Bac+3/5/8), détection des formations en cours, et 7 pays de référence  
(`backend/app/services/nlp/formation_extractor.py`)

### 6.6 Extracteur d'expériences professionnelles  
Extraction des postes, entreprises, dates (début/fin/durée), villes, descriptions de missions. Supporte les mois en français avec et sans accents (février/fevrier, décembre/decembre), 28 villes tunisiennes, et environ 25 intitulés de postes FR/EN  
(`backend/app/services/nlp/experience_extractor.py`)

### 6.7 Configuration NLP centralisée  
Fichier de configuration centralisé regroupant : les patterns de sections de CV (formations, expériences, compétences, langues, projets, certifications), les mois FR/EN (avec variantes sans accents), les villes par pays (Tunisie 28 villes, France, Allemagne, UK, USA, Canada, Afrique du Nord, Golfe), les titres de postes courants, les titres honorifiques  
(`backend/app/services/nlp/config.py`)

### 6.8 Utilitaires NLP partagés  
Fonctions utilitaires réutilisables : `normalize_text()` (suppression accents + minuscules), `strip_accents()`, `extract_section()` (isolation d'une section de CV par patterns d'en-tête), `parse_date_str()` (parsing de dates FR/EN), `clean_text_block()`, `is_likely_name()`  
(`backend/app/services/nlp/utils.py`)

---

## 7. Structure des données parsées (sortie NLP)

Le résultat du parsing NLP retourne un JSON structuré :

```json
{
  "identite": { "nom_complet": "..." },
  "contacts": { "email": "...", "telephone": "...", "linkedin": "...", "github": "...", "website": "...", "address": "..." },
  "competences": [{ "name": "Python", "category": "langages", "source": "section", "years": null, "level": "..." }],
  "formations": [{ "diplome": "...", "specialite": "...", "etablissement": "...", "annee": 2025, "en_cours": false }],
  "experiences": [{ "poste": "...", "entreprise": "...", "date_debut": "...", "date_fin": "...", "duree_mois": 24, "ville": "...", "description": "..." }],
  "langues": [{ "langue": "...", "niveau": "..." }],
  "competences_par_categorie": { "langages": ["Python", "JavaScript"], "frameworks_web": ["FastAPI", "React"] },
  "metadata": { "parser_version": "2.1.0", "confidence_score": 0.85, "annees_experience_totales": 2.0, "niveau_seniorite": "Junior" },
  "errors": []
}
```

Cette structure est produite par (`backend/app/services/nlp/nlp_parser.py`) et stockée en JSON dans la colonne `parsed_data` de la table `candidates` (`backend/app/models/candidate.py`)

---

## 8. Frontend React

### 8.1 Application principale  
Routage React avec 3 pages : Accueil, Upload CV, Liste des candidats  
(`frontend/src/App.jsx`)

### 8.2 Barre de navigation  
Composant de navigation entre les pages  
(`frontend/src/components/Navbar.jsx`, `frontend/src/components/Navbar.css`)

### 8.3 Page d'accueil  
Page d'accueil du projet avec présentation  
(`frontend/src/pages/Home.jsx`, `frontend/src/pages/Home.css`)

### 8.4 Page Upload CV  
Interface d'upload avec drag-and-drop, accepte les formats PDF, DOCX, PNG, JPG (max 10 Mo). Affiche les résultats parsés avec onglets (Résumé, Compétences, Expériences, Formations, Texte brut) et barre de métadonnées (score de confiance, nombre de compétences, séniorité)  
(`frontend/src/pages/UploadCV.jsx`, `frontend/src/pages/UploadCV.css`)

### 8.5 Page Liste des candidats  
Affiche la liste des candidats stockés en BDD avec leurs informations extraites  
(`frontend/src/pages/Candidates.jsx`, `frontend/src/pages/Candidates.css`)

---

## 9. Améliorations NLP réalisées (Sprint 2)

### 9.1 (P2) Isolation de section pour les compétences  
Les compétences ne sont plus extraites de tout le texte mais d'abord de la section "Compétences" du CV, ce qui élimine les faux positifs (ex: "Docker" dans une phrase de description qui n'est pas une compétence)  
(`backend/app/services/nlp/skills_extractor.py`)

### 9.2 (P2) Protection contre les faux positifs (mots ambigus)  
Les mots courts ambigus comme C, R, Go nécessitent une confirmation contextuelle (ex: "langage C", "programmation Go") pour éviter les faux positifs  
(`backend/app/services/nlp/skills_extractor.py`)

### 9.3 (P3) Support des mois sans accents  
Les mois français comme "février", "décembre", "août" sont aussi reconnus dans leurs formes sans accents : "fevrier", "decembre", "aout" — important pour les textes OCR qui perdent souvent les accents  
(`backend/app/services/nlp/experience_extractor.py`, `backend/app/services/nlp/config.py`)

### 9.4 (P4) 28 villes tunisiennes  
Ajout de 28 villes tunisiennes pour la détection des lieux dans les expériences et contacts : Tunis, Sfax, Sousse, Ariana, Ben Arous, Nabeul, Monastir, Bizerte, Gabès, Kairouan, Médenine, Tozeur, etc.  
(`backend/app/services/nlp/config.py`, `backend/app/services/nlp/experience_extractor.py`, `backend/app/services/nlp/contact_extractor.py`)

### 9.5 (P5) ~25 nouveaux intitulés de postes FR/EN  
Ajout de titres de postes courants en français et anglais pour améliorer la détection dans les expériences : Chef de projet, Architecte logiciel, Data Scientist, Scrum Master, Product Owner, etc.  
(`backend/app/services/nlp/experience_extractor.py`, `backend/app/services/nlp/config.py`)

### 9.6 (P6) Logging structuré  
Ajout de logs détaillés dans chaque extracteur pour le suivi et le debug  
(`backend/app/services/nlp/entity_extractor.py`, `backend/app/services/nlp/nlp_parser.py`)

### 9.7 (P7) Gestion d'erreurs robuste  
Chaque extracteur est encapsulé dans un try/except individuel dans le pipeline. Si un extracteur échoue, les autres continuent. Les erreurs sont collectées dans une liste `errors` dans les données parsées  
(`backend/app/services/nlp/nlp_parser.py`)

---

## 10. Support upload PNG/JPG (correction)

### 10.1 Problème identifié  
Les fichiers PNG et JPG étaient rejetés par l'API avec le message "Format non supporté" alors que l'extracteur OCR les supportait déjà. La cause : la route API ne listait que PDF et DOCX dans les extensions autorisées

### 10.2 Correction backend  
Ajout de `.png`, `.jpg`, `.jpeg` dans `ALLOWED_EXTENSIONS`, mise à jour du message d'erreur et de la documentation Swagger  
(`backend/app/routes/cv.py`)

### 10.3 Correction frontend  
Mise à jour de l'attribut `accept` du champ file pour accepter PNG/JPG, et du texte "Formats acceptés"  
(`frontend/src/pages/UploadCV.jsx`)

### 10.4 Mise à jour documentation API  
Description Swagger mise à jour pour mentionner les formats image  
(`backend/app/main.py`)

---

## 11. Tests unitaires

### 11.1 Tests Sprint 2 (50 tests)  
Suite complète de 50 tests couvrant : faux positifs compétences (8 tests), isolation de section (4), années d'expérience (2), mois sans accents (3), villes tunisiennes (2), entités nommées (6), contacts (8), gestion d'erreurs pipeline (3), configuration (6), utilitaires (8)  
(`backend/tests/test_sprint2_unit.py`)

### 11.2 Tests US-017 (extraction de texte)  
Tests pour l'extraction de texte depuis PDF, DOCX et images  
(`backend/tests/test_us017_extraction.py`)

### 11.3 Tests US-018 (validation upload)  
Tests de validation : fichier vide, format non supporté, taille maximale, formats acceptés  
(`backend/tests/test_us018_validation.py`)

### 11.4 Tests API endpoints  
Tests des endpoints REST : upload, liste des candidats, détail  
(`backend/tests/test_api_endpoints.py`)

### 11.5 Tests pipeline complet  
Tests end-to-end du pipeline NLP complet sur un CV avec vérification de tous les champs extraits  
(`backend/tests/test_pipeline_full.py`)

### 11.6 Tests extracteur de contacts  
Tests spécifiques pour l'extraction d'emails, téléphones, LinkedIn, GitHub  
(`backend/tests/test_nlp_contact_extractor.py`)

### 11.7 Tests extracteur d'entités  
Tests spécifiques pour l'extraction du nom complet  
(`backend/tests/test_nlp_entity_extractor.py`)

### 11.8 Tests qualité d'extraction  
Tests de qualité d'extraction incluant performance (temps d'exécution)  
(`backend/tests/test_extraction_quality.py`)

### 11.9 Tests OCR pipeline  
Tests du pipeline OCR : images, PDFs scannés, formats non supportés  
(`backend/tests/test_ocr_extractor_pipeline.py`)

### 11.10 Diagnostic OCR  
Script de diagnostic pour vérifier que l'OCR fonctionne correctement sur PDF scanné et image PNG  
(`backend/tests/test_ocr_diagnostic.py`)

### 11.11 Configuration Pytest  
Configuration pour l'auto-découverte des fichiers de tests (`python_files = test_*.py`)  
(`backend/pytest.ini`)

### 11.12 Fixtures partagées  
Fixtures Pytest réutilisables entre tous les tests  
(`backend/tests/conftest.py`)

**Résultat total : 110/110 tests passent** (hors scripts standalone)

---

## 12. Outils et technologies utilisés

| Catégorie | Technologie | Rôle |
|---|---|---|
| Backend | Python 3.11, FastAPI | API REST |
| BDD | PostgreSQL 5433, SQLAlchemy, Alembic | Stockage et migrations |
| NLP | spaCy (fr_core_news_md) | Traitement du langage naturel |
| OCR | EasyOCR, pdf2image, Poppler | Reconnaissance optique de caractères |
| PDF | PyPDF | Extraction texte PDF textuels |
| DOCX | python-docx | Extraction texte Word |
| Frontend | React, Vite, Tailwind CSS | Interface utilisateur |
| Tests | Pytest | Tests unitaires |
| Versioning | Git | Contrôle de version |

---

## 13. Flux complet d'un upload CV

1. L'utilisateur upload un fichier via le frontend (`frontend/src/pages/UploadCV.jsx`)
2. Le fichier est envoyé en POST à `/api/upload-cv` (`backend/app/routes/cv.py`)
3. Validation du format (PDF/DOCX/PNG/JPG) et de la taille (< 10 Mo)
4. Le fichier est sauvegardé temporairement et envoyé à l'extracteur unifié (`backend/app/services/extraction/cv_extractor.py`)
5. Selon le format :
   - PDF textuel → PyPDF extrait le texte (`backend/app/services/extraction/pdf_extractor.py`)
   - PDF scanné → PyPDF échoue (< 100 chars) → EasyOCR prend le relais (`backend/app/services/extraction/ocr_extractor.py`)
   - Image → EasyOCR directement (`backend/app/services/extraction/ocr_extractor.py`)
   - DOCX → python-docx (`backend/app/services/extraction/word_extractor.py`)
6. Le texte brut est envoyé au pipeline NLP (`backend/app/services/nlp/nlp_parser.py`)
7. Les 5 extracteurs NLP s'exécutent dans l'ordre : contacts, entités, compétences, formations, expériences
8. Les données parsées sont stockées en BDD PostgreSQL dans la table `candidates` (`backend/app/models/candidate.py`)
9. Le frontend affiche les résultats avec onglets et métadonnées (`frontend/src/pages/UploadCV.jsx`)
10. Les candidats sont consultables via la page Candidats (`frontend/src/pages/Candidates.jsx`)
