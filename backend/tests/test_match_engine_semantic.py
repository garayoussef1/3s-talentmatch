from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.matching.match_engine import MatchEngine


def _offer(**kwargs):
    defaults = {
        "titre": "Data Scientist",
        "description": "We are looking for a data scientist with NLP experience. Python, machine learning.",
        "competences_requises": ["Python", "NLP"],
        "localisation": "Tunis",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _candidate(**kwargs):
    defaults = {
        "raw_text": "Experienced Data Scientist. NLP, Python, spaCy, Transformers. Based in Tunis.",
        "parsed_data": {
            "metadata": {
                "annees_experience_totales": 3,
                "niveau_formation_max": 5,
            },
            "competences": ["Python", "spaCy", "NLP"],
        },
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_semantic_component_present_and_score_in_range() -> None:
    engine = MatchEngine(enable_semantic=True)
    score, details = engine.score(_offer(), _candidate())

    assert 0.0 <= score <= 1.0
    assert "semantic" in details["components"]
    assert 0.0 <= details["components"]["semantic"]["score"] <= 1.0


def test_semantic_disabled_sets_weight_to_zero() -> None:
    engine = MatchEngine(enable_semantic=False)
    score, details = engine.score(_offer(), _candidate())

    assert 0.0 <= score <= 1.0
    assert details["weights_raw"]["semantic"] == 0.0
    assert details["weights"]["semantic"] == 0.0


def test_semantic_fallback_neutral_when_text_too_short() -> None:
    engine = MatchEngine(enable_semantic=True)
    short_cand = _candidate(raw_text="too short")
    score, details = engine.score(_offer(), short_cand)

    sem = details["components"]["semantic"]
    assert sem["score"] == pytest.approx(0.5)
    assert sem.get("note") in {"text_too_short", "no_vectors_or_model", None}  # selon runtime


def test_semantic_auto_lang_uses_candidate_metadata() -> None:
    engine = MatchEngine(enable_semantic=True, semantic_lang=None)
    cand = _candidate(
        raw_text="Experienced Software Engineer. Python, APIs, FastAPI. Based in London.",
        parsed_data={
            "metadata": {"langue_cv": "en", "annees_experience_totales": 4, "niveau_formation_max": 5},
            "competences": ["Python", "FastAPI"],
        },
    )
    score, details = engine.score(_offer(localisation="London"), cand)
    assert 0.0 <= score <= 1.0
    assert details["components"]["semantic"].get("lang") == "en"
