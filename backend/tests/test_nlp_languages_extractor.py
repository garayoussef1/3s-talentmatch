"""Tests unitaires pour l'extraction de langues (NLPParser._extract_langues).

Objectif: augmenter le rappel sur les formats de niveau courants
(étoiles, 3/5, "Très bon", etc.) tout en restant robuste.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _langs(text: str):
    from app.services.nlp.nlp_parser import NLPParser

    return NLPParser._extract_langues(text)


def test_langues_etoiles():
    text = """
Langues
Français : ★★★★★
Anglais : ★★★☆☆
"""
    langues = _langs(text)
    assert any(l["langue"].lower().startswith("fran") for l in langues)
    assert any(l["langue"].lower().startswith("ang") for l in langues)


def test_langues_note_sur_5():
    text = """
Languages:
English: 4/5
French: 5/5
"""
    langues = _langs(text)
    assert any(l["langue"].lower() == "english" and l.get("niveau") for l in langues)
    assert any(l["langue"].lower() == "french" and l.get("niveau") for l in langues)


def test_langues_niveaux_fr_courants():
    text = """
Langues
Français - Très bon
Anglais - Bon
Arabe - Langue maternelle
"""
    langues = _langs(text)
    names = {l["langue"].lower() for l in langues}
    assert any("fran" in n for n in names)
    assert any("ang" in n for n in names)
    assert any("arab" in n for n in names)
