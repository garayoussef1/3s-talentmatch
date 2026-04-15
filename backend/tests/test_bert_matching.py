from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer


def _mock_sentence_transformers_module(mock_model):
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = MagicMock(return_value=mock_model)
    return fake_module


def test_bert_semantic_score():
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1] * 384, [0.1] * 384], dtype=float)
    fake_mod = _mock_sentence_transformers_module(mock_model)

    with patch.dict(sys.modules, {"sentence_transformers": fake_mod}):
        scorer = BERTMatchingScorer()
        score, details = scorer.score_semantic("offer text", "cv text")

    assert 0.0 <= score <= 1.0
    assert details.get("model") == "paraphrase-multilingual-MiniLM-L12-v2"


def test_skill_inconsistency_detection():
    scorer = BERTMatchingScorer()
    inconsistencies = scorer.detect_skill_inconsistencies(
        cv_skills=["Kubernetes"],
        cv_experiences=[],
        cv_raw_text="Python Docker FastAPI",
    )

    assert any(
        i.get("skill") == "Kubernetes"
        and i.get("level") == 1
        and i.get("reason") == "absent_from_text"
        for i in inconsistencies
    )


def test_hybrid_scoring():
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1] * 384, [0.1] * 384], dtype=float)
    fake_mod = _mock_sentence_transformers_module(mock_model)

    offer = SimpleNamespace(
        titre="Python Backend Engineer",
        description="Need Python Docker and 2 years experience, bac+3",
        competences_requises=["Python", "Docker"],
        localisation="Tunis",
    )
    candidate = SimpleNamespace(
        raw_text="Python Docker backend development in Tunis",
        parsed_data={
            "competences": [{"name": "Python"}, {"name": "Docker"}],
            "experiences": [{"description": "Used Python and Docker in production"}],
            "metadata": {
                "annees_experience_totales": 3,
                "niveau_formation_max": 3,
            },
        },
    )

    with patch.dict(sys.modules, {"sentence_transformers": fake_mod}):
        scorer = BERTMatchingScorer()
        total, details = scorer.score(offer, candidate)

    assert 0.0 <= total <= 1.0
    assert details.get("ready") is True