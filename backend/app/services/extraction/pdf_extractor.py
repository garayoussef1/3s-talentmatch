"""
Module d'extraction de texte depuis des PDFs
Utilise pypdf pour extraction rapide de PDFs textuels
"""

from pypdf import PdfReader
from pathlib import Path
from typing import Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extracteur de texte pour PDFs textuels"""
    
    def __init__(self, min_text_length: int = 100):
        self.min_text_length = min_text_length
        logger.info("PDFExtractor initialisé")
    
    def extract(self, file_path: str) -> Dict:
        """
        Extrait le texte d'un fichier PDF
        
        Returns:
            dict avec success, text, pages, method, needs_ocr, error
        """
        logger.info(f"Début extraction: {file_path}")
        
        try:
            # Vérifier existence
            path = Path(file_path)
            if not path.exists():
                error_msg = f"Fichier non trouvé: {file_path}"
                logger.error(error_msg)
                return self._error_response(error_msg)
            
            # Vérifier extension
            if path.suffix.lower() != '.pdf':
                error_msg = f"Extension invalide: {path.suffix}"
                logger.error(error_msg)
                return self._error_response(error_msg)
            
            # Lire PDF
            reader = PdfReader(str(path))
            num_pages = len(reader.pages)
            
            logger.info(f"PDF chargé: {num_pages} page(s)")
            
            # Extraire texte
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                logger.debug(f"Page {i+1}: {len(page_text)} caractères")
            
            full_text = "\n\n".join(text_parts)
            cleaned_text = self._clean_text(full_text)
            
            # Vérifier si suffisant
            if len(cleaned_text) < self.min_text_length:
                logger.warning(f"Texte insuffisant. PDF probablement scanné.")
                return {
                    'success': False,
                    'text': cleaned_text,
                    'pages': num_pages,
                    'method': 'pypdf',
                    'needs_ocr': True,
                    'error': 'PDF scanné détecté - OCR nécessaire'
                }
            
            # Succès
            logger.info(f"Extraction réussie: {len(cleaned_text)} caractères")
            
            return {
                'success': True,
                'text': cleaned_text,
                'pages': num_pages,
                'method': 'pypdf',
                'needs_ocr': False,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Erreur extraction PDF: {str(e)}"
            logger.exception(error_msg)
            return self._error_response(error_msg)
    
    def _clean_text(self, text: str) -> str:
        """Nettoie le texte extrait"""
        if not text:
            return ""
        
        # Supprimer espaces multiples
        text = ' '.join(text.split())
        
        # Supprimer lignes vides
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
        
        cleaned = '\n'.join(lines)
        logger.debug(f"Nettoyage: {len(text)} -> {len(cleaned)} caractères")
        
        return cleaned
    
    def _error_response(self, error_msg: str) -> Dict:
        """Réponse d'erreur standardisée"""
        return {
            'success': False,
            'text': '',
            'pages': 0,
            'method': 'pypdf',
            'needs_ocr': False,
            'error': error_msg
        }


def extract_text_from_pdf(file_path: str) -> str:
    """Fonction simple pour extraction rapide"""
    extractor = PDFExtractor()
    result = extractor.extract(file_path)
    
    if result['success']:
        return result['text']
    else:
        raise Exception(result['error'])