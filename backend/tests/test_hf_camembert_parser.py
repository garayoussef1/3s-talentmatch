import os
import sys

import pytest


# Setup import path (repo backend)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.nlp.hf_camembert import HFCamembertNameExtractor  # noqa: E402


def test_parse_token_classification_response_groups_person_tokens():
    payload = [
        {"entity_group": "PER", "word": "Jean", "score": 0.99, "start": 0, "end": 4},
        {"entity_group": "PER", "word": "Dupont", "score": 0.98, "start": 5, "end": 11},
        {"entity_group": "ORG", "word": "ESPRIT", "score": 0.9, "start": 20, "end": 26},
    ]
    candidates = HFCamembertNameExtractor._parse_token_classification_response(payload)
    assert candidates
    assert candidates[0].text == "Jean Dupont"


def test_parse_token_classification_response_ignores_non_list_payload():
    assert HFCamembertNameExtractor._parse_token_classification_response({"a": 1}) == []


def test_parse_token_classification_response_handles_entity_field():
    payload = [
        {"entity": "PERSON", "word": "SARAH", "score": 0.95, "start": 0, "end": 5},
        {"entity": "PERSON", "word": "JOHNSON", "score": 0.94, "start": 6, "end": 13},
    ]
    candidates = HFCamembertNameExtractor._parse_token_classification_response(payload)
    assert candidates[0].text == "SARAH JOHNSON"
