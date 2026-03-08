"""
Module d'extraction OCR pour PDFs scannés et images.

Stratégie moteur OCR:
1) EasyOCR (prioritaire)
2) Surya OCR (fallback automatique)
"""

from pathlib import Path
from typing import Dict, List, Tuple
import importlib
import logging
import time

logger = logging.getLogger(__name__)


class OCRExtractor:
    """
    Extracteur de texte pour PDFs scannés et images.
    Utilise EasyOCR en priorité, puis Surya OCR en fallback.
    """

    def __init__(self, languages: List[str] = None, preferred_engine: str = 'easyocr'):
        """
        Args:
            languages: Liste des langues pour l'OCR.
                       Défaut : ['fr', 'en']
            preferred_engine: 'easyocr' (défaut) ou 'surya'
        """
        self.languages = languages or ['fr', 'en']
        self.preferred_engine = preferred_engine
        self._easyocr_reader = None
        logger.info(
            "OCRExtractor initialisé - langues=%s, moteur préféré=%s",
            self.languages,
            self.preferred_engine
        )

    def _is_surya_available(self) -> bool:
        return importlib.util.find_spec('surya_ocr') is not None

    def _is_easyocr_available(self) -> bool:
        return importlib.util.find_spec('easyocr') is not None

    def _resolve_engine(self) -> str:
        """Détermine le moteur OCR à utiliser avec fallback automatique."""
        if self.preferred_engine == 'surya':
            if self._is_surya_available():
                return 'suryaocr'
            if self._is_easyocr_available():
                logger.warning("Surya OCR indisponible, fallback vers EasyOCR")
                return 'easyocr'
        else:
            if self._is_easyocr_available():
                return 'easyocr'
            if self._is_surya_available():
                logger.warning("EasyOCR indisponible, fallback vers Surya OCR")
                return 'suryaocr'

        raise ImportError(
            "Aucun moteur OCR disponible. Installez Surya OCR ou EasyOCR."
        )

    def _get_easyocr_reader(self):
        """Charge EasyOCR seulement quand nécessaire (lazy loading)."""
        if self._easyocr_reader is None:
            import easyocr
            logger.info("Chargement du modèle EasyOCR...")
            self._easyocr_reader = easyocr.Reader(self.languages, gpu=False)
            logger.info("Modèle EasyOCR chargé")
        return self._easyocr_reader

    def _extract_text_from_image_easyocr(self, image_path: str) -> List[str]:
        reader = self._get_easyocr_reader()
        results = reader.readtext(image_path)
        return [text for (_, text, confidence) in results if confidence > 0.3]

    def _extract_text_from_image_surya(self, image_path: str) -> List[str]:
        """
        Extraction via Surya OCR.

        Cette implémentation essaie des points d'entrée courants pour rester
        robuste selon les versions. Si l'API Surya installée ne correspond pas,
        une exception est levée et le fallback est pris en charge au niveau appelant.
        """
        surya_module = importlib.import_module('surya_ocr')

        if hasattr(surya_module, 'extract_text_from_image'):
            result = surya_module.extract_text_from_image(
                image_path,
                languages=self.languages
            )
            if isinstance(result, list):
                return [str(item) for item in result if str(item).strip()]
            if isinstance(result, str):
                return [result] if result.strip() else []

        if hasattr(surya_module, 'extract_text'):
            result = surya_module.extract_text(image_path, languages=self.languages)
            if isinstance(result, list):
                return [str(item) for item in result if str(item).strip()]
            if isinstance(result, str):
                return [result] if result.strip() else []

        raise RuntimeError(
            "API Surya OCR non reconnue. Attendu: extract_text_from_image() ou extract_text()."
        )

    def extract(self, file_path: str) -> Dict:
        """
        Extrait le texte d'un PDF scanné ou d'une image.

        Formats supportés : .pdf (scanné), .png, .jpg, .jpeg, .tiff, .bmp

        Returns:
            dict avec success, text, pages, method, needs_ocr, error
        """
        logger.info(f"Début extraction OCR: {file_path}")

        start_time = time.perf_counter()

        result = {
            'success': False,
            'text': '',
            'pages': 0,
            'method': 'ocr',
            'needs_ocr': True,
            'engine': None,
            'seconds_total': 0.0,
            'seconds_per_page': 0.0,
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
            engine = self._resolve_engine()
            result['engine'] = engine
            result['method'] = engine

            if suffix in image_formats:
                # Extraction directe sur image
                texts = self.extract_text_from_image(str(path), engine=engine)
                result['pages'] = 1

            else:
                # PDF scanné : convertir chaque page en image puis OCR
                texts, num_pages = self.extract_text_from_scanned_pdf(str(path), engine=engine)
                result['pages'] = num_pages

            full_text = '\n'.join(texts).strip()
            result['text'] = full_text

            if not full_text:
                result['error'] = "Aucun texte détecté par l'OCR"
                logger.warning(result['error'])
                elapsed = time.perf_counter() - start_time
                result['seconds_total'] = round(elapsed, 3)
                result['seconds_per_page'] = round(elapsed / max(result['pages'], 1), 3)
                return result

            result['success'] = True
            elapsed = time.perf_counter() - start_time
            result['seconds_total'] = round(elapsed, 3)
            result['seconds_per_page'] = round(elapsed / max(result['pages'], 1), 3)
            logger.info(f"OCR réussi: {len(full_text)} caractères sur {result['pages']} page(s)")
            return result

        except ImportError:
            result['error'] = "Aucun moteur OCR installé (Surya OCR / EasyOCR)"
            logger.error(result['error'])
            return result

        except Exception as e:
            result['error'] = f"Erreur OCR: {str(e)}"
            logger.exception(result['error'])
            elapsed = time.perf_counter() - start_time
            result['seconds_total'] = round(elapsed, 3)
            result['seconds_per_page'] = round(elapsed / max(result['pages'], 1), 3)
            return result

    def extract_text_from_image(self, image_path: str, engine: str = None) -> List[str]:
        """Extrait le texte d'une image (PNG/JPG/JPEG/TIFF/BMP/WEBP)."""
        selected_engine = engine or self._resolve_engine()

        if selected_engine == 'suryaocr':
            return self._extract_text_from_image_surya(image_path)

        return self._extract_text_from_image_easyocr(image_path)

    def extract_text_from_scanned_pdf(self, pdf_path: str, engine: str = None) -> Tuple[List[str], int]:
        """
        Convertit chaque page du PDF en image puis applique l'OCR.
        Utilise pdf2image pour la conversion PDF -> image.
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image n'est pas installé. "
                "Installez-le avec : pip install pdf2image"
            )

        import os
        import tempfile

        selected_engine = engine or self._resolve_engine()

        pages_images = convert_from_path(pdf_path, dpi=200)
        all_texts = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, page_img in enumerate(pages_images):
                img_path = os.path.join(tmp_dir, f"page_{i+1}.png")
                page_img.save(img_path, 'PNG')
                page_texts = self.extract_text_from_image(img_path, engine=selected_engine)
                all_texts.extend(page_texts)
                logger.info(f"Page {i+1}/{len(pages_images)} traitée")

        return all_texts, len(pages_images)
