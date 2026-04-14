import os
import sys

import pytest


# Setup import path (repo backend)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.nlp.entity_extractor import EntityExtractor  # noqa: E402
from app.services.nlp.hf_camembert import HFCamembertNameExtractor  # noqa: E402
from app.services.nlp.nlp_parser import NLPParser  # noqa: E402


class _DummyContactExtractor:
    def extract(self, text: str):
        return {
            "primary_email": None,
            "primary_phone": None,
            "emails": [],
            "phones": [],
            "linkedin": None,
            "github": None,
            "website": None,
            "address": None,
        }


class _DummySkillsExtractor:
    def extract(self, text: str):
        return {"skills": [], "by_category": {}, "total_skills": 0}


class _DummyFormationExtractor:
    def extract(self, text: str):
        return {"formations": [], "niveau_max": 0}


class _DummyExperienceExtractor:
    def extract(self, text: str):
        return {"experiences": [], "annees_experience_totales": 0}


def _make_parser(monkeypatch):
    parser = NLPParser(model_name="fr_core_news_md")
    parser._contact_extractor = _DummyContactExtractor()
    parser._skills_extractor = _DummySkillsExtractor()

    def _fake_load_model(self):
        # Évite de charger spaCy + initialise les extracteurs requis par parse()
        self._formation_extractor = _DummyFormationExtractor()
        self._experience_extractor = _DummyExperienceExtractor()
        return object()

    monkeypatch.setattr(NLPParser, "_load_model", _fake_load_model, raising=True)
    return parser


def test_name_resolution_prefers_hf_when_different(monkeypatch):
    parser = _make_parser(monkeypatch)

    monkeypatch.setattr(EntityExtractor, "extract_full_name", lambda self, text: "Alice Heuristic", raising=True)
    monkeypatch.setattr(HFCamembertNameExtractor, "extract_person_name", lambda self, text: "Alice IA", raising=True)

    text = "Alice Heuristic\nEmail: alice@example.com\n" + ("x" * 80)
    out = parser.parse(text, cv_id="cv-1")

    assert out["success"] is True
    assert out["parsed_data"]["identite"]["nom_complet"] == "Alice IA"

    md = out["parsed_data"]["metadata"]
    assert md["name_source"] == "hf_camembert_override"
    assert md["name_conflict"] is True
    assert md["name_candidates"]["entity_extractor"] == "Alice Heuristic"
    assert md["name_candidates"]["hf_camembert"] == "Alice IA"


def test_name_resolution_uses_entity_when_hf_none(monkeypatch):
    parser = _make_parser(monkeypatch)

    monkeypatch.setattr(EntityExtractor, "extract_full_name", lambda self, text: "Bob Martin", raising=True)
    monkeypatch.setattr(HFCamembertNameExtractor, "extract_person_name", lambda self, text: None, raising=True)

    text = "Bob Martin\n" + ("y" * 80)
    out = parser.parse(text, cv_id="cv-2")

    assert out["success"] is True
    assert out["parsed_data"]["identite"]["nom_complet"] == "Bob Martin"

    md = out["parsed_data"]["metadata"]
    assert md["name_source"] == "entity_extractor"
    assert md["name_conflict"] is False
    assert md["name_candidates"]["entity_extractor"] == "Bob Martin"
    assert md["name_candidates"]["hf_camembert"] is None
