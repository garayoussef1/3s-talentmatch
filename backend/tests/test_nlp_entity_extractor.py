import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import spacy

from app.services.nlp.entity_extractor import EntityExtractor
from app.services.nlp.nlp_parser import NLPParser


class TestEntityExtractor:
    def test_extract_full_name_from_nom_prefix(self):
        nlp = spacy.load("fr_core_news_md")
        extractor = EntityExtractor(nlp)

        text = """
        CURRICULUM VITAE
        Nom: Youssef Test
        Email: youssef.test@example.com
        """

        full_name = extractor.extract_full_name(text)
        assert full_name == "Youssef Test"

    def test_extract_full_name_from_person_entity_fallback(self):
        nlp = spacy.load("fr_core_news_md")
        extractor = EntityExtractor(nlp)

        text = """
        Marie Martin
        Email: marie.martin@example.com
        Compétences: Python, FastAPI
        """

        full_name = extractor.extract_full_name(text)
        assert full_name is not None
        assert len(full_name.split()) >= 2


class TestNLPParserEntityIntegration:
    def test_parse_populates_full_name_when_available(self):
        parser = NLPParser()

        text = """
        CURRICULUM VITAE
        Nom: Marie Martin
        Email: marie.martin@example.com
        Téléphone: +33 6 12 34 56 78
        Compétences: Python, FastAPI, React.
        Expérience: Ingénieure DevOps chez TechCorp 2021-2026.
        """

        result = parser.parse(text, cv_id="cv-test-name")

        assert result["success"] is True
        assert result["parsed_data"]["identite"]["nom_complet"] == "Marie Martin"
        assert result["parsed_data"]["metadata"]["confidence_score"] >= 0.4
