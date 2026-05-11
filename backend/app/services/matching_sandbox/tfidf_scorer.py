"""
TF-IDF Scorer — Baseline de comparaison pour TalentMatch-BERT

But : prouver que TalentMatch-BERT > TF-IDF > aléatoire (0.5)

Principe :
  - Vectorise offre et CV avec TF-IDF (sklearn)
  - Calcule la similarité cosinus entre les deux vecteurs
  - Pas de IA, pas de réseau de neurones — méthode classique

Utilisation dans matching_sandbox uniquement (persisted=False).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.services.matching.match_engine import (
    _candidate_skills,
    _candidate_text_for_semantic,
    _extract_offer_skills,
    _offer_text_for_semantic,
)


class TFIDFMatchingScorer:
    """Scorer basé sur TF-IDF cosinus — baseline non-IA."""

    def __init__(self):
        self._vectorizer = None
        self._ready = False
        self._load_error: Optional[str] = None
        self._corpus_fitted = False
        self._init_vectorizer()

    def _init_vectorizer(self) -> None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
            self._vectorizer = TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),      # unigrammes + bigrammes
                max_features=8000,
                sublinear_tf=True,       # atténue les termes très fréquents
                min_df=1,
                strip_accents="unicode",
                lowercase=True,
            )
            self._ready = True
        except ImportError:
            self._ready = False
            self._load_error = "sklearn_not_installed"

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    @property
    def model_version(self) -> str:
        return "TF-IDF baseline (sklearn)"

    def _cosine_sim(self, vec_a, vec_b) -> float:
        """Similarité cosinus entre deux vecteurs sparse sklearn."""
        try:
            from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
            sim = float(cosine_similarity(vec_a, vec_b)[0][0])
            return max(0.0, min(1.0, sim))
        except Exception:
            return 0.5

    def score_semantic(self, offer_text: str, cv_text: str) -> Tuple[float, Dict[str, Any]]:
        if not self._ready or self._vectorizer is None:
            return 0.5, {"ready": False, "reason": self._load_error or "unavailable"}

        try:
            texts = [offer_text or "", cv_text or ""]
            tfidf_matrix = self._vectorizer.fit_transform(texts)
            sim = self._cosine_sim(tfidf_matrix[0], tfidf_matrix[1])
            return sim, {
                "ready": True,
                "method": "tfidf_cosine",
                "similarity": round(sim, 4),
            }
        except Exception as e:
            return 0.5, {"ready": False, "reason": f"error:{type(e).__name__}"}

    def score_skills(self, offer_skills: List[str], cv_skills: List[str]) -> Tuple[float, Dict[str, Any]]:
        """Chevauchement pondéré des skills (Jaccard étendu)."""
        if not offer_skills or not cv_skills:
            return 0.5, {"note": "no_skills"}

        offer_set = {s.lower().strip() for s in offer_skills if s}
        cv_set    = {s.lower().strip() for s in cv_skills if s}

        intersection = offer_set & cv_set
        if not offer_set:
            return 0.5, {"note": "empty_offer_skills"}

        # Précision côté offre : combien de skills requises sont dans le CV
        precision = len(intersection) / len(offer_set)

        return float(precision), {
            "offer_skills": len(offer_set),
            "cv_skills":    len(cv_set),
            "matched":      len(intersection),
            "precision":    round(precision, 4),
        }

    def score(self, offer: JobOffer, candidate: Candidate) -> Tuple[float, Dict[str, Any]]:
        offer_text = _offer_text_for_semantic(offer)
        cv_text    = _candidate_text_for_semantic(candidate)
        offer_skills = _extract_offer_skills(offer)
        cv_skills    = _candidate_skills(candidate)

        semantic_score, semantic_info = self.score_semantic(offer_text, cv_text)
        skills_score,   skills_info   = self.score_skills(offer_skills, cv_skills)

        # Pondération : 60% sémantique + 40% skills
        total = 0.6 * float(semantic_score) + 0.4 * float(skills_score)
        total = max(0.0, min(1.0, total))

        return total, {
            "tfidf_semantic": round(float(semantic_score), 4),
            "tfidf_skills":   round(float(skills_score), 4),
            "total":          round(float(total), 4),
            "semantic":       semantic_info,
            "skills":         skills_info,
            "model":          self.model_version,
            "ready":          self._ready,
        }
