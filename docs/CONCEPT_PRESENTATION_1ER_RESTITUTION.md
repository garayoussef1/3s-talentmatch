# 📊 Concept de Présentation - 1ère Restitution
## 3S TalentMatch - Plateforme de Matching CV/Offres

**Durée totale** : ~15 minutes  
**Date** : À déterminer avec l'expert  
**Public** : Jury + Expert + Encadrant  

---

## Structure générale (5 blocs)

| Bloc | Titre | Durée | Slides |
|------|-------|-------|--------|
| 1 | **Introduction** | 3 min | 1-3 |
| 2 | **Analyse des besoins** | 2 min | 4-5 |
| 3 | **Architectures** | 4 min | 6-10 |
| 4 | **Avancement actuel** | 4 min | 11-13 |
| 5 | **Conclusion & perspectives** | 2 min | 14-15 |

---

# 📌 BLOC 1 : INTRODUCTION (3 min) — Slides 1-3

## Slide 1 : Couverture
```
┌─────────────────────────────────────┐
│                                     │
│    3S TalentMatch                   │
│    Plateforme de Matching           │
│    CV / Offres d'Emploi             │
│                                     │
│    Youssef Gara                     │
│    PFE ESPRIT 2025-2026             │
│    Expert : [À compléter]           │
│                                     │
└─────────────────────────────────────┘
```
**Notes**: Sourire, présentation sobre, afficher le logo 3S si disponible.

---

## Slide 2 : Contexte et Problématique

### Titre
**Le Recrutement : Défi Métier pour les Cabinets RH**

### Contenu
**Problématiques identifiées :**
- 📄 Volume massif de CVs à traiter manuellement
- ⏱️ Temps consacré au tri et pré-qualification très important
- ❌ Risque d'erreurs humaines (oublis, fatigue)
- 🔍 Manque de traçabilité et d'objectivité

**Étude de l'existant :**
- Outils actuels : tableurs Excel, tri manuel
- Processus : reçeption email → tri → archivage
- Limite : pas d'automatisation, pas de scoring

**Solution proposée :**
- 🤖 **TalentMatch** : plateforme intelligente
- ✅ Extraction automatique de CVs (multi-format)
- ✅ Matching sémantique CV ↔ Offre
- ✅ Rapport de recommandation
- ✅ Interface intuitive pour recruteurs

**Notes** (15 sec) : Décrire rapidement le pain point réel.

---

## Slide 3 : Objectifs du Projet

### Titre
**Objectifs Fonctionnels et Techniques**

### Contenu

**Fonctionnels :**
1. Upload et extraction de CVs (PDF, DOCX, images OCR)
2. Création et gestion d'offres d'emploi
3. Matching candidat-offre avec score
4. Génération de rapports de recommandation
5. Authentification et gestion des droits

**Non-fonctionnels :**
- 📱 Interface responsive (desktop/mobile)
- ⚡ Performance : matching < 5 sec par candidat
- 🔐 Sécurité : JWT, chiffrement données sensibles
- 📊 Traçabilité : logs de tous les matchings
- 🛡️ RGPD : consentement, anonymisation, droit à l'oubli

**Notes** (15 sec) : Lister rapidement, pas de détail technique ici.

---

# 📋 BLOC 2 : ANALYSE DES BESOINS (2 min) — Slides 4-5

## Slide 4 : Besoins Métier Détaillés

### Titre
**Cas d'Usage Principaux**

### Contenu (Format : Cas d'usage)

```
┌─────────────────────────────────────────┐
│  Acteur Principal : Recruteur           │
├─────────────────────────────────────────┤
│ UC1 : Upload d'un CV                    │
│   - Télécharger PDF/DOCX/JPG            │
│   - Système extrait automatiquement      │
│   - Candidat créé en base               │
│                                         │
│ UC2 : Créer une Offre                   │
│   - Saisir titre, description, skills   │
│   - Sauvegarder en base                 │
│                                         │
│ UC3 : Matcher un candidat à une offre   │
│   - Visualiser score et recommandation  │
│   - Générer rapport détaillé            │
│   - Exporter en PDF                     │
│                                         │
│ UC4 : Consulter l'historique            │
│   - Voir tous les matchings passés      │
│   - Télécharger rapports antérieurs     │
└─────────────────────────────────────────┘
```

