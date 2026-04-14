# Validation encadrante — synthèse (02/04/2026)

## 1) Ce que l’encadrante demande (extraits **correction.docx**)

- Stabiliser les formulations (pas de marketing, pas de chiffres non prouvés).
- Clarifier l’architecture: **Extraction** / **Parsing** / **Matching** / **Stockage** + éventuellement validation/queue.
- Être prudent sur RGPD: parler de **mesures envisagées**, pas “RGPD compliant garanti”.
- Remarque forte: **CamemBERT via API HuggingFace** n’est pas robuste/pérenne (dépendance externe, quotas, latence, confidentialité).

## 2) Ce que dit le cahier des charges (data/cahier_de_charge.docx)

Fonctionnel attendu (résumé):
- Authentification JWT + rôles (candidat / recruteur / admin).
- Upload multi-format (PDF, DOCX, image/scan) + validation format/poids + **stockage du CV original**.
- Extraction automatique → structuration JSON: identité, contacts, compétences, expériences, formations.
- Analyse NLP (NER) pour entités utiles.
- Matching CV–offre + dashboard + export.

## 3) Ce qui est déjà implémenté (preuve dans le code)

### A) Extraction (format → texte)
- Point d’entrée extraction unifiée: [backend/app/services/extraction/cv_extractor.py](../backend/app/services/extraction/cv_extractor.py)
  - PDF textuel: `PDFExtractor`
  - DOCX: `WordExtractor`
  - Images/PDF scannés: `OCRExtractor` (EasyOCR)
  - Fallback: PDF scanné → OCR

### B) Parsing (texte → JSON structuré)
- Orchestrateur NLP: [backend/app/services/nlp/nlp_parser.py](../backend/app/services/nlp/nlp_parser.py)
  - `ContactExtractor`: email/tél/LinkedIn/GitHub
  - `EntityExtractor`: entités (PERSON/ORG/DATE…)
  - `SkillsExtractor`: compétences + catégories
  - `FormationExtractor`: formations
  - `ExperienceExtractor`: expériences
  - Traces runtime dans `metadata` (spaCy + config CamemBERT + score de confiance)

### C) API backend (upload, stockage, listing)
- Route upload + pipeline complet: [backend/app/routes/cv.py](../backend/app/routes/cv.py)
  - `POST /upload-cv?offer_id=...`
  - Sauvegarde fichier original: `data/cvs_raw/originals/{cv_id}.*`
  - Exécute extraction + parsing, persiste en BDD (PostgreSQL)

### D) CamemBERT (HuggingFace) — statut
- Module présent mais **désactivé par défaut (opt-in)**: [backend/app/services/nlp/hf_camembert.py](../backend/app/services/nlp/hf_camembert.py)
  - Pour activer: `HF_ENABLE_CAMEMBERT_NAME=1` + `HF_TOKEN=...`
  - Sinon: spaCy + heuristiques uniquement.

## 4) Ce que tu peux expliquer demain (pitch 2 minutes)

1. **Objectif**: automatiser extraction + structuration des CV pour aider le tri/matching.
2. **Pipeline**:
   - Upload CV → Extraction texte (PDF/DOCX/OCR)
   - Parsing NLP → JSON structuré (identité/contacts/skills/exp/formation)
   - Stockage en base + conservation du fichier original
3. **Robustesse**:
   - OCR fallback pour scans
   - Parsing non bloquant: si NLP échoue, l’upload reste OK
   - Traces `metadata` pour prouver quels modules ont tourné
4. **IA/NLP**:
   - spaCy (NER) + règles/heuristiques
   - CamemBERT via API externe: gardé comme expérimentation, **désactivé par défaut**

## 5) Démo conseillée (simple et claire)

- Côté candidat: choisir une offre → upload CV (PDF ou DOCX).
- Côté recruteur/admin: ouvrir la liste candidats → ouvrir un candidat → montrer:
  - texte extrait (preview)
  - JSON structuré (identité/contacts/skills/exp/formation)
  - `metadata` (méthode extraction + spaCy actif + score confiance)

## 6) Prochaines améliorations parsing/extraction (priorité PFE)

- Améliorer la robustesse sur PDF “compact” (gestion sauts de lignes / mots cassés) — déjà partiellement fait dans `NLPParser._normalize_pdf_text`.
- Améliorer la détection d’expériences (dates + entreprise + poste) sur mises en page atypiques.
- Ajouter une évaluation simple (A/B) sur un lot de CV (qualité extraction/structuration) pour objectiver les progrès.

---

Si tu veux, on peut compléter ce doc avec une table "exigence → état (fait/en cours/à faire)" et des captures d’écran à utiliser pendant la validation.
