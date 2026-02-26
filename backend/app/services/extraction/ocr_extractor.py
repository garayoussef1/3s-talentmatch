"""
Module d'extraction de texte depuis des PDFs scannés / images
Utilise EasyOCR pour la reconnaissance optique de caractères
Partie du projet 3S TalentMatch
"""

from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class OCRExtractor:
    """
    Extracteur de texte pour PDFs scannés et images.
    Utilise EasyOCR (support multilingue : fr, en, ar).
    """

    def __init__(self, languages: List[str] = None):
        """
        Args:
            languages: Liste des langues pour l'OCR.
                       Défaut : ['fr', 'en']
        """
        self.languages = languages or ['fr', 'en']
        self._reader = None  # Chargement lazy (lourd à initialiser)
        logger.info(f"OCRExtractor initialisé - langues: {self.languages}")

    def _get_reader(self):
        """Charge EasyOCR seulement quand nécessaire"""
        if self._reader is None:
            import easyocr
            logger.info("Chargement du modèle EasyOCR...")
            self._reader = easyocr.Reader(self.languages, gpu=False)
            logger.info("Modèle EasyOCR chargé")
        return self._reader

    def extract(self, file_path: str) -> Dict:
        """
        Extrait le texte d'un PDF scanné ou d'une image.

        Formats supportés : .pdf (scanné), .png, .jpg, .jpeg, .tiff, .bmp

        Returns:
            dict avec success, text, pages, method, needs_ocr, error
        """
        logger.info(f"Début extraction OCR: {file_path}")

        result = {
            'success': False,
            'text': '',
            'pages': 0,
            'method': 'easyocr',
            'needs_ocr': True,
            'error': None
        }

        path = Path(file_path)

        # Vérifier existence
        if not path.exists():
            result['error'] = f"Fichier non trouvé: {file_path}"
            logger.error(result['error'])
            return result

        suffix = path.suffix.lower()
        image_formats = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp']
        pdf_format = ['.pdf']

        if suffix not in image_formats + pdf_format:
            result['error'] = f"Format non supporté: {suffix}"
            logger.error(result['error'])
            return result

        try:
            reader = self._get_reader()

            if suffix in image_formats:
                # Extraction directe sur image
                texts = self._extract_from_image(reader, str(path))
                result['pages'] = 1

            else:
                # PDF scanné : convertir chaque page en image puis OCR
                texts, num_pages = self._extract_from_pdf(reader, str(path))
                result['pages'] = num_pages

            full_text = '\n'.join(texts).strip()
            result['text'] = full_text

            if not full_text:
                result['error'] = "Aucun texte détecté par l'OCR"
                logger.warning(result['error'])
                return result

            result['success'] = True
            logger.info(f"OCR réussi: {len(full_text)} caractères sur {result['pages']} page(s)")
            return result

        except ImportError:
            result['error'] = "EasyOCR n'est pas installé (pip install easyocr)"
            logger.error(result['error'])
            return result

        except Exception as e:
            result['error'] = f"Erreur OCR: {str(e)}"
            logger.exception(result['error'])
            return result

    def _extract_from_image(self, reader, image_path: str) -> List[str]:
        """Extrait le texte d'une image"""
        results = reader.readtext(image_path)
        return [text for (_, text, confidence) in results if confidence > 0.3]

    def _extract_from_pdf(self, reader, pdf_path: str):
        """
        Convertit chaque page du PDF en image puis applique l'OCR.
        Utilise pdf2image (nécessite poppler).
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image n'est pas installé. "
                "Installez-le avec : pip install pdf2image\n"
                "Et installez aussi Poppler : https://github.com/oschwartz10612/poppler-windows/releases"
            )

        import tempfile, os

        pages_images = convert_from_path(pdf_path, dpi=200)
        all_texts = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, page_img in enumerate(pages_images):
                img_path = os.path.join(tmp_dir, f"page_{i+1}.png")
                page_img.save(img_path, 'PNG')
                page_texts = self._extract_from_image(reader, img_path)
                all_texts.extend(page_texts)
                logger.info(f"Page {i+1}/{len(pages_images)} traitée")

        return all_texts, len(pages_images)