**Notes** (20 sec) : Montrer les 4 cas d'usage clés.

---

## Slide 5 : Contraintes et Hypothèses

### Titre
**Hypothèses, Contraintes, Risques**

### Contenu

**Hypothèses :**
- ✅ CVs en français ou anglais
- ✅ Données sensibles (nom, email) à protéger
- ✅ Modèle d'IA suffisant pour POC

**Contraintes :**
- 🖥️ Pas de GPU disponible → solution CPU-first
- 📊 Dataset limité pour ML → sandbox non persistante
- 🔌 Base PostgreSQL locale
- 🌐 Pas de dépendances cloud tierces

**Risques et mitigations :**
| Risque | Impact | Mitigation |
|--------|--------|-----------|
| OCR imprécis | Extraction partielle | Validations + fallback manuel |
| Temps matching lent | UX dégradée | Cache, optimisation BERT |
| Modèle peu fiable | Mauvais scores | Heuristique robuste + sandbox IA |

**Notes** (15 sec) : Montrer qu'on a pensé aux limites et solutions.

---

# 🏗️ BLOC 3 : ARCHITECTURES (4 min) — Slides 6-10

## Slide 6 : Architecture Générale (High-Level)

### Titre
**Architecture Système**

### Contenu (Diagramme)
```
┌──────────────────────────────────────────────────────┐
│                  Frontend (React)                     │
│              Port 3000 - Vite + Tailwind             │
│                                                      │
│  • Upload CV        • Offres        • Matchings     │
│  • Drag & Drop      • Candidats     • Rapports      │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP(S) + JWT
                   ↓
┌──────────────────────────────────────────────────────┐
│               Backend API (FastAPI)                   │
│           Port 8000 - uvicorn                        │
│                                                      │
│  • /api/upload-cv           • /api/match            │
│  • /api/candidates          • /api/candidates/{id}  │
│  • /api/offers              • /api/auth             │
│  • /api/match-sandbox/{id}  • /api/reports         │
└──────────────────┬───────────────────────────────────┘
                   │ SQLAlchemy ORM
                   ↓
┌──────────────────────────────────────────────────────┐
│         PostgreSQL 16 - Base de Données              │
│                                                      │
│  • Candidates        • Offers      • MatchLogs      │
│  • Users             • CVDocuments • Consents       │
└──────────────────────────────────────────────────────┘
```

**Notes** (20 sec) : Montrer la séparation frontend/backend/DB.

---

## Slide 7 : Architecture Backend - Services

### Titre
**Microservices Backend**

### Contenu (Arborescence)
```
Backend (FastAPI)
│
├── 📂 Extraction
│   ├── PDF Extractor (pypdf)
│   ├── DOCX Extractor (python-docx)
│   └── OCR Engine (EasyOCR, Tesseract)
│
├── 📂 NLP & Parsing
│   ├── Entity Extractor (spaCy)
│   ├── Skill Detector
│   └── Experience Parser
│
├── 📂 Matching Engine
│   ├── RapidFuzz Scorer (heuristique)
│   ├── ML Scorer (LogReg)
│   └── BERT Scorer (IA sémantique) ← NOUVEAU
│
├── 📂 Persistence
│   ├── SQLAlchemy Models
│   ├── Alembic Migrations
│   └── PostgreSQL Connection
│
└── 📂 Routes API
    ├── /candidates (GET, POST, PATCH)
    ├── /offers (GET, POST)
    ├── /match (POST) - production
    └── /match-sandbox (POST) - IA
```

**Notes** (25 sec) : Décrire les 5 groupes, mettre l'accent sur la structure modulaire.

---

## Slide 8 : Matching Engine - Détail

### Titre
**Système de Matching Hybride**

### Contenu

**3 Moteurs en parallèle :**

1️⃣ **Heuristique (Production)**
   - RapidFuzz : fuzzy matching skills
   - Comparaison : expérience, diplômes, localisation
   - Poids : Skills 45% + Exp 25% + Edu 20% + Loc 10%
   - ✅ Rapide, expliquable, sans dépendance IA

