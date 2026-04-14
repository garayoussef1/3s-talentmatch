"""
Détecteur de langue pour CVs.
Utilisé par NLPParser pour choisir le bon modèle spaCy (FR/EN).
"""
from __future__ import annotations
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Mots-clés discriminants pour détection rapide sans dépendance externe
_FR_SIGNALS = frozenset([
    "expérience", "experience", "formation", "compétences", "competences",
    "diplôme", "diplome", "entreprise", "poste", "missions", "responsabilités",
    "baccalauréat", "licence", "master", "ingénieur", "développeur",
    "stagiaire", "alternant", "langues", "niveaux", "courant", "natif",
    "présent", "actuel", "depuis", "jusqu", "objet", "objectif",
])

_EN_SIGNALS = frozenset([
    "experience", "education", "skills", "objective", "summary", "profile",
    "position", "responsibilities", "achievements", "projects", "certifications",
    "bachelor", "master", "degree", "university", "college", "internship",
    "present", "current", "since", "fluent", "native", "proficient",
    "worked", "developed", "managed", "designed", "implemented",
])


def _keyword_detect(text: str) -> Tuple[str, float]:
    """
    Détection rapide par comptage de mots-clés FR vs EN.
    Utilisé comme fallback si langdetect n'est pas disponible.
    """
    sample = text[:2000].lower()
    words = set(sample.split())

    fr_hits = len(words & _FR_SIGNALS)
    en_hits = len(words & _EN_SIGNALS)

    total = fr_hits + en_hits
    if total == 0:
        return "fr", 0.5

    if fr_hits > en_hits:
        return "fr", round(fr_hits / total, 2)
    elif en_hits > fr_hits:
        return "en", round(en_hits / total, 2)
    else:
        return "fr", 0.5  # Tie → défaut FR


def detect_language(text: str) -> Dict:
    """
    Détecte la langue principale d'un CV.

    Returns:
        {
            "langue": "fr" | "en",
            "confiance": 0.0–1.0,
            "bilingue": bool,
            "methode": "langdetect" | "keywords",
            "langues_detectees": [("fr", 0.95), ...]
        }
    """
    if not text or len(text.strip()) < 20:
        return {
            "langue": "fr",
            "confiance": 0.5,
            "bilingue": False,
            "methode": "default",
            "langues_detectees": [("fr", 0.5)],
        }

    # ── Tentative avec langdetect ────────────────────────────────
    try:
        from langdetect import detect_langs  # type: ignore

        # Analyser les 800 premiers caractères (plus représentatifs que 500)
        sample = text[:800]
        raw = detect_langs(sample)

        # Filtrer uniquement FR et EN (ignorer autres langues détectées)
        fr_en = [(l.lang, round(l.prob, 3)) for l in raw if l.lang in ("fr", "en")]

        if not fr_en:
            # Langue non FR/EN → on fait le keyword detect pour arbitrer
            langue_kw, conf_kw = _keyword_detect(text)
            return {
                "langue": langue_kw,
                "confiance": conf_kw,
                "bilingue": False,
                "methode": "keywords_fallback",
                "langues_detectees": [(l.lang, round(l.prob, 3)) for l in raw[:3]],
            }

        # Tri par probabilité décroissante
        fr_en.sort(key=lambda x: x[1], reverse=True)
        langue_principale = fr_en[0][0]
        confiance = fr_en[0][1]

        # Bilingue si 2ème langue > 30% de probabilité
        bilingue = len(fr_en) > 1 and fr_en[1][1] > 0.30

        logger.debug(
            "Langue détectée : %s (%.0f%%) — bilingue=%s",
            langue_principale, confiance * 100, bilingue,
        )

        return {
            "langue": langue_principale,
            "confiance": confiance,
            "bilingue": bilingue,
            "methode": "langdetect",
            "langues_detectees": fr_en,
        }

    except ImportError:
        logger.warning("langdetect non installé — utilisation détection par mots-clés")
    except Exception as e:
        logger.warning("Erreur langdetect (%s) — fallback mots-clés", e)

    # ── Fallback : mots-clés ─────────────────────────────────────
    langue_kw, conf_kw = _keyword_detect(text)
    return {
        "langue": langue_kw,
        "confiance": conf_kw,
        "bilingue": False,
        "methode": "keywords",
        "langues_detectees": [(langue_kw, conf_kw)],
    }
