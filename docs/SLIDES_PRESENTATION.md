# 3S TalentMatch - Slides Présentation 1ère Restitution

## Slide 1 : Couverture
---
**3S TalentMatch**

Plateforme Intelligente de Matching CV / Offres d'Emploi

Youssef Gara  
PFE ESPRIT 2025-2026

Expert : [À compléter]

---

## Slide 2 : Problématique et Contexte
---
### Le Recrutement : Défi Métier

**Problèmes identifiés chez les Cabinets RH :**
- 📄 Volume massif de CVs à traiter manuellement
- ⏱️ Temps consacré au tri et pré-qualification très important  
- ❌ Risque d'erreurs humaines (oublis, fatigue, subjectivité)
- 🔍 Manque de traçabilité et d'objectivité dans le processus

**Étude de l'existant :**
- Outils : Excel, email, tri manuel
- Processus : réception → archivage → recherche fastidieuse
- **Limite majeure** : 0 automatisation, 0 scoring intelligent

**Solution Proposée : TalentMatch**
- ✅ Extraction automatique CVs (PDF, DOCX, OCR)
- ✅ Matching sémantique CV ↔ Offre (IA)
- ✅ Recommandations objectivées
- ✅ Interface pour recruteurs

---

## Slide 3 : Objectifs du Projet
---
### Objectifs Fonctionnels et Non-Fonctionnels

**Fonctionnels :**
1. Upload et extraction automatique CVs (multi-format)
2. Création et gestion d'offres d'emploi
3. Matching candidat-offre avec score pertinent
4. Génération de rapports détaillés et professionnels
5. Authentification et gestion des droits (recruteur, candidat)

**Non-Fonctionnels :**
- 📱 Responsive design (desktop et mobile)
- ⚡ Performance : matching < 5 sec/candidat
- 🔐 Sécurité : JWT, chiffrement données sensibles
- 📊 Traçabilité : logs audit complets
- 🛡️ **RGPD** : consentement, anonymisation, droit à l'oubli

---

## Slide 4 : Analyse des Besoins - Cas d'Usage
---
### Cas d'Usage Principaux

**Acteur : Recruteur**

| Cas d'Usage | Flux |
|-------------|------|
| **UC1 : Upload CV** | Drag & drop PDF/DOCX/JPG → Extraction auto → Candidat créé |
| **UC2 : Créer Offre** | Saisir titre, skills, description → Sauvegarde base |
| **UC3 : Matcher Candidat** | Sélectionner candidat + offre → Score + rapport → Export PDF |
| **UC4 : Historique** | Consulter tous matchings passés → Télécharger rapports |

**Acteur : Candidat**
- Consulter profil
- Gérer consentement RGPD
- Demander suppression données

---

## Slide 5 : Contraintes et Risques
---
### Hypothèses, Contraintes, Risques

**Hypothèses :**
- CVs en français ou anglais
- Données sensibles (nom, email, tél) nécessitent protection
- Modèle IA suffisant pour POC (pas fine-tuning)

**Contraintes Techniques :**
- 🖥️ **Pas de GPU** → solution CPU-first
- 📊 Dataset limité → sandbox non persistante
- 🔌 Base PostgreSQL locale
- 🌐 Pas de dépendances cloud tierces

**Risques et Mitigations :**

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| OCR imprécis | Extraction partielle | Validations + fallback manuel |
| Temps matching lent | UX dégradée | Cache, optimisation BERT |
| Modèle peu fiable | Mauvais scores | Heuristique robuste + sandbox |

---

## Slide 6 : Architecture Générale
---
### Architecture Système High-Level

```
┌─────────────────────────────────────┐
│   Frontend (React 18 + Vite)        │
│   Port 3000 - Tailwind CSS          │
│   • Upload  • Offres  • Matchings   │
└──────────────┬──────────────────────┘
               │ HTTP(S) + JWT
               ↓
┌─────────────────────────────────────┐
│   Backend API (FastAPI)             │
│   Port 8000 - uvicorn               │
│   • /api/upload-cv                  │
│   • /api/candidates                 │
│   • /api/match                      │
│   • /api/match-sandbox (IA)         │
└──────────────┬──────────────────────┘
               │ SQLAlchemy ORM
               ↓
┌─────────────────────────────────────┐
│   PostgreSQL 16                     │
│   • Candidates  • Offers  • Logs    │
│   • CVDocuments • Consents          │
└─────────────────────────────────────┘
```

---

## Slide 7 : Backend - Microservices
---
### Architecture Backend - Services Modulaires