2️⃣ **ML Classique (Sandbox)**
   - Logistic Regression (6 samples)
   - Features : exp_score, edu_score, location
   - ⚠️ POC technique, manque données réelles

3️⃣ **BERT Sémantique (Sandbox - NOUVEAU)**
   - `paraphrase-multilingual-MiniLM-L12-v2`
   - Cosine similarity embeddings
   - Détection d'incohérences CV vs skills déclarées
   - 🤖 Comprend sens : "Python engineer" = "développeur Python"
   - 🌐 Multilingue natif (FR, EN, 50+ langues)

**Formule BERT :**
```
Score = 0.50 × bert_semantic
      + 0.30 × bert_skills  
      + 0.20 × base_score
      - penalty_incoherences
```

**Notes** (30 sec) : Expliquer la progression heuristique → ML → BERT, souligner multilingue.

---

## Slide 9 : Stack Technologique

### Titre
**Technologies Utilisées**

### Contenu (Tableau)

| Couche | Stack | Détails |
|--------|-------|---------|
| **Frontend** | React 18 + Vite 5 | UI rapide, bundle < 500KB |
| | Tailwind CSS 3 | Utility-first CSS |
| | Axios + React Router | HTTP client + routing SPA |
| **Backend** | FastAPI | Framework API performant |
| | SQLAlchemy 2 | ORM moderne, migrations Alembic |
| | PostgreSQL 16 | Base relationnelle robuste |
| **Extraction** | PyPDF, python-docx | PDF, DOCX parsing |
| | EasyOCR, Tesseract | OCR multilingue |
| **NLP/IA** | spaCy, SentenceTransformers | Embeddings, entities, matching |
| | RapidFuzz | Fuzzy string matching |
| **Tests** | pytest | Couverture unitaire |
| **Auth** | JWT + bcrypt | Authentification sécurisée |
| **Deployment** | Docker (optionnel) | Containerisation |

**Notes** (20 sec) : Survol rapide, pas besoin de détail chaque ligne.

---

## Slide 10 : Diagramme Flux de Données

### Titre
**Pipeline Principal : Upload → Matching → Rapport**

### Contenu (Flux)
```
┌─────────────────┐
│  Recruteur      │
│  Upload CV      │
└────────┬────────┘
         │ (PDF, DOCX, JPG)
         ↓
┌──────────────────────┐
│  1. Extraction       │
│  ├─ PDF Parser       │
│  ├─ OCR (si image)   │
│  └─ Texte brut → DB  │
└────────┬─────────────┘
         │
         ↓
┌──────────────────────┐
│  2. NLP Enrichment   │
│  ├─ Entity Extract   │
│  ├─ Skill Detect     │
│  └─ Exp Parse → DB   │
└────────┬─────────────┘
         │
    ┌────┴────┐
    │ Offre ? │  (recruteur saisit offre)
    └────┬────┘
         │
         ↓
┌──────────────────────────┐
│  3. Matching (3 modes)   │
│  ├─ Heuristique (prod)   │
│  ├─ ML (sandbox)         │
│  └─ BERT IA (sandbox)    │
└────────┬─────────────────┘
         │
         ↓
┌──────────────────────────┐
│  4. Rapport Généré       │
│  ├─ Score final          │
│  ├─ Top skills match     │
│  ├─ Recommandation       │
│  └─ Incoherences détectées
└──────────────────────────┘
```

**Notes** (25 sec) : Montrer le chemin complet d'un CV jusqu'au rapport final.

---

# ✅ BLOC 4 : AVANCEMENT ACTUEL (4 min) — Slides 11-13

## Slide 11 : Fonctionnalités Implémentées

### Titre
**État d'Avancement v1.0 (MVP)**

### Contenu

### ✅ COMPLÉTÉ (Prêt à la démo)

1. **Backend API**
   - ✅ Endpoints CRUD candidats, offres
   - ✅ Upload CV multi-format (PDF, DOCX, JPG)
   - ✅ Extraction texte + OCR (Tesseract, EasyOCR)
   - ✅ Parsing NLP (spaCy, entités, skills)
   - ✅ Authentification JWT + contrôle d'accès
   - ✅ Matching heuristique (production)
   - ✅ Sandbox ML + BERT (non-destructive)
   - ✅ Historique matchings + logs

