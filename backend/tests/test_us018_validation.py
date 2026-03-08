"""
US-018 — Tests validation des formats et des erreurs
Format invalide → 400
Fichier trop grand → 413
Champ manquant → 422
"""

import io
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.database import get_db


def override_get_db():
    db = MagicMock()
    db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.count.return_value = 0
    db.refresh = MagicMock()
    yield db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ──────────────────────────────────────────────
# US-018 : Tests de validation
# ──────────────────────────────────────────────

class TestFormatValidation:
    """Vérifie que les formats non supportés sont rejetés avec 400."""

    def test_txt_file_returns_400(self):
        """Un fichier .txt doit être rejeté avec 400."""
        files = {"file": ("cv.txt", io.BytesIO(b"Ceci est un cv"), "text/plain")}
        response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 400

    def test_jpg_file_returns_200_or_500(self):
        """Un fichier .jpg est maintenant accepté (OCR EasyOCR)."""
        files = {"file": ("cv.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")}
        response = client.post("/api/upload-cv", files=files)
        # 200 si OCR réussit, 500 si contenu invalide — mais PAS 400
        assert response.status_code != 400

    def test_xlsx_file_returns_400(self):
        """Un fichier .xlsx doit être rejeté avec 400."""
        files = {"file": ("data.xlsx", io.BytesIO(b"PK fake xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 400

    def test_exe_file_returns_400(self):
        """Un fichier .exe doit être rejeté avec 400."""
        files = {"file": ("virus.exe", io.BytesIO(b"MZ fake exe"), "application/octet-stream")}
        response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 400

    def test_error_message_mentions_format(self):
        """Le message d'erreur doit mentionner le format non supporté."""
        files = {"file": ("cv.txt", io.BytesIO(b"test"), "text/plain")}
        response = client.post("/api/upload-cv", files=files)
        assert "detail" in response.json()
        assert ".txt" in response.json()["detail"] or "supporté" in response.json()["detail"]


class TestFileSizeValidation:
    """Vérifie que les fichiers trop volumineux sont rejetés avec 413."""

    def test_file_over_10mb_returns_413(self):
        """Un fichier > 10 Mo doit retourner 413."""
        big_content = b"%PDF " + b"x" * (11 * 1024 * 1024)  # 11 Mo
        files = {"file": ("gros_cv.pdf", io.BytesIO(big_content), "application/pdf")}
        response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 413

    def test_file_exactly_at_limit_is_accepted(self):
        """Un fichier à exactement 10 Mo doit être accepté (si extraction OK)."""
        content = b"%PDF " + b"x" * (10 * 1024 * 1024 - 5)  # exactement 10 Mo
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = {
                "success": True, "text": "text", "method": "pypdf"
            }
            files = {"file": ("cv_limite.pdf", io.BytesIO(content), "application/pdf")}
            response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 200


class TestMissingFieldValidation:
    """Vérifie les erreurs quand les champs obligatoires sont absents."""

    def test_no_file_returns_422(self):
        """POST sans fichier doit retourner 422 Unprocessable Entity."""
        response = client.post("/api/upload-cv")
        assert response.status_code == 422

    def test_valid_pdf_returns_200(self):
        """Un PDF valide doit retourner 200."""
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = {
                "success": True, "text": "Nom: Ahmed Email: ahmed@email.com",
                "method": "pypdf"
            }
            files = {"file": ("cv_valid.pdf", io.BytesIO(b"%PDF-1.4 valid"), "application/pdf")}
            response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 200

    def test_valid_docx_returns_200(self):
        """Un DOCX valide doit retourner 200."""
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = {
                "success": True, "text": "CV Sarah Martin", "method": "docx"
            }
            files = {"file": ("cv_valid.docx", io.BytesIO(b"PK fake docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 200
