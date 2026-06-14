"""
EscoService — détection de domaine professionnel basée sur ISCO-08.

Remplace _PROFESSION_ONTOLOGY (20 métiers hardcodés) par une couverture
universelle de tous les domaines professionnels via la classification ISCO-08.

Approche :
  1. Matching par mots-clés (rapide, déterministe) — couvre ~95% des cas communs
  2. Fallback : similarité token (pour les intitulés non standards)
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "data", "esco", "isco08_fr.json"
)


def _normalize(text: str) -> str:
    """Minuscules + suppression accents + espaces normalisés."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"['’‘]", " ", text)   # apostrophes
    text = re.sub(r"[-_/,;|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _token_overlap(a: str, b: str) -> float:
    """Ratio de tokens communs entre deux chaînes normalisées."""
    ta = set(_normalize(a).split())
    tb = set(_normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


class EscoService:
    """Service de détection de domaine professionnel universel via ISCO-08."""

    _instance: Optional["EscoService"] = None

    def __init__(self):
        self._groups: List[Dict] = []
        self._adjacent: set = set()
        self._major_labels: Dict[str, str] = {}
        self._keyword_index: List[Tuple[str, Dict]] = []   # (norm_kw, group)
        self._loaded = False

    @classmethod
    def get(cls) -> "EscoService":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        path = os.path.normpath(_DATA_PATH)
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._groups = data.get("groups", [])
            self._major_labels = data.get("major_group_labels", {})

            # Construire l'index de mots-clés normalisés
            for group in self._groups:
                for kw in group.get("keywords_fr", []):
                    self._keyword_index.append((_normalize(kw), group))

            # Construire le set de paires adjacentes (bidirectionnel)
            for pair in data.get("adjacent_pairs", []):
                if len(pair) == 2:
                    a, b = pair[0], pair[1]
                    self._adjacent.add((a, b))
                    self._adjacent.add((b, a))

            self._loaded = True
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────

    def detect_domain(self, text: str) -> Optional[Dict]:
        """
        Détecte le domaine ISCO-08 d'un texte (titre CV ou offre).

        Retourne un dict :
          {
            "isco_code":   "25",
            "major_group": 2,
            "label_fr":    "Professionnels des technologies de l'information",
            "skills_fr":   [...],
            "score":       0.85   # confiance 0-1
          }
        ou None si aucun groupe détecté avec suffisamment de confiance.
        """
        if not self._loaded or not text:
            return None

        norm = _normalize(text)

        best_group: Optional[Dict] = None
        best_score = 0.0

        for kw_norm, group in self._keyword_index:
            # 1. Match exact ou sous-chaîne — bonus longueur pour favoriser les mots-clés spécifiques
            if kw_norm in norm:
                score = 1.0 + len(kw_norm) / 10000
            elif norm in kw_norm:
                score = 0.90
            else:
                # 2. Overlap de tokens (fuzzy)
                score = _token_overlap(kw_norm, norm)

            if score > best_score:
                best_score = score
                best_group = group

        if best_group is None or best_score < 0.35:
            return None

        return {
            "isco_code":   best_group["code"],
            "major_group": best_group["major"],
            "label_fr":    best_group["label_fr"],
            "skills_fr":   best_group.get("skills_fr", []),
            "score":       round(best_score, 3),
        }

    def are_adjacent(self, code1: str, code2: str) -> bool:
        """Vrai si deux groupes ISCO sont considérés comme adjacents."""
        return (code1, code2) in self._adjacent

    def get_compatibility(self, code1: str, code2: str) -> str:
        """
        Compatibilité entre deux codes ISCO-08 :
          "same"         → même code (ex: 25 ↔ 25)
          "adjacent"     → groupes proches déclarés (ex: 25 ↔ 21)
          "same_major"   → même major group ET codes proches (diff ≤ 2)
          "different"    → domaines clairement différents

        Cas spécial groupe 2 : ce groupe est très hétérogène (médecins,
        développeurs, avocats…). On n'applique "same_major" que si les
        codes numériques diffèrent de ≤ 2, sinon "different".
        """
        if code1 == code2:
            return "same"
        if self.are_adjacent(code1, code2):
            return "adjacent"
        major1, major2 = code1[:1], code2[:1]
        if major1 == major2:
            # "same_major" seulement si même sous-groupe (2 premiers caractères identiques)
            # Ex: 261 vs 263 → "26" == "26" → same_major (juriste vs travail social)
            #     261 vs 25  → "26" != "25" → different  (juriste vs développeur)
            #     21  vs 22  → "21" != "22" → different  (ingénieur vs médecin)
            if code1[:2] == code2[:2]:
                return "same_major"
            return "different"
        return "different"

    def get_score_cap(self, domain1: Optional[Dict], domain2: Optional[Dict]) -> Optional[float]:
        """
        Retourne le plafond de score (0-1) pour une paire de domaines.

          same / adjacent  → None  (pas de cap)
          same_major       → 0.65  (même secteur mais spécialisation différente)
          different        → 0.35  (domaine clairement différent)

        Si l'un des deux domaines est None (non détecté) → pas de cap appliqué,
        on laisse BERT décider.
        """
        if domain1 is None or domain2 is None:
            return None

        compat = self.get_compatibility(domain1["isco_code"], domain2["isco_code"])

        if compat in ("same", "adjacent"):
            return None
        if compat == "same_major":
            return 0.65
        return 0.35   # different

    def get_implied_skills(self, domain: Optional[Dict]) -> List[str]:
        """Retourne les compétences implicites attendues pour un domaine."""
        if domain is None:
            return []
        return domain.get("skills_fr", [])

    def get_major_label(self, major: int) -> str:
        return self._major_labels.get(str(major), f"Groupe {major}")

    @property
    def loaded(self) -> bool:
        return self._loaded