2. **Frontend UI**
   - ✅ Drag & drop upload CV
   - ✅ Liste des candidats + détail
   - ✅ Création offres
   - ✅ Visualization matching score
   - ✅ **Modal rapport professionnel** (nouveau)

3. **Infrastructure**
   - ✅ PostgreSQL 16 + SQLAlchemy ORM
   - ✅ Migrations Alembic
   - ✅ Scripts démarrage dev (PowerShell)
   - ✅ Tests pytest (extraction, matching, API)

4. **RGPD & Sécurité**
   - ✅ Consentement candidat
   - ✅ Logs d'accès
   - ✅ Anonymisation possible
   - ✅ Droit à l'oubli
   - ✅ JWT + bcrypt

**Notes** (35 sec) : Faire impression que projet est solide et utilisable.

---

## Slide 12 : Résultats de Validation

### Titre
**Tests de Validation - Cas Réels**

### Contenu

**Test sur 3 offres fictives réalistes + 6 CVs réels :**

### Offre 1 : Ingénieur Backend Python
| Candidat | Heuristique | BERT | Recommandation |
|----------|------------|------|----------------|
| Wajih | 72.4% | 65.4% | ✅ Qualifié |
| Ahmed | 63.5% | 65.0% | ✅ Bon candidat |
| Maram | 68.8% | 63.5% | ⚠️ À vérifier |
| Ranim | 69.2% | 62.9% | ⚠️ À vérifier |

### Offre 2 : Data Scientist / ML
| Candidat | Heuristique | BERT | Recommandation |
|----------|------------|------|----------------|
| Maram | 87.9% | 66.7% | ⚠️ BERT pénalise (skills déclarées, contexte faible) |
| Wajih FR | 75.0% | 70.4% | ✅ Cohérent et qualifié |

