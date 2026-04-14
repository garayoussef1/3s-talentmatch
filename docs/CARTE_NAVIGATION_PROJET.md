# 3S TalentMatch — Carte de navigation & récap (à jour)

Date : 31 mars 2026

Ce document sert de **repère unique** pour comprendre :
- la différence **Extraction** (fichier → texte) vs **NLP** (texte → JSON structuré),
- où et comment **spaCy** est utilisé (et comment le prouver),
- comment on a **mesuré** la valeur de spaCy (A/B test),
- où sont les **heuristiques** et les **extracteurs dédiés** dans le code,
- et une recommandation sur ton idée “utiliser le compte candidat pour fiabiliser nom/email”.

---

## 1) Le pipeline (vue simple)

### Étape A — Extraction (fichier → texte brut)
Objectif : obtenir une string exploitable, sans structuration.
- Code : `backend/app/services/extraction/` (ex: `CVExtractor`)
- Méthodes typiques : PDF textuel (rapide), DOCX, OCR (lent pour scannés)

### Étape B — NLP parsing (texte brut → JSON structuré)
Objectif : remplir un JSON (identité, contacts, skills, formations, expériences, langues).
- Orchestrateur : `backend/app/services/nlp/nlp_parser.py` → classe `NLPParser` → méthode `parse(...)`
- Extracteurs appelés (ordre) :
  1. `ContactExtractor` → email/tel/LinkedIn/GitHub/site/adresse
  2. `EntityExtractor` + CamemBERT (optionnel) + fallback email → nom complet
  3. `SkillsExtractor` → compétences
  4. `FormationExtractor` → formations
  5. `ExperienceExtractor` → expériences
  + `NLPParser._extract_langues(...)` → langues (regex + fallback)

---

## 2) Où spaCy intervient (et comment le prouver)

### Rôle de spaCy
spaCy n’est **pas** dans l’étape d’extraction du texte.
Il intervient dans l’étape **NLP** pour aider la structuration (NER, renfort sur ORG/PER selon extracteur).

### Preuve runtime (traces dans `metadata`)
On expose des champs “preuve” dans le JSON final (dans `parsed_data.metadata`) :
- `spacy_model`
- `spacy_version`
- `spacy_has_ner`
- `spacy_fallback`
- `spacy_pipes`

Ces champs sont définis dans :
- `backend/app/schemas/cv_data.py` → modèle `Metadata`

Ils sont renseignés dans :
- `backend/app/services/nlp/nlp_parser.py` (chargement spaCy + injection dans le résultat)

Politique fallback :
- si `fr_core_news_md` ne charge pas, on fallback vers `spacy.blank('fr')` (pipeline minimal, souvent sans NER).

---

## 3) Comment on a mesuré “la valeur” de spaCy (A/B test)

Principe :
- même texte extrait
- 2 runs NLP :
  - Run A : spaCy modèle (`fr_core_news_md`) → NER actif
  - Run B : fallback forcé (`spacy.blank('fr')`) → pas de NER
- on compare des métriques simples : `full_name`, `org_formations`, `org_experiences`, etc.

### Scripts
- Comparaison batch (génère un rapport JSON) :
  - `backend/tests/compare_spacy_impact_batch.py`
- Résumé “score de valeur” (lit le JSON et génère un Markdown) :
  - `backend/tests/summarize_spacy_impact.py`

### Commandes (Windows PowerShell)
Depuis la racine du repo :

- Générer un rapport :
  - `Push-Location backend`
  - `& ..\.venv-10\Scripts\python.exe -m tests.compare_spacy_impact_batch --dir ..\data\cvs_raw --exclude-scanned --out ..\data\cvs_processed\spacy_impact_report_noscan.json`
  - `Pop-Location`

- Générer un résumé Markdown :
  - `Push-Location backend`
  - `& ..\.venv-10\Scripts\python.exe -m tests.summarize_spacy_impact --report ..\data\cvs_processed\spacy_impact_report_noscan.json --md ..\docs\spacy_value_summary.md`
  - `Pop-Location`

Sorties typiques :
- Rapport JSON : `data/cvs_processed/spacy_impact_report_*.json`
- Résumé : `docs/spacy_value_summary.md`

---

## 3bis) Scripts rapides pour tester CamemBERT depuis le frontend

