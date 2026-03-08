# Sprint 2 - Pipeline NLP : Parsing et Structuration CVs

**Date:** 28 février 2026  
**Durée prévue:** Mois 2 (4 semaines)  
**Phase:** 2 / 5  

---

## 📋 Contexte

### ✅ Sprint 1 Terminé
- Extraction texte multi-format (PDF, DOCX, OCR) ✅
- Upload de CVs via API FastAPI ✅
- Base de données PostgreSQL opérationnelle ✅
- Frontend React basique ✅
- Tests qualité extraction (44 tests passing) ✅

### 🎯 Objectifs Sprint 2
D'après le CDC (Phase 2 - Mois 2):
> **Pipeline NLP : parsing et structuration des CV en JSON**

**Technologies:**
- **spaCy** (fr_core_news_md) : NER (reconnaissance entités nommées)
- **Extraction structurée** : Nom, organisations, dates, compétences, formation

---

## 📊 User Stories Proposées - Sprint 2

### Epic 4 : Pipeline NLP - Parsing Structuré

| ID | User Story | Story Points | Priorité |
|----|-----------|--------------|----------|
| **US-033** | Installation et configuration spaCy + modèle français | 3 | P0 |
| **US-034** | Service NLP : extraction nom/prénom (NER PERSON) | 5 | P0 |
| **US-035** | Service NLP : extraction email, téléphone (regex) | 3 | P0 |
| **US-036** | Service NLP : extraction organisations (NER ORG) | 5 | P0 |
| **US-037** | Service NLP : extraction dates (NER DATE) | 3 | P1 |
| **US-038** | Service NLP : extraction compétences (patterns) | 8 | P0 |
| **US-039** | Service NLP : extraction formation/diplômes | 5 | P1 |
| **US-040** | Service NLP : extraction expériences professionnelles | 8 | P1 |
| **US-041** | Agrégateur : structurer en JSON normalisé | 5 | P0 |
| **US-042** | API endpoint : POST /cvs/{id}/parse | 3 | P0 |
| **US-043** | Tests unitaires pipeline NLP | 5 | P1 |
| **US-044** | Tests E2E : upload → extraction → parse → JSON | 5 | P1 |
| **US-045** | Documentation pipeline NLP | 3 | P2 |

**Total:** ~61 story points

---

## 🏗️ Architecture Technique

### Structure Backend Proposée

```
backend/
├── app/
│   ├── services/
│   │   ├── extraction/          # ✅ Sprint 1
│   │   │   ├── cv_extractor.py
│   │   │   ├── pdf_extractor.py
│   │   │   ├── word_extractor.py
│   │   │   └── ocr_extractor.py
│   │   │
│   │   └── nlp/                 # 🆕 Sprint 2
│   │       ├── __init__.py
│   │       ├── nlp_parser.py          # Orchestrateur principal
│   │       ├── entity_extractor.py    # Nom, orgs, dates (spaCy NER)
│   │       ├── contact_extractor.py   # Email, tél (regex)
│   │       ├── skills_extractor.py    # Compétences techniques
│   │       ├── education_extractor.py # Formation, diplômes
│   │       ├── experience_extractor.py # Expériences professionnelles
│   │       └── json_builder.py        # Construction JSON normalisé
│   │
│   ├── schemas/
│   │   ├── cv_schemas.py        # ✅ Existant
│   │   └── parsed_cv_schemas.py # 🆕 Sprint 2 - Schéma JSON structuré
│   │
│   └── routes/
│       └── cv_routes.py         # Ajouter endpoint /cvs/{id}/parse
│
├── tests/
│   └── test_nlp_pipeline.py     # 🆕 Sprint 2
│
└── requirements.txt             # Ajouter spaCy + fr_core_news_md
```

---

## 📝 Format JSON Cible

```json
{
  "candidate_id": "uuid",
  "raw_text": "texte extrait complet...",
  "parsed_data": {
    "personal_info": {
      "full_name": "Marie Martin",
      "email": "marie.martin@example.com",
      "phone": "+33 6 12 34 56 78",
      "linkedin": "linkedin.com/in/marie-martin"
    },
    "skills": [
      {"name": "Python", "category": "language"},
      {"name": "FastAPI", "category": "framework"},
      {"name": "Docker", "category": "devops"}
    ],
    "education": [
      {
        "degree": "Diplôme d'Ingénieur",
        "institution": "École Centrale",
        "year": 2019,
        "field": "Informatique"
      }
    ],
    "experience": [
      {
        "title": "Ingénieure DevOps Senior",
        "company": "TechCorp",
        "start_date": "2021",
        "end_date": "Present",
        "location": "Paris, France",
        "description": "Mise en place pipeline CI/CD..."
      }
    ],
    "languages": [
      {"name": "Français", "level": "Native"},
      {"name": "Anglais", "level": "Fluent"}
    ]
  },
  "metadata": {
    "parsed_at": "2026-02-28T10:30:00Z",
    "parser_version": "2.0.0",
    "confidence_score": 0.85
  }
}
```

---

## 🚀 Plan d'Action - Sprint 2

### Semaine 1 : Setup NLP
- [ ] **US-033:** Installer spaCy + modèle français
  ```bash
  pip install spacy
  python -m spacy download fr_core_news_md
  ```
- [ ] **US-034:** Service extraction nom/prénom
- [ ] **US-035:** Service extraction email/téléphone
- [ ] Tests unitaires extraction entités basiques

### Semaine 2 : Extraction Compétences & Formation
- [ ] **US-038:** Extraction compétences (dictionnaire + patterns)
- [ ] **US-039:** Extraction formation/diplômes
- [ ] **US-036:** Extraction organisations
- [ ] Tests sur CVs réels