```
FastAPI Backend
│
├── 📂 Extraction (PDF/DOCX/OCR)
│   ├── PyPDF Extractor
│   ├── DOCX Extractor
│   └── EasyOCR + Tesseract
│
├── 📂 NLP & Parsing
│   ├── spaCy Entity Extractor
│   ├── Skill Detector
│   └── Experience Parser
│
├── 📂 Matching Engine (3 modes)
│   ├── RapidFuzz (heuristique)
│   ├── LogReg (ML classique)
│   └── BERT (IA sémantique) ← NOUVEAU
│
├── 📂 Persistence
│   ├── SQLAlchemy ORM
│   ├── Alembic Migrations
│   └── PostgreSQL
│
└── 📂 Routes API
    ├── /candidates (CRUD)
    ├── /offers (CRUD)
    ├── /match (production)
    └── /match-sandbox (IA)
```

---

## Slide 8 : Matching Engine - 3 Moteurs
---
### Système de Matching Hybride

**1️⃣ Heuristique (Production - Fiable)**
- RapidFuzz fuzzy matching
- Comparaison : expérience, diplômes, localisation
- Poids : Skills 45% + Exp 25% + Edu 20% + Loc 10%
- ✅ Rapide, expliquable, sans IA

**2️⃣ ML Classique (Sandbox - POC)**
- Logistic Regression
- Features : exp_score, edu_score, location
- ⚠️ Dataset limité (6 samples)

**3️⃣ BERT Sémantique (Sandbox - NOUVEAU IA)**
- Modèle : `paraphrase-multilingual-MiniLM-L12-v2`
- 🤖 Comprend sens : "Python engineer" = "Dev Python"
- 🌐 Multilingue natif (50+ langues)
- 🔍 Détecte incohérences : skills déclarées vs contexte CV
- Formule :
```
Score = 0.50×semantic + 0.30×skills + 0.20×base - penalty
```

---

## Slide 9 : Stack Technologique
---
### Technologies Utilisées

| Couche | Stack | Détails |
|--------|-------|---------|
| **Frontend** | React 18 + Vite 5 | UI rapide, SPA moderne |
| | Tailwind CSS 3 | Utility-first design |
| | Axios + React Router | HTTP + routing |
| **Backend** | FastAPI | API haute-perf |
| | SQLAlchemy 2 | ORM moderne |
| | PostgreSQL 16 | Base robuste |
| **Extraction** | PyPDF, python-docx | PDF/DOCX parsing |
| | EasyOCR, Tesseract | OCR multilingue |
| **NLP** | spaCy, BERT | Entities, embeddings |
| | RapidFuzz | Fuzzy matching |
| **Auth** | JWT + bcrypt | Sécurité |
| **Tests** | pytest | Couverture unitaire |

---

## Slide 10 : Pipeline Complet
---
### Flux de Données : Upload → Matching → Rapport

```
Recruteur
   │ Upload CV
   ↓
[1. Extraction]
   ├─ PDF Parser / OCR
   └─ Texte brut + DB
   │
   ↓
[2. NLP Enrichment]
   ├─ Entity Extraction
   ├─ Skill Detection
   └─ Experience Parsing
   │
   ↓
Recruteur saisit Offre
   │
   ↓
[3. Matching (3 modes)]
   ├─ Heuristique (prod)
   ├─ ML (sandbox)
   └─ BERT IA (sandbox)
   │
   ↓
[4. Rapport Généré]
   ├─ Score final
   ├─ Top skills match
   ├─ Recommandation
   └─ Incohérences
```

---

## Slide 11 : État d'Avancement MVP
---
### Fonctionnalités Implémentées ✅

**Backend API**
- ✅ CRUD candidats, offres
- ✅ Upload CV (PDF, DOCX, JPG)
- ✅ Extraction + OCR automatique
- ✅ Parsing NLP (entités, skills)
- ✅ Auth JWT + contrôle accès
- ✅ Matching heuristique
- ✅ Sandbox ML + BERT
- ✅ Logs audit complets

**Frontend UI**
- ✅ Drag & drop upload
- ✅ Liste candidats + détail
- ✅ Création offres
- ✅ Visualisation score matching
- ✅ Modal rapport professionnel
- ✅ Responsive design

**Infrastructure & RGPD**
- ✅ PostgreSQL 16 + migrations
- ✅ Tests pytest (extraction, matching)
- ✅ Consentement candidat
- ✅ Anonymisation + droit oubli
- ✅ Scripts démarrage dev

---

## Slide 12 : Résultats de Validation
---
### Tests sur Cas Réels (6 CVs + 3 offres)

