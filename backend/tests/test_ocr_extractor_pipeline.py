import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.ocr_extractor import OCRExtractor
from app.services.extraction.cv_extractor import CVExtractor


class TestOCRExtractorCore:
    def test_missing_file_returns_error(self):
        extractor = OCRExtractor()
        result = extractor.extract("file_not_found_ocr.pdf")

        assert result["success"] is False
        assert "Fichier non trouvé" in result["error"]

    def test_unsupported_format_returns_error(self, tmp_path):
        invalid_file = tmp_path / "notes.txt"
        invalid_file.write_text("hello", encoding="utf-8")

        extractor = OCRExtractor()
        result = extractor.extract(str(invalid_file))

        assert result["success"] is False
        assert "Format non supporté" in result["error"]

    def test_extract_text_from_image_uses_selected_engine(self, tmp_path, monkeypatch):
        image_file = tmp_path / "cv.png"
        image_file.write_bytes(b"fake-image")

        extractor = OCRExtractor(preferred_engine="easyocr")

        monkeypatch.setattr(extractor, "_resolve_engine", lambda: "easyocr")
        monkeypatch.setattr(
            extractor,
            "_extract_text_from_image_easyocr",
            lambda _: ["Nom: Test", "Email: test@example.com"]
        )

        result = extractor.extract(str(image_file))

        assert result["success"] is True
        assert "test@example.com" in result["text"]
        assert result["engine"] == "easyocr"
        assert result["seconds_per_page"] >= 0

    def test_extract_scanned_pdf_via_mocked_pipeline(self, tmp_path, monkeypatch):
        pdf_file = tmp_path / "scan.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        extractor = OCRExtractor(preferred_engine="easyocr")

        monkeypatch.setattr(extractor, "_resolve_engine", lambda: "easyocr")
        monkeypatch.setattr(
            extractor,
            "extract_text_from_scanned_pdf",
            lambda _pdf, engine=None: (["Profil", "Python FastAPI"], 1)
        )

        result = extractor.extract(str(pdf_file))

        assert result["success"] is True
        assert result["pages"] == 1
        assert "Python FastAPI" in result["text"]


class TestUniversalPipelineFallback:
    def test_cv_extractor_fallback_when_pdf_text_fails(self, monkeypatch):
        extractor = CVExtractor()

        monkeypatch.setattr(
            extractor._pdf_extractor,
            "extract",
            lambda _: {
                "success": False,
                "text": "",
                "pages": 1,
                "method": "pypdf",
                "needs_ocr": True,
                "error": "PDF scanné détecté - OCR nécessaire",
            },
        )

        monkeypatch.setattr(
            extractor._ocr_extractor,
            "extract",
            lambda _: {
                "success": True,
                "text": "Nom: Youssef Test\nEmail: youssef.test@example.com",
                "pages": 1,
                "method": "easyocr",
                "engine": "easyocr",
                "needs_ocr": False,
                "seconds_total": 0.2,
                "seconds_per_page": 0.2,
                "error": None,
            },
        )

        class DummyPath:
            suffix = ".pdf"
            name = "cv_scanned.pdf"

            def exists(self):
                return True

        monkeypatch.setattr("app.services.extraction.cv_extractor.Path", lambda _: DummyPath())

        result = extractor.extract("cv_scanned.pdf")

        assert result["success"] is True
        assert result["method"] == "pypdf+ocr"
        assert result["format"] == ".pdf"


class TestMixedBatchQuality:
    def test_success_rate_over_85_on_10_mixed_cvs(self, tmp_path, monkeypatch):
        extractor = CVExtractor()

        files = []
        for i in range(4):
            f = tmp_path / f"text_{i}.pdf"
            f.write_bytes(b"%PDF-text")
            files.append(f)

        for i in range(3):
            f = tmp_path / f"scanned_{i}.pdf"
            f.write_bytes(b"%PDF-scan")
            files.append(f)

        for i in range(3):
            f = tmp_path / f"img_{i}.jpg"
            f.write_bytes(b"image")
            files.append(f)

        def fake_pdf_extract(path):
            if "scanned_" in path:
                return {
                    "success": False,
                    "text": "",
                    "pages": 1,
                    "method": "pypdf",
                    "needs_ocr": True,
                    "error": "PDF scanné détecté - OCR nécessaire",
                }
            return {
                "success": True,
                "text": "CV textuel avec contenu exploitable",
                "pages": 1,
                "method": "pypdf",
                "needs_ocr": False,
                "error": None,
            }

        def fake_ocr_extract(path):
            return {
                "success": True,
                "text": f"Texte OCR extrait de {Path(path).name}",
                "pages": 1,
                "method": "easyocr",
                "engine": "easyocr",
                "needs_ocr": False,
                "seconds_total": 0.8,
                "seconds_per_page": 0.8,
                "error": None,
            }

        monkeypatch.setattr(extractor._pdf_extractor, "extract", fake_pdf_extract)
        monkeypatch.setattr(extractor._ocr_extractor, "extract", fake_ocr_extract)

        success_count = 0
        for file_path in files:
            result = extractor.extract(str(file_path))
            if result["success"]:
                success_count += 1

        success_rate = success_count / len(files)
        assert len(files) == 10
        assert success_rate > 0.85