Pour tester “en conditions réelles” via l’UI (upload CV), tu peux lancer l’app avec CamemBERT ON/OFF :

- Activer CamemBERT (HF) :
  - `./dev-camembert-on.ps1`
  - ou `./dev-camembert-on.ps1 -HFToken "<ton_token>"`

- Désactiver CamemBERT (même si `HF_TOKEN` existe) :
  - `./dev-camembert-off.ps1`

- Vérifier l’état (session courante) :
  - `./dev-camembert-status.ps1`

---

## 4) Carte de navigation (lecture du code, ordre recommandé)

Si tu veux comprendre vite “qui fait quoi”, lis dans cet ordre :

1) Orchestrateur
- `backend/app/services/nlp/nlp_parser.py`
  - `NLPParser.parse(...)`
  - `NLPParser._load_model(...)`

2) Extracteurs (1 fichier = 1 domaine)
- Contacts : `backend/app/services/nlp/contact_extractor.py` → `ContactExtractor.extract(...)`
- Nom : `backend/app/services/nlp/entity_extractor.py` → `EntityExtractor.extract_full_name(...)`
- CamemBERT (optionnel) : `backend/app/services/nlp/hf_camembert.py` → `HFCamembertNameExtractor.extract_person_name(...)`
- Skills : `backend/app/services/nlp/skills_extractor.py` → `SkillsExtractor.extract(...)`
- Formations : `backend/app/services/nlp/formation_extractor.py` → `FormationExtractor.extract(...)`
- Expériences : `backend/app/services/nlp/experience_extractor.py` → `ExperienceExtractor.extract(...)`

3) Heuristiques partagées + config
- Sections / normalisation : `backend/app/services/nlp/utils.py` → `extract_section(...)`
- Titres de sections : `backend/app/services/nlp/config.py` → `SECTION_PATTERNS`

---

## 5) Heuristiques vs extracteurs dédiés (définition + exemples)

### Extracteur dédié
Une **classe** qui encapsule une responsabilité et expose un point d’entrée `extract(text)` (ou équivalent).

### Heuristiques
Règles concrètes à l’intérieur des extracteurs :
- regex (emails, dates, sections, séparateurs)
- multi-passes (essayer plusieurs stratégies dans un ordre)
- normalisation (accents, espaces, artefacts PDF/OCR)
- filtres anti-faux-positifs (mots interdits, contextes obligatoires)
- déduplication

Exemples rapides :
- `ContactExtractor` : regex email (incluant artefacts PDF), variantes OCR avec espaces, filtres anti-dates.
- `EntityExtractor` : passes “ligne simple / préfixe / honorifique / CamelCase / 1ères lignes / spaCy NER”.
- `SkillsExtractor` : section “Compétences” prioritaire, puis texte global, garde-fous sur skills ambigus.
- `FormationExtractor` & `ExperienceExtractor` : “section → blocs → extraction par bloc” + dédup/tri.

---

## 6) Ton idée : utiliser le compte candidat pour fiabiliser nom/email

Oui, c’est pertinent, mais à condition de l’utiliser **comme source de référence**, pas comme “remplacement aveugle”.

Recommandation simple :
- Si **le candidat est authentifié** et upload **son propre CV** :
  - `email` : utiliser l’email du compte comme **email principal** (puis garder l’email trouvé dans le CV comme info secondaire si différent).
  - `nom` : utiliser le nom du compte comme **prior** (si le parsing sort un nom différent, on garde les deux + on marque un conflit).
- Si **un recruteur** upload le CV d’un candidat : ne pas utiliser l’identité du compte recruteur (sinon tu écrases avec la mauvaise identité).

Bon pattern produit :
- garder `name_source` / `email_source` + un bool `conflict` quand CV vs compte ne matchent pas,
- afficher un warning côté UI/admin plutôt que “corriger silencieusement”.

---

## 7) Docs existantes utiles (références)
- `docs/PROJET_OVERVIEW.md` : vue d’ensemble produit
- `docs/EXTRACTION_QUALITY_QUICKSTART.md` + `docs/EXTRACTION_QUALITY_REPORT.md` : qualité extraction
- `docs/spacy_value_summary.md` : preuve de valeur spaCy (résumé)
- `docs/PIPELINE_NLP_EXPLICATION.txt` : doc historique (certaines sections peuvent être dépassées)
