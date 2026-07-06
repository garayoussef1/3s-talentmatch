"""
Calcul du "Reality Gap Score" (Module 3).

Mesure l'écart entre le niveau DÉCLARÉ (dérivé du CV) et le niveau DÉMONTRÉ
(test adaptatif + questions ouvertes) pour les compétences clés du poste.

  gap_competence   = |niveau_declare - niveau_demontre| / 10
  reality_gap_score = moyenne pondérée des gaps (poids = importance dans l'offre)
  fiabilite_cv      = 100 - reality_gap_score * 100
  score_final_ajuste = matching_score * (0.7 + 0.3 * fiabilite_cv/100)

Seuils : < 0.15 « CV fiable » · 0.15-0.30 « À vérifier » · > 0.30 « Écart important ».
100% local, aucune dépendance externe.
"""
from __future__ import annotations

# Niveau textuel du CV → note 0-10 (quand renseigné, rare en pratique)
_LEVEL_MAP = {
    "débutant": 3.0, "debutant": 3.0,
    "intermédiaire": 5.0, "intermediaire": 5.0,
    "avancé": 7.5, "avance": 7.5,
    "expert": 9.5,
}
# Bonus de niveau déclaré selon la séniorité globale du CV
_SENIORITY_BONUS = {"junior": 0.0, "confirmé": 1.0, "confirme": 1.0,
                    "senior": 2.0, "expert": 2.0}


def _mentioned_in_experience(parsed: dict, name: str) -> bool:
    """La compétence est-elle citée dans les expériences (réellement utilisée) ?"""
    name_l = name.lower()
    for e in parsed.get("experiences", []) or []:
        blob = " ".join(str(e.get(k, "")) for k in ("poste", "entreprise")).lower()
        missions = e.get("missions")
        if isinstance(missions, list):
            blob += " " + " ".join(str(m) for m in missions).lower()
        elif missions:
            blob += " " + str(missions).lower()
        if name_l in blob:
            return True
    return False


def derive_declared_level(parsed: dict, competence: str) -> float:
    """Dérive un niveau déclaré 0-10 pour une compétence, depuis le CV.

    Formule transparente (défendable) :
      • compétence absente du CV        → 0 (non déclarée)
      • niveau textuel renseigné        → mapping direct (Débutant..Expert)
      • sinon base 5 (simplement listée)
          + years*0.4 (plafond +3)
          + 2 si utilisée dans une expérience
          + bonus séniorité (Junior 0 · Confirmé +1 · Senior +2)
    """
    comps = parsed.get("competences", []) or []
    match = next((c for c in comps
                  if isinstance(c, dict) and (c.get("name", "").lower() == competence.lower())), None)
    if not match:
        return 0.0

    lvl = (match.get("level") or "").strip().lower()
    if lvl in _LEVEL_MAP:
        return _LEVEL_MAP[lvl]

    base = 5.0
    years = match.get("years")
    if years:
        try:
            base += min(3.0, float(years) * 0.4)
        except (TypeError, ValueError):
            pass
    if _mentioned_in_experience(parsed, competence):
        base += 2.0
    seniorite = (parsed.get("metadata", {}) or {}).get("niveau_seniorite", "").lower()
    base += _SENIORITY_BONUS.get(seniorite, 0.0)
    return round(max(0.0, min(10.0, base)), 1)


def compute_reality_gap(parsed: dict, demonstrated: dict, weights: dict | None = None) -> dict:
    """Calcule le Reality Gap sur les compétences DÉMONTRÉES (testées).

    Args:
        parsed: parsed_data du candidat (CV)
        demonstrated: {competence: niveau_demontre 0-10}
        weights: {competence: poids} (importance dans l'offre) ; défaut 1.0

    Retourne un dict prêt à persister (sans score_final_ajuste).
    """
    weights = weights or {}
    details = []
    gaps_w, poids_tot = 0.0, 0.0

    for comp, dem in demonstrated.items():
        dec = derive_declared_level(parsed, comp)
        gap = abs(dec - dem) / 10.0
        w = float(weights.get(comp, 1.0))
        gaps_w += gap * w
        poids_tot += w
        details.append({
            "competence": comp,
            "niveau_declare": dec,
            "niveau_demontre": round(float(dem), 1),
            "gap": round(gap, 3),
            "poids": w,
        })

    reality_gap_score = round(gaps_w / poids_tot, 3) if poids_tot else 0.0
    fiabilite_cv = round(100.0 - reality_gap_score * 100.0, 1)

    if reality_gap_score < 0.15:
        label = "fiable"
    elif reality_gap_score < 0.30:
        label = "a_verifier"
    else:
        label = "ecart_important"

    return {
        "reality_gap_score": reality_gap_score,
        "fiabilite_cv": fiabilite_cv,
        "niveau_label": label,
        "details": details,
    }


def adjust_matching_score(matching_score: float, fiabilite_cv: float) -> float:
    """score_final_ajuste = matching_score * (0.7 + 0.3 * fiabilite/100)."""
    facteur = 0.7 + 0.3 * (max(0.0, min(100.0, fiabilite_cv)) / 100.0)
    return round(float(matching_score) * facteur, 4)
