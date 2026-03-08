# Guide Technique OCR - Sprint 2

Ce document décrit l'implémentation OCR pour CVs scannés/images avec détection automatique et fallback.

## Objectif

- Extraire du texte depuis PDF scannés et images (PNG/JPG/JPEG)
- Prioriser Surya OCR
- Fallback automatique vers EasyOCR
- Intégration transparente dans le pipeline universel d'extraction

## Fichier principal

- Module OCR: [ocr_extractor.py](../backend/app/services/extraction/ocr_extractor.py)
- Intégration pipeline: [cv_extractor.py](../backend/app/services/extraction/cv_extractor.py)
- Tests: [test_ocr_extractor_pipeline.py](../backend/tests/test_ocr_extractor_pipeline.py)

## Architecture

1. Entrée `OCRExtractor.extract(file_path)`
2. Détection extension
3. Résolution moteur OCR
   - Surya OCR si disponible
   - Sinon EasyOCR
4. Exécution OCR:
   - Image: `extract_text_from_image()`
   - PDF scanné: `extract_text_from_scanned_pdf()` + `pdf2image`
5. Retour standardisé: succès, texte, pages, moteur, temps total, temps/page

## API de service

### `extract(file_path: str) -> dict`
Retourne:

- `success`: bool
- `text`: texte extrait
- `pages`: nombre de pages
- `method`: moteur OCR utilisé
- `engine`: `suryaocr` ou `easyocr`
- `needs_ocr`: bool
- `seconds_total`: temps total
- `seconds_per_page`: temps/page
- `error`: message d'erreur

### `extract_text_from_image(image_path: str, engine: str | None = None) -> list[str]`
Extraction OCR depuis image.

### `extract_text_from_scanned_pdf(pdf_path: str, engine: str | None = None) -> tuple[list[str], int]`
Convertit PDF en images via `pdf2image`, applique OCR page par page.

## Détection automatique et fallback

Dans le pipeline universel:

1. `PDFExtractor` tente extraction textuelle classique
2. Si `needs_ocr=True`, `CVExtractor` bascule automatiquement vers `OCRExtractor`
3. `method` final est marqué `pypdf+ocr`

## Exemples d'utilisation

### 1) OCR direct sur image

```python
from app.services.extraction.ocr_extractor import OCRExtractor

ocr = OCRExtractor(languages=['fr', 'en'])
result = ocr.extract("data/cvs_raw/scanned/cv_scanne_test.png")

print(result['success'], result['engine'])
print(result['text'][:300])
```

### 2) OCR direct sur PDF scanné

```python
from app.services.extraction.ocr_extractor import OCRExtractor

ocr = OCRExtractor()
result = ocr.extract("data/cvs_raw/scanned/cv_scanne_test.pdf")

print(result['pages'], result['seconds_per_page'])
```

### 3) Pipeline universel auto (textuel vs scanné)

```python
from app.services.extraction.cv_extractor import CVExtractor

extractor = CVExtractor()
result = extractor.extract("data/cvs_raw/scanned/cv_scanne_test.pdf")

print(result['method'])  # pypdf ou pypdf+ocr
print(result['format'])  # .pdf / .png / .jpg / .jpeg
```

## Tests

Lancer uniquement les tests OCR/pipeline:

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_ocr_extractor_pipeline.py -v
```

## Couverture critères d'acceptation

- Support formats scannés/images: PDF, PNG, JPG, JPEG
- Détection automatique textuel/scanné: oui (via `CVExtractor`)
- Fallback automatique: oui (`PDFExtractor` -> `OCRExtractor`)
- Tests unitaires: 6 tests (>= 5)
- Batch 10 CVs mixtes: test simulé avec taux de succès > 85%

## Notes d'exploitation

- `pdf2image` est requis pour OCR sur PDF
- Le moteur Surya est essayé en priorité; si indisponible, fallback EasyOCR
- Les performances réelles dépendent du CPU, de la résolution et de la qualité du scan
