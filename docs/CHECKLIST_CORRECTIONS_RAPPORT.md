# Checklist corrections rapport (basée sur correction.docx)

Objectif: pouvoir répondre « oui / en cours / à faire » sur chaque remarque.

## 1) Style / formulation
- [ ] Retirer les phrases “marketing”.
- [ ] Stabiliser la terminologie dans tout le document:
  - utiliser toujours « parsing de CV » et « matching candidat–offre ».
- [ ] Remplacer les affirmations fortes non prouvées (ex: “réduction 80–90%”) par:
  - hypothèses / objectifs visés / limites.

## 2) Objectifs (PFE)
- [ ] Séparer objectif général vs objectifs spécifiques.
- [ ] Garder les objectifs spécifiques réalistes (prototype fonctionnel).

## 3) Étude de l’existant
- [ ] Ajouter un mini tableau comparatif (coût, personnalisation, précision, hébergement, dépendance externe).

## 4) Architecture (le point le plus important)
- [x] Séparer clairement:
  - Extraction (PDF/DOCX/OCR)
  - Parsing (sections + extraction d’entités)
  - Matching (score)
  - Stockage (BDD + fichiers originaux)
  - (Optionnel) Validation/queue
- [x] Stockage du CV original: le backend stocke `data/cvs_raw/originals/{cv_id}.*`.

## 5) Choix technologiques / NLP
- [x] Positionner l’approche comme progressive:
  - règles/regex + spaCy (NER)
  - enrichissements optionnels selon besoins.
- [x] CamemBERT via API externe: présenté comme expérimental et **désactivé par défaut**.

## 6) RGPD (formulation prudente)
- [ ] Remplacer « RGPD compliant » par « mesures envisagées / objectifs de conformité ».
- [ ] Consentement: éviter de dire que c’est la seule base légale.
- [ ] Conservation: éviter « 2 ans universel » → « selon politique interne + réglementation applicable ».
- [ ] Chiffrement: préciser “quoi” (mots de passe hashés, fichiers stockés, échanges HTTPS, etc.).

## 7) Planification Scrum
- [ ] Corriger l’incohérence des semaines (24 semaines vs sprints).

---

## Annexes — preuves dans le code (pour répondre vite en validation)

- Pipeline upload/extraction/parsing + stockage original: [backend/app/routes/cv.py](../backend/app/routes/cv.py)
- Extracteur unifié (PDF/DOCX/OCR): [backend/app/services/extraction/cv_extractor.py](../backend/app/services/extraction/cv_extractor.py)
- Parser NLP (contact/skills/exp/formation + metadata): [backend/app/services/nlp/nlp_parser.py](../backend/app/services/nlp/nlp_parser.py)
- CamemBERT opt-in (désactivé par défaut): [backend/app/services/nlp/hf_camembert.py](../backend/app/services/nlp/hf_camembert.py)
