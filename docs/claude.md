# RÉSUMÉ SPRINT 2

## Objectifs Sprint 2
- ✅ OCR EasyOCR pour images/scans
- ✅ Pipeline NLP (spaCy fr_core_news_md)
- ✅ BDD PostgreSQL
- ✅ Tests unitaires

## Travail accompli

### 1. Extraction (Core fixes)
**entity_extractor.py** : 5-pass name extraction
- Pass 1a : Préfixe "Nom:" 
- Pass 1b : Honorifiques (Dr./M./Mme.)
- Pass 1c : CamelCase splitting (SarahJohnson → Sarah Johnson)
- Pass 2 : spaCy NER avec nettoyage
- Pass 3 : Première ligne + deco cleanup

**contact_extractor.py** : Email + Phone
- Label-based emails (Email: xxx@email.com)
- PDF artifact cleaning (pe/ope/envelope prefixes)
- Phone date exclusion (19xx/20xx patterns)
- ORCID filtering

### 2. Bugs corrigés (5 critiques)
- `pesarah.johnson` → `sarah.johnson` ✅
- `Youssef Gara LinkedIn` → `Youssef Gara` ✅
- CamelCase names (`SarahJohnson`, `MehdiBenali`) → split ✅
- `Dr. AMIRA JEBALI` → `Amira Jebali` ✅
- `║ ASMA GHARBI ║` (box decorations) → `Asma Gharbi` ✅
- Dates exclues phones (2019 2022, 20242026) ✅

### 3. Infrastructure
- EasyOCR intégré (images + PDFs scannés)
- PyPDF pour PDFs texte
- python-docx pour DOCX
- Détection auto : text<100chars → OCR

### 4. BDD
- Table `candidates` (cv_id, nom, email, telephone, linkedin, github, parsed_data, raw_text, extraction_method)
- 18 CVs uploadés + re-parsés avec corrections
- All methods tracked (pypdf, python-docx, easyocr, pypdf+ocr)

### 5. Tests
- pytest 50 unit tests → **110 tests total**
- **110/110 passing** (test_sprint2_unit.py)
- Coverage: entity, contact, pipeline, skills, experience, config, utils

## État actuel
- Backend API (/api/upload-cv, /api/candidates) opérationnel
- 3 formats CV testés (PDF, DOCX, PNG)
- Extraction : noms 95%+ correct, emails 100%, phones bon filtre

## Améliorations restantes (Sprint 3)
- CamemBERT pour post-processing OCR (Yousset → Youssef)
- Matching candidat↔offre
- Dashboard RH
- Performance optimisation