**Offre 1 : Ingénieur Backend Python**
| Candidat | Heuristique | BERT | Verdict |
|----------|------------|------|---------|
| Wajih | 72.4% | 65.4% | ✅ Qualifié |
| Ahmed | 63.5% | 65.0% | ✅ Bon |
| Maram | 68.8% | 63.5% | ⚠️ À vérifier |
| Ranim | 69.2% | 62.9% | ⚠️ À vérifier |

**Offre 2 : Data Scientist / ML**
| Candidat | Heuristique | BERT | Verdict |
|----------|------------|------|---------|
| Maram | 87.9% | 66.7% | ⚠️ Skills déclarées, contexte faible |
| Wajih FR | 75.0% | 70.4% | ✅ Cohérent |

**Offre 3 : Mobile React Native**
| Candidat | Heuristique | BERT | Verdict |
|----------|------------|------|---------|
| Ines | 80.6% | 68.9% | ✅ Meilleur match |

**🔍 Insight Clé :** BERT détecte les incohérences (skills déclarées vs contexte réel)

---

## Slide 13 : Démo Live (Optionnel)
---
### Points de Démonstration Proposés

**5 min de démo en direct :**

1. **Upload CV**
   - Montrer drag & drop
   - Extraction automatique

2. **Créer Offre**
   - Formulaire simple
   - Skills + description

3. **Matching**
   - Cliquer "Match"
   - Voir score heuristique
   - Ouvrir modal "Rapport Professionnel"
   - Détails : top skills, incoherences

4. **Comparaison IA (optionnel)**
   - Endpoint /api/match-sandbox
   - BERT score vs heuristique

---

## Slide 14 : Points Forts du Projet
---
### Apports Clés et Valeur Ajoutée

✅ **Solution Complète**
- Full-stack utilisable immédiatement
- Déployable en local ou cloud

✅ **Architecture Robuste**
- Séparation frontend/backend/DB
- Services modulaires testables
- ORM moderne (SQLAlchemy 2)

✅ **IA Intégrée Intelligemment**
- Heuristique rapide en production
- Sandbox sans risque pour expérimenter
- BERT multilingue pour comprendre sens
- Détection incohérences CV vs skills déclarées

✅ **Qualité Défendable**
- Tests pytest (extraction, matching, API)
- Validation sur cas réels (6 CVs)
- Traçabilité complète (logs, historique)

✅ **RGPD & Sécurité**
- Data-privacy by design
- Consentement, anonymisation, suppression

✅ **Documentation**
- README clair (backend/frontend)
- Doc matching technique
- Code bien commenté

---

## Slide 15 : Perspectives et Roadmap
---
### Évolutions Post-Projet

**Court Terme (1-3 mois) 🔧**
- Fine-tuner BERT sur CVs tunisiens
- Collecter dataset réel pour ML
- Optimiser frontend mobile
- Themes colorés + personnalisation

**Moyen Terme (3-6 mois) 📅**
- Déploiement cloud (AWS/Heroku)
- Intégration LinkedIn API
- Notifications email
- Export PDF automatique
- Recommendation inverse (offres → candidats)

**Long Terme (6-12 mois) 🎓**
- Modèle BERT custom fine-tuné RH
- Prédiction "fit culturel"
- Support 20+ langues
- Dashboard analytics
- Blockchain audit trail RGPD

**Vision Finale ⭐**  
**TalentMatch v2.0 : plateforme IA RH tout-en-un**

---

# Notes de Présentation Supplémentaires

## Timing Par Bloc
- **Slide 1-3** (Intro) : 3 min
- **Slide 4-5** (Besoins) : 2 min
- **Slide 6-10** (Architectures) : 4 min
- **Slide 11-13** (Avancement) : 4 min
- **Slide 14-15** (Conclusion) : 2 min
- **Total** : ~15 min (+ 5 min questions)

## Conseils de Présentation
- 📌 Tester démo sur machine de présentation avant
- 📌 Imprimer handout (slides + archi)
- 📌 Ton professionnel, naturel (pas lu)
- 📌 Rythme : 1 slide par 30-40 sec
- 📌 Regard : jury d'abord, écran second
- 📌 Préparer 2-3 CVs et offres pour démo

## Checklist
- [ ] Slides converties en PowerPoint/Google Slides
- [ ] Démo testée (backend + frontend)
- [ ] CVs et offres prêts
- [ ] Rapport technique finalisé
- [ ] Timing mesuré (avec chronomètre)
- [ ] Expert assigné et date fixée
- [ ] Salle/projecteur confirmés