### Offre 3 : Mobile React Native
| Candidat | Heuristique | BERT | Recommandation |
|----------|------------|------|----------------|
| Ines | 80.6% | 68.9% | ✅ Bien classée (#1) |
| Ranim | 84.1% | 60.5% | ⚠️ Skills déclarées non prouvées |

**Insight clé :**
- ✅ BERT détecte les incohérences (skills déclarées vs contexte réel)
- ✅ Heuristique et BERT souvent d'accord, écart utile comme signal

**Notes** (30 sec) : Montrer des chiffres concrets, expliquer la valeur du BERT.

---

## Slide 13 : Démo en Direct (optionnel / live)

### Titre
**Démo Courte - Interface Utilisateur**

### Contenu (Points clés à montrer)

```
📺 Démo Proposée (2-3 min max) :

1. Upload d'un CV
   - Montrer drag & drop
   - Extraction texte rapide

2. Créer une offre
   - Formulaire simple
   - Skills et description

3. Matching
   - Cliquer "Match"
   - Voir le score heuristique
   - Ouvrir le modal "Rapport professionnel"
   - Voir détail : top skills, incoherences, recommandation

4. Comparaison IA (optionnel)
   - Montrer endpoint /api/match-sandbox
   - Afficher BERT score vs heuristique
```

**Notes** : Préparer d'avance 2-3 CVs et offres pour ne pas perdre de temps.

---

# 🎯 BLOC 5 : CONCLUSION & PERSPECTIVES (2 min) — Slides 14-15

## Slide 14 : Points Forts du Projet

### Titre
**Apports Clés et Valeur Ajoutée**

### Contenu

### 🎯 Points Forts Projet

1. **Solution Complète**
   - ✅ Full-stack : frontend, backend, DB
   - ✅ Prêt à être déployé et utilisé
   - ✅ Utilisable en local ou cloud

2. **Architecture Robuste**
   - ✅ Séparation clair backend/frontend
   - ✅ Services modulaires et testables
   - ✅ ORM moderne (SQLAlchemy 2)

3. **IA Intégrée Intelligemment**
   - ✅ Heuristique rapide en production
   - ✅ Sandbox pour expérimenter IA sans risque
   - ✅ BERT multilingue pour comprendre sens
   - ✅ Détection d'incohérences CV vs skills

4. **Qualité Défendable**
   - ✅ Tests pytest (extraction, matching, API)
   - ✅ Validation résultats sur cas réels
   - ✅ Traçabilité complète (logs, historique)

5. **RGPD & Sécurité**
   - ✅ Approche data-privacy by design
   - ✅ Consentement, anonymisation, suppression

6. **Documentation**
   - ✅ README clair (backend/frontend)
   - ✅ Matching doc technique complète
   - ✅ Code commenté et lisible

**Notes** (30 sec) : Résumer rapidement, accent sur "utilisable aujourd'hui".

---

## Slide 15 : Perspectives et Évolutions

### Titre
**Roadmap Post-Projet**

### Contenu

### 📈 Améliorations Court Terme (1-3 mois)

- 🔧 Fine-tuner BERT sur données tunisiennes CVs
- 📊 Collecter dataset réel pour ML
- 📱 Optimiser frontend mobile
- 🎨 Ajouter thèmes colorés + personnalisation

### 📅 Évolutions Moyen Terme (3-6 mois)

- 🚀 Déploiement cloud (AWS / Heroku)
- 🔗 Intégration LinkedIn API pour enrichissement
- 📧 Notifications email (nouveaux matchings)
- 📋 Export rapports en PDF automatique
- 🤖 Recommandation offres → candidats (inverse)

### 🎓 Innovations Long Terme (6-12 mois)

- 🧠 Modèle custom BERT fine-tuné métier RH
- 🎯 Prédiction "fit culturel" via CV + offre
- 🌍 Support multilingue complet (20+ langues)
- 📊 Dashboard analytics (trends candidats, offres)
- 🔐 Blockchain audit trail pour légal/RGPD

### ⭐ Vision Finale

**TalentMatch v2.0 : plateforme IA RH tout-en-un**
- Smart matching multilingue
- Recommendation engine en temps réel
- Analytics prédictives
- Intégrations tierces (ATS, paie, etc.)

**Notes** (25 sec) : Montrer l'ambition sans surcharger, rester réaliste.

---

# 🎤 Conseils de Présentation

## Avant la restitution

1. **Timing**
   - ⏱️ Bloc 1 (Intro) : 3 min
   - ⏱️ Bloc 2 (Besoins) : 2 min
   - ⏱️ Bloc 3 (Archi) : 4 min
   - ⏱️ Bloc 4 (Avanc) : 4 min
   - ⏱️ Bloc 5 (Concl) : 2 min
   - **Total : ~15 min** (+ 5 min questions)

2. **Préparation**
   - ✅ Tester démo sur machine de présentation
   - ✅ Avoir un backup (vidéo enregistrée)
   - ✅ Imprimer handout (slides + archi)
   - ✅ Relire les slides la veille

3. **Livrables**
   - 📑 Slides (Google Slides, PowerPoint ou PDF)
   - 📝 Notes de présentation (ce document)
   - 🎥 Vidéo démo court (si démo en direct ne marche pas)
   - 📊 Rapport technique (bilan_v1.tex + matching.md)

## Pendant la restitution

- **Ton** : professionnel, confiant, pas lu (naturel)
- **Rythme** : 1 slide par ~30 sec (adapté au contenu)
- **Regard** : jury d'abord, puis écran
- **Voix** : claire, volume moyen-haut
- **Gestes** : naturels, pointeur laser si nécessaire
- **Questions** : noter et répondre à la fin du bloc

---

# 📋 Checklist Finale

- [ ] Slides créées (Google Slides ou PowerPoint)
- [ ] Notes de présentation révisées
- [ ] Démo testée en local (backend + frontend)
- [ ] 2-3 CVs et offres prêts pour la démo
- [ ] Backup vidéo enregistrée
- [ ] Rapport technique finalisé (bilan + matching)
- [ ] Handouts imprimés
- [ ] Timing exact mesuré (avec chronomètre)
- [ ] Expert assigné et date fixée
- [ ] Salle / projecteur confirmés

---

**Prêt pour la 1ère restitution ? 🚀**

Fais-moi signe une fois que tu as choisi le concept de présentation et je t'aide à créer les slides !
