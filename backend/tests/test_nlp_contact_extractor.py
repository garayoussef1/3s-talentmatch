import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.nlp.contact_extractor import ContactExtractor
from app.services.nlp.nlp_parser import NLPParser


class TestContactExtractor:
    def test_extract_email_and_phone(self):
        text = """
        Nom: Marie Martin
        Email: marie.martin@example.com
        Téléphone: +33 6 12 34 56 78
        """

        extractor = ContactExtractor()
        result = extractor.extract(text)

        assert result["primary_email"] == "marie.martin@example.com"
        assert result["primary_phone"] is not None
        assert len(result["emails"]) == 1
        assert len(result["phones"]) == 1

    def test_deduplicate_emails_case_insensitive(self):
        text = "Email: Test.User@Example.com ; Copie: test.user@example.com"

        extractor = ContactExtractor()
        result = extractor.extract(text)

        assert len(result["emails"]) == 1

    def test_ignore_too_short_phone_like_values(self):
        text = "Code: 1234, tél réel: +216 22 333 444"

        extractor = ContactExtractor()
        result = extractor.extract(text)

        assert any("216" in phone or "22" in phone for phone in result["phones"])
        assert all(len("".join(ch for ch in phone if ch.isdigit())) >= 8 for phone in result["phones"])


class TestNLPParserContactIntegration:
    def test_parse_populates_personal_info_contact_fields(self):
        parser = NLPParser()
        text = """
        CURRICULUM VITAE
        Nom: Youssef Test
        Email: youssef.test@example.com
        Téléphone: +216 22 333 444
        Compétences: Python, FastAPI, React, Docker.
        Expérience: Développeur Full Stack 2024-2026.
        """

        result = parser.parse(text, cv_id="cv-test-contact")

        assert result["success"] is True
        assert result["parsed_data"]["contacts"]["email"] == "youssef.test@example.com"
        assert result["parsed_data"]["contacts"]["telephone"] is not None
        assert result["parsed_data"]["metadata"]["confidence_score"] > 0
        assert result["parsed_data"]["metadata"]["parsed_at"] is not None