### Semaine 3 : Expériences & Agrégation JSON
- [ ] **US-040:** Extraction expériences professionnelles
- [ ] **US-037:** Extraction dates (périodes)
- [ ] **US-041:** Agrégateur JSON normalisé
- [ ] Schéma Pydantic pour validation

### Semaine 4 : API, Tests & Documentation
- [ ] **US-042:** Endpoint API `/cvs/{id}/parse`
- [ ] **US-043/044:** Tests unitaires + E2E
- [ ] **US-045:** Documentation
- [ ] Démo Sprint 2

---

## 🛠️ Dépendances Techniques

### À Installer
```bash
# Dans requirements.txt
spacy>=3.7.0
fr-core-news-md @ https://github.com/explosion/spacy-models/releases/download/fr_core_news_md-3.7.0/fr_core_news_md-3.7.0-py3-none-any.whl

# Optionnel pour matching futur (Sprint 4)
sentence-transformers>=2.2.0  # CamemBERT embeddings
scikit-learn>=1.3.0           # Similarité cosinus
```

### Commandes
```bash
# Activer venv
.\.venv\Scripts\activate

# Installer spaCy
pip install spacy

# Télécharger modèle français
python -m spacy download fr_core_news_md

# Vérifier installation
python -c "import spacy; nlp = spacy.load('fr_core_news_md'); print('✅ spaCy OK')"
```

---

## 📊 Métriques de Succès Sprint 2

### Critères d'Acceptation
- ✅ Extraction nom/prénom : **> 90% précision**
- ✅ Extraction email/téléphone : **> 95% précision**
- ✅ Extraction compétences : **> 70% rappel**
- ✅ JSON valide et conforme au schéma : **100%**
- ✅ Temps parsing < 5s par CV
- ✅ Tests : **> 80% coverage** sur module NLP

### Tests de Qualité
Utiliser les CVs de test créés au Sprint 1:
- `test_pdf_text.pdf` (Jean Dupont)
- `test_word.docx` (Marie Martin)
- `cv_scanne_test.pdf` (Youssef Test)

---

## 🔗 Intégration avec Sprint 1

### Workflow Complet
```
1. Upload CV → API /cvs/upload
2. Extraction texte → CVExtractor (Sprint 1 ✅)
3. Parsing NLP → NLPParser (Sprint 2 🆕)
4. JSON structuré → Base de données
5. Affichage → Frontend React
```

### Endpoints API
```
Existants (Sprint 1):
- POST   /cvs/upload          ✅
- GET    /cvs/                ✅
- GET    /cvs/{id}            ✅

Nouveaux (Sprint 2):
- POST   /cvs/{id}/parse      🆕  # Déclencher parsing NLP
- GET    /cvs/{id}/parsed     🆕  # Récupérer JSON structuré
- GET    /cvs/{id}/skills     🆕  # Liste compétences extraites
```

---

## ⚠️ Défis Anticipés

### 1. Variabilité des CV
**Problème:** Pas de format standard  
**Solution:** 
- Patterns flexibles (regex + spaCy)
- Dictionnaire de compétences techniques
- Fallback : extraction basique si NER échoue

### 2. Performance spaCy
**Problème:** Traitement peut être lent sur gros CV  
**Solution:**
- Limiter taille texte analysé (premiers 5000 caractères)
- Processing asynchrone (Celery/RQ si nécessaire)
- Cache résultats parsing

### 3. Précision NER sur CVs
**Problème:** Modèle spaCy entraîné sur texte général, pas CVs  
**Solution:**
- Post-traitement règles métier
- Validation manuelle sur échantillon
- Fine-tuning modèle (Sprint 3+ si besoin)

---

## 📚 Ressources

### Documentation
- [spaCy Docs](https://spacy.io/usage)
- [spaCy NER Guide](https://spacy.io/usage/linguistic-features#named-entities)
- [Regex Python](https://docs.python.org/3/howto/regex.html)

### Inspiration Projets
- [Resume Parser (GitHub)](https://github.com/OmkarPathak/pyresparser)
- [CV Parser spaCy](https://github.com/ahmedafifi86/CVParser)

---

## 🎯 Démo Sprint 2 (Objectif)

### Scénario de Démo
1. **Upload CV** via frontend
2. **Extraction texte** automatique (Sprint 1)
3. **Clic bouton "Parser CV"** → déclenche NLP
4. **Affichage JSON structuré** dans interface
5. **Visualisation champs extraits:**
   - Nom, email, téléphone
   - Liste compétences avec badges
   - Timeline expériences
   - Formation

---

## ✅ Checklist Démarrage Sprint 2

**Avant de commencer:**
- [x] Sprint 1 validé et documenté
- [x] Backend en état propre (44 tests passing)
- [x] CVs de test disponibles
- [x] Frontend opérationnel sur port 3000
- [ ] Installer spaCy + modèle français
- [ ] Créer structure dossier `services/nlp/`
- [ ] Définir schéma JSON cible (Pydantic)
- [ ] Premier test NLP basique

**Prêt à démarrer ?**
```bash
# Vérifier état actuel
pytest backend/tests/ -v

# Créer branche Sprint 2
git checkout -b sprint2-nlp-pipeline

# Installer spaCy
pip install spacy
python -m spacy download fr_core_news_md

# Let's go! 🚀
```

---

**Note:** Ce document sera affiné au fur et à mesure du Sprint 2 avec les détails d'implémentation et les résultats obtenus.
