"""
Extracteur unifié de CVs - Point d'entrée principal
Détecte automatiquement le format et appelle le bon extracteur
Partie du projet 3S TalentMatch
"""

from pathlib import Path
from typing import Dict
import logging

from app.services.extraction.pdf_extractor import PDFExtractor
from app.services.extraction.word_extractor import WordExtractor
from app.services.extraction.ocr_extractor import OCRExtractor

logger = logging.getLogger(__name__)

# Formats supportés par chaque extracteur
PDF_FORMATS   = ['.pdf']
WORD_FORMATS  = ['.docx']
IMAGE_FORMATS = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp']


class CVExtractor:
    """
    Extracteur unifié : détecte le format du fichier
    et délègue au bon extracteur.

    Formats supportés :
      - PDF textuel  → PDFExtractor (pypdf)
      - PDF scanné   → PDFExtractor détecte, fallback OCRExtractor
      - Word (.docx) → WordExtractor (python-docx)
      - Images       → OCRExtractor (EasyOCR)
    """

    def __init__(self, ocr_languages: list = None):
        self._pdf_extractor  = PDFExtractor()
        self._word_extractor = WordExtractor()
        self._ocr_extractor  = OCRExtractor(languages=ocr_languages or ['fr', 'en'])
        logger.info("CVExtractor initialisé")

    def extract(self, file_path: str) -> Dict:
        """
        Extrait le texte d'un CV quel que soit son format.

        Args:
            file_path: Chemin vers le fichier CV

        Returns:
            dict avec : success, text, pages, method, format, needs_ocr, error
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        logger.info(f"Extraction CV: {path.name} (format: {suffix})")

        # Fichier inexistant
        if not path.exists():
            return self._error(f"Fichier non trouvé: {file_path}", suffix)

        # Format non supporté
        all_formats = PDF_FORMATS + WORD_FORMATS + IMAGE_FORMATS
        if suffix not in all_formats:
            return self._error(
                f"Format non supporté: {suffix}. "
                f"Formats acceptés: {', '.join(all_formats)}",
                suffix
            )

        # Routing vers le bon extracteur
        if suffix in WORD_FORMATS:
            result = self._word_extractor.extract(file_path)

        elif suffix in IMAGE_FORMATS:
            result = self._ocr_extractor.extract(file_path)

        elif suffix in PDF_FORMATS:
            # Essayer d'abord l'extraction texte
            result = self._pdf_extractor.extract(file_path)

            # Si le PDF est scanné (needs_ocr=True), basculer sur OCR
            if result.get('needs_ocr'):
                logger.info("PDF scanné détecté → basculement sur OCR")
                result = self._ocr_extractor.extract(file_path)
                result['method'] = 'pypdf+easyocr'

        # Ajouter le format détecté dans le résultat
        result['format'] = suffix
        return result

    def _error(self, message: str, suffix: str = '') -> Dict:
        return {
            'success': False,
            'text': '',
            'pages': 0,
            'method': '',
            'format': suffix,
            'needs_ocr': False,
            'error': message
        }
