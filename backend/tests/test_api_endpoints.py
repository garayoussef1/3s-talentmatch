"""
US-016 — Tests des endpoints FastAPI
GET /health
POST /api/upload-cv
GET /api/candidates
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

# ──────────────────────────────────────────────
# Fixture : BDD mockée (pas de vraie connexion PG)
# ──────────────────────────────────────────────

def override_get_db():
    db = MagicMock()
    db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.count.return_value = 0
    db.refresh = MagicMock()
    try:
        yield db
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ──────────────────────────────────────────────
# US-016 : Tests endpoints
# ──────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self):
        """GET /health doit retourner 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self):
        """GET /health doit retourner status='ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_service_name(self):
        """GET /health doit contenir le nom du service."""
        response = client.get("/health")
        data = response.json()
        assert "service" in data
        assert "TalentMatch" in data["service"]


class TestUploadCVEndpoint:
    def _make_pdf_file(self, content=b"%PDF-1.4 fake content", filename="test_cv.pdf"):
        return {"file": (filename, io.BytesIO(content), "application/pdf")}

    def _make_docx_file(self, filename="test_cv.docx"):
        # Minimal DOCX (ZIP header)
        docx_bytes = (
            b"PK\x03\x04\x14\x00\x00\x00\x08\x00"
            + b"\x00" * 30
        )
        return {"file": (filename, io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    def test_upload_returns_cv_id(self):
        """POST /api/upload-cv doit retourner un cv_id."""
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = {
                "success": True, "text": "Texte extrait du CV", "method": "pypdf"
            }
            response = client.post("/api/upload-cv", files=self._make_pdf_file())
        assert response.status_code == 200
        data = response.json()
        assert "cv_id" in data
        assert len(data["cv_id"]) == 36  # UUID format

    def test_upload_returns_filename(self):
        """POST /api/upload-cv doit retourner le nom du fichier."""
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = {
                "success": True, "text": "Texte", "method": "pypdf"
            }
            response = client.post("/api/upload-cv", files=self._make_pdf_file(filename="mon_cv.pdf"))
        assert response.status_code == 200
        assert response.json()["filename"] == "mon_cv.pdf"

    def test_upload_success_field_is_true(self):
        """POST /api/upload-cv doit retourner success=True."""
        with patch("app.routes.cv.CVExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = {
                "success": True, "text": "Texte", "method": "pypdf"
            }
            response = client.post("/api/upload-cv", files=self._make_pdf_file())
        assert response.json()["success"] is True

    def test_upload_no_file_returns_422(self):
        """POST /api/upload-cv sans fichier doit retourner 422."""
        response = client.post("/api/upload-cv")
        assert response.status_code == 422


class TestCandidatesEndpoint:
    def test_candidates_returns_200(self):
        """GET /api/candidates doit retourner 200."""
        response = client.get("/api/candidates")
        assert response.status_code == 200

    def test_candidates_returns_list(self):
        """GET /api/candidates doit retourner une liste."""
        response = client.get("/api/candidates")
        data = response.json()
        assert "candidates" in data
        assert isinstance(data["candidates"], list)

    def test_candidates_returns_total(self):
        """GET /api/candidates doit retourner le total."""
        response = client.get("/api/candidates")
        data = response.json()
        assert "total" in data
        assert isinstance(data["total"], int)
