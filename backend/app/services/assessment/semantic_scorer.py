"""
Scoring sémantique des questions ouvertes (Module 2 du "Reality Gap Score").

Principe : on encode la réponse du candidat avec BGE-M3 (déjà utilisé par le
matching → on réutilise la même instance, pas de second chargement) puis on
mesure sa similarité cosinus avec 3 réponses de référence pré-encodées
(experte / correcte / faible). Le score 0-100 interpole entre ces ancres.

100% local (BGE-M3 embarqué, aucune API externe).
"""
from __future__ import annotations

import numpy as np

# Ancres de score associées à chaque réponse de référence
_ANCHORS = {"faible": 25.0, "correct": 62.0, "expert": 95.0}
# Température du softmax : amplifie l'écart de similarité vers la réf la plus proche
_TEMPERATURE = 12.0
# Pénalité si réponse trop courte (< 30 mots)
_MIN_WORDS = 30
_SHORT_PENALTY = 0.6

_scorer = None  # singleton BERTMatchingScorer (réutilise BGE-M3)


def _embedder():
    """Réutilise le BGE-M3 déjà chargé par le moteur de matching."""
    global _scorer
    if _scorer is None:
        from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
        _scorer = BERTMatchingScorer()
        _scorer._get_model()  # chargement paresseux
    return _scorer


def embed(texts: list[str]):
    """Encode une liste de textes en vecteurs normalisés (ou None si indispo)."""
    model = _embedder()._get_model()
    if model is None:
        return None
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


def _cosine(a, b) -> float:
    """Cosinus entre deux vecteurs (déjà normalisés → produit scalaire)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return 0.0
    return float(np.dot(a, b))


def score_open_answer(answer: str, emb_faible, emb_correct, emb_expert) -> dict:
    """Note une réponse ouverte (0-100) par interpolation vers les 3 références.

    Retourne {score, similarites, penalise}.
    """
    answer = (answer or "").strip()
    if not answer:
        return {"score": 0.0, "similarites": {}, "penalise": True}

    vecs = embed([answer])
    if vecs is None:
        return {"score": 0.0, "similarites": {}, "penalise": False, "erreur": "modele_indisponible"}
    v = vecs[0]

    sims = {
        "faible":  _cosine(v, emb_faible),
        "correct": _cosine(v, emb_correct),
        "expert":  _cosine(v, emb_expert),
    }

    # Softmax pondéré : la référence la plus proche domine le score final
    labels = ["faible", "correct", "expert"]
    s = np.array([sims[l] for l in labels])
    w = np.exp(s * _TEMPERATURE)
    w = w / w.sum()
    anchors = np.array([_ANCHORS[l] for l in labels])
    score = float(np.dot(w, anchors))

    # Pénalité de longueur (réponse bâclée)
    penalise = len(answer.split()) < _MIN_WORDS
    if penalise:
        score *= _SHORT_PENALTY

    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "similarites": {k: round(val, 3) for k, val in sims.items()},
        "penalise": penalise,
    }
