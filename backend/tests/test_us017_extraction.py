"""
US-017 — Tests extraction PDF et DOCX
Vérifie que CVExtractor retourne les bons champs pour chaque format.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from app.services.extraction.cv_extractor import CVExtractor


def make_extractor_with_mock_pdf(text="Jean Dupont Développeur Python", method="pypdf"):
    """Crée un CVExtractor avec _pdf_extractor mocké + path.exists=True."""
    extractor = CVExtractor()
    extractor._pdf_extractor = MagicMock()
    extractor._pdf_extractor.extract.return_value = {
        "success": True, "text": text, "method": method,
        "pages": 1, "needs_ocr": False, "error": None
    }
    return extractor


def make_extractor_with_mock_docx(text="Marie Martin Ingénieure DevOps", method="docx"):
    """Crée un CVExtractor avec _word_extractor mocké + path.exists=True."""
    extractor = CVExtractor()
    extractor._word_extractor = MagicMock()
    extractor._word_extractor.extract.return_value = {
        "success": True, "text": text, "method": method,
        "pages": 1, "needs_ocr": False, "error": None
    }
    return extractor


# ──────────────────────────────────────────────
# US-017 : Tests extraction
# ──────────────────────────────────────────────

class TestCVExtractorStructure:
    """Vérifie que le résultat a toujours les bons champs."""

    def test_result_has_success_field(self):
        extractor = make_extractor_with_mock_pdf()
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.pdf")
        assert "success" in result

    def test_result_has_text_field(self):
        extractor = make_extractor_with_mock_pdf()
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.pdf")
        assert "text" in result

    def test_result_has_method_field(self):
        extractor = make_extractor_with_mock_pdf()
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.pdf")
        assert "method" in result

    def test_result_has_pages_field(self):
        extractor = make_extractor_with_mock_pdf()
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.pdf")
        assert "pages" in result


class TestPDFExtraction:
    """Tests du flux d'extraction PDF."""

    def test_pdf_extraction_success(self):
        """Un PDF valide doit retourner success=True."""
        extractor = make_extractor_with_mock_pdf()
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.pdf")
        assert result["success"] is True

    def test_pdf_extraction_returns_text(self):
        """L'extraction PDF doit retourner du texte non vide."""
        extractor = make_extractor_with_mock_pdf(text="Jean Dupont Développeur Python")
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.pdf")
        assert len(result["text"]) > 0

    def test_pdf_extraction_method_is_pypdf_or_ocr(self):
        """La méthode doit être pypdf ou ocr."""
        extractor = make_extractor_with_mock_pdf(method="pypdf")
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.pdf")
        assert result["method"] in ("pypdf", "ocr", "pypdf+ocr", "pypdf+easyocr")


class TestDOCXExtraction:
    """Tests du flux d'extraction DOCX."""

    def test_docx_extraction_success(self):
        """Un DOCX valide doit retourner success=True."""
        extractor = make_extractor_with_mock_docx()
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.docx")
        assert result["success"] is True

    def test_docx_extraction_returns_text(self):
        """L'extraction DOCX doit retourner du texte non vide."""
        extractor = make_extractor_with_mock_docx(text="Marie Martin Ingénieure DevOps")
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.docx")
        assert len(result["text"]) > 0

    def test_docx_method_is_docx(self):
        """La méthode DOCX doit être 'docx'."""
        extractor = make_extractor_with_mock_docx(method="docx")
        with patch("pathlib.Path.exists", return_value=True):
            result = extractor.extract("cv.docx")
        assert result["method"] == "docx"


class TestErrorHandling:
    """Tests des cas d'erreur."""

    def test_nonexistent_file_returns_failure(self):
        """Un fichier inexistant doit retourner success=False."""
        extractor = CVExtractor()
        result = extractor.extract("fichier_qui_nexiste_pas.pdf")
        assert result["success"] is False

    def test_nonexistent_file_has_error_message(self):
        """Un fichier inexistant doit avoir un message d'erreur."""
        extractor = CVExtractor()
        result = extractor.extract("fichier_qui_nexiste_pas.pdf")
        assert result.get("error") is not None
        assert len(result["error"]) > 0

