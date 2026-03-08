"""
Fonctions utilitaires partagées par les extracteurs NLP — 3S TalentMatch.

Auteur  : Youssef Gara
Projet  : 3S TalentMatch — PFE ESPRIT 2025-2026
"""

from __future__ import annotations

import re
import logging
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)


# ================================================================
# Normalisation de texte
# ================================================================

def normalize_text(text: str) -> str:
    """Normalise le texte pour le matching :
    - Supprime les accents
    - Met en minuscules
    - Compacte les espaces
    """
    nfkd = unicodedata.normalize("NFKD", text)
    sans_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sans_accents.lower()).strip()


def strip_accents(text: str) -> str:
    """Supprime les accents sans changer la casse."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ================================================================
# Extraction de sections
# ================================================================

def extract_section(text: str, section_patterns: list[str],
                    next_section_patterns: Optional[list[str]] = None,
                    max_length: int = 5000) -> Optional[str]:
    """Extrait le contenu d'une section de CV.

    Args:
        text: Texte complet du CV.
        section_patterns: Patterns regex pour détecter le début de section.
        next_section_patterns: Patterns pour détecter la section suivante
            (fin de la section courante). Si None, utilise des patterns
            par défaut couvrant les sections classiques.
        max_length: Longueur max du contenu extrait (sécurité).

    Returns:
        Le contenu de la section ou None si non trouvée.
    """
    if not text:
        return None

    # Pattern de début de section
    header_re = re.compile(
        r"(?:^|\n)\s*(?:" + "|".join(section_patterns) + r")\s*[:：\-–—]?\s*\n?",
        re.IGNORECASE | re.MULTILINE,
    )

    match = header_re.search(text)
    if not match:
        return None

    start = match.end()

    # Pattern de section suivante (par défaut : tout titre de section courant)
    if next_section_patterns is None:
        from .config import SECTION_PATTERNS
        all_patterns: list[str] = []
        for patterns in SECTION_PATTERNS.values():
            all_patterns.extend(patterns)
        next_section_patterns = all_patterns

    next_re = re.compile(
        r"(?:^|\n)\s*(?:" + "|".join(next_section_patterns) + r")\s*[:：\-–—]?\s*(?:\n|$)",
        re.IGNORECASE | re.MULTILINE,
    )

    next_match = next_re.search(text, pos=start)
    if next_match:
        end = next_match.start()
    else:
        end = len(text)

    content = text[start:min(start + max_length, end)].strip()
    return content if content else None


# ================================================================
# Parsing de dates
# ================================================================

def parse_date_str(date_str: str) -> Optional[str]:
    """Tente de parser une chaîne de date et renvoie le format ISO YYYY-MM ou YYYY.

    Gère : "Janvier 2020", "01/2020", "2020", "Jan 2020", etc.
    """
    from .config import ALL_MONTHS

    date_str = date_str.strip()

    # Format MM/YYYY ou MM-YYYY
    m = re.match(r"(\d{1,2})[/\-](\d{4})", date_str)
    if m:
        month = int(m.group(1))
        year = int(m.group(2))
        if 1 <= month <= 12 and 1900 <= year <= 2100:
            return f"{year}-{month:02d}"

    # Format YYYY seul
    m = re.match(r"^(\d{4})$", date_str)
    if m:
        year = int(m.group(1))
        if 1900 <= year <= 2100:
            return str(year)

    # Format "Mois YYYY"
    lower = date_str.lower().strip()
    for month_name, month_num in ALL_MONTHS.items():
        pattern = rf"\b{re.escape(month_name)}\b[\s.,]*(\d{{4}})"
        m = re.search(pattern, lower)
        if m:
            year = int(m.group(1))
            if 1900 <= year <= 2100:
                return f"{year}-{month_num}"

    return None


# ================================================================
# Nettoyage de texte
# ================================================================

def clean_text_block(text: str) -> str:
    """Nettoie un bloc de texte extrait :
    - Supprime les lignes vides multiples
    - Réduit les espaces multiples
    - Strip les lignes
    """
    lines = text.splitlines()
    cleaned: list[str] = []
    prev_empty = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not prev_empty:
                cleaned.append("")
            prev_empty = True
        else:
            cleaned.append(stripped)
            prev_empty = False
    return "\n".join(cleaned).strip()


def is_likely_name(text: str) -> bool:
    """Détermine si un texte ressemble à un nom de personne.

    Heuristique : 2-4 mots, pas de chiffres, pas trop long.
    """
    text = text.strip()
    if not text or len(text) > 60:
        return False
    words = text.split()
    if len(words) < 2 or len(words) > 5:
        return False
    if re.search(r"\d", text):
        return False
    if re.search(r"[;:!?@#$%^&*(){}[\]]", text):
        return False
    return True
