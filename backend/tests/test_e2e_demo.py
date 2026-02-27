"""
US-032 — Test End-to-End : Scénario de démonstration complet
============================================================
Simule le parcours complet : upload d'un CV → récupération dans la liste candidats.
Ce test valide l'intégration des couches API + extraction + persistance (mock DB).
"""
import io
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db


# ─── Fixture : mock base de données ─────────────────────────────────────────

def get_db_mock():
    """Base de données mockée — pas de connexion PostgreSQL réelle."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    yield db


app.dependency_overrides[get_db] = get_db_mock
client = TestClient(app)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_pdf_file(name="cv_demo.pdf", content=b"%PDF-1.4 CV Demo Content"):
    return {"file": (name, io.BytesIO(content), "application/pdf")}


def make_docx_file(name="cv_demo.docx"):
    # Minimal DOCX magic bytes (PK header)
    content = b"PK\x03\x04" + b"\x00" * 50
    return {"file": (name, io.BytesIO(content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}


# ─── E2E Scénario 1 : Upload PDF → vérification réponse JSON ────────────────

class TestE2EUploadPDF:

    def test_e2e_upload_pdf_retourne_200(self):
        """Scénario E2E : un recruteur uploade un CV PDF et obtient un cv_id."""
        mock_extraction = {
            "success": True,
            "text": "Marie Dupont\nDéveloppeuse Python\nParis",
            "method": "pypdf",
            "pages": 1,
        }
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = mock_extraction
            response = client.post("/api/upload-cv", files=make_pdf_file())

        assert response.status_code == 200

    def test_e2e_upload_pdf_contient_cv_id(self):
        """Le JSON de réponse contient un cv_id UUID valide."""
        import uuid
        mock_extraction = {"success": True, "text": "CV content", "method": "pypdf", "pages": 1}
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = mock_extraction
            response = client.post("/api/upload-cv", files=make_pdf_file())

        data = response.json()
        assert "cv_id" in data
        # Vérifie que c'est un UUID valide
        uuid.UUID(data["cv_id"])

    def test_e2e_upload_pdf_contient_method(self):
        """La méthode d'extraction est indiquée dans la réponse."""
        mock_extraction = {"success": True, "text": "CV content", "method": "pypdf", "pages": 1}
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = mock_extraction
            response = client.post("/api/upload-cv", files=make_pdf_file())

        data = response.json()
        assert data["method"] in ("pypdf", "ocr", "unknown")

    def test_e2e_upload_pdf_contient_text_preview(self):
        """Un aperçu du texte extrait est inclus dans la réponse."""
        mock_extraction = {
            "success": True,
            "text": "Marie Dupont\nDéveloppeuse Python\nParis",
            "method": "pypdf",
            "pages": 1,
        }
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = mock_extraction
            response = client.post("/api/upload-cv", files=make_pdf_file())

        data = response.json()
        assert "text_preview" in data
        assert isinstance(data["text_preview"], str)


# ─── E2E Scénario 2 : Upload DOCX ────────────────────────────────────────────

class TestE2EUploadDOCX:

    def test_e2e_upload_docx_retourne_200(self):
        """Scénario E2E : upload d'un CV Word."""
        mock_extraction = {"success": True, "text": "Ahmed Ben Ali\nIngénieur Data", "method": "docx", "pages": 1}
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = mock_extraction
            response = client.post("/api/upload-cv", files=make_docx_file())

        assert response.status_code == 200

    def test_e2e_upload_docx_method_est_docx(self):
        """La méthode rapportée pour un DOCX est 'docx'."""
        mock_extraction = {"success": True, "text": "Ahmed Ben Ali", "method": "docx", "pages": 1}
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = mock_extraction
            response = client.post("/api/upload-cv", files=make_docx_file())

        assert response.json()["method"] == "docx"


# ─── E2E Scénario 3 : Consultation liste candidats ────────────────────────────

class TestE2ECandidatesList:

    def setup_method(self):
        """Mock DB qui retourne une liste de candidats simulés."""
        from datetime import datetime
        candidate = MagicMock()
        candidate.cv_id = "abc-123"
        candidate.filename = "cv_demo.pdf"
        candidate.nom = "Marie Dupont"
        candidate.email = "marie@example.com"
        candidate.extraction_method = "pypdf"
        candidate.created_at = datetime(2026, 2, 27, 10, 0, 0)

        db_with_data = MagicMock()
        query_mock = MagicMock()
        query_mock.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [candidate]
        query_mock.count.return_value = 1
        db_with_data.query.return_value = query_mock

        def override():
            yield db_with_data

        app.dependency_overrides[get_db] = override

    def teardown_method(self):
        app.dependency_overrides[get_db] = get_db_mock

    def test_e2e_candidates_retourne_200(self):
        """L'endpoint /api/candidates répond 200."""
        response = client.get("/api/candidates")
        assert response.status_code == 200

    def test_e2e_candidates_contient_total(self):
        """La réponse inclut le champ 'total'."""
        response = client.get("/api/candidates")
        data = response.json()
        assert "total" in data
        assert data["total"] == 1

    def test_e2e_candidates_contient_liste(self):
        """La réponse inclut la liste 'candidates'."""
        response = client.get("/api/candidates")
        data = response.json()
        assert "candidates" in data
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["filename"] == "cv_demo.pdf"


# ─── E2E Scénario 4 : Rejets et erreurs ──────────────────────────────────────

class TestE2EValidation:

    def test_e2e_format_invalide_retourne_400(self):
        """Fichier .txt → rejet 400 avec message d'erreur."""
        files = {"file": ("cv.txt", io.BytesIO(b"contenu texte brut"), "text/plain")}
        response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 400
        assert "Format" in response.json()["detail"] or "format" in response.json()["detail"].lower()

    def test_e2e_fichier_trop_grand_retourne_413(self):
        """Fichier > 10 Mo → rejet 413."""
        big_content = b"%PDF-1.4 " + b"x" * (10 * 1024 * 1024 + 1)
        files = {"file": ("cv_gros.pdf", io.BytesIO(big_content), "application/pdf")}
        response = client.post("/api/upload-cv", files=files)
        assert response.status_code == 413

    def test_e2e_sans_fichier_retourne_422(self):
        """Requête sans fichier → 422 Unprocessable Entity."""
        response = client.post("/api/upload-cv")
        assert response.status_code == 422
