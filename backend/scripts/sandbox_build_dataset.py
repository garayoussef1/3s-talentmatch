from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

# Rendre le package app importable quand le script est execute depuis backend/scripts
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.match import Match, MatchStatus  # noqa: E402


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _parse_details(details_text: Optional[str]) -> Dict[str, Any]:
    if not details_text:
        return {}
    try:
        data = json.loads(details_text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _extract_component_score(details: Dict[str, Any], key: str) -> float:
    components = details.get("components") if isinstance(details, dict) else None
    if not isinstance(components, dict):
        return 0.0
    block = components.get(key)
    if not isinstance(block, dict):
        return 0.0
    return _safe_float(block.get("score"), 0.0)


def _extract_feature_row(match: Match, label: int) -> Dict[str, Any]:
    candidate = match.candidate
    offer = match.job_offer
    details = _parse_details(match.details)

    parsed_data = candidate.parsed_data if candidate and isinstance(candidate.parsed_data, dict) else {}
    metadata = parsed_data.get("metadata") if isinstance(parsed_data, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}

    competences = parsed_data.get("competences") if isinstance(parsed_data, dict) else []
    if not isinstance(competences, list):
        competences = []

    required_skills = offer.competences_requises if offer else []
    if not isinstance(required_skills, list):
        required_skills = []

    offer_title = (offer.titre if offer and offer.titre else "").strip()
    offer_desc = (offer.description if offer and offer.description else "").strip()
    offer_loc = (offer.localisation if offer and offer.localisation else "").strip()

    raw_text = (candidate.raw_text if candidate and candidate.raw_text else "").strip()

    return {
        "match_id": str(match.id),
        "job_offer_id": str(match.job_offer_id),
        "candidate_id": str(match.candidate_id),
        "created_at": match.created_at.isoformat() if match.created_at else "",
        "label": label,
        "label_source": "human_status",
        "match_status": match.status.value if match.status else "",
        "current_score": _safe_float(match.score),
        "score_skills": _extract_component_score(details, "skills"),
        "score_experience": _extract_component_score(details, "experience"),
        "score_education": _extract_component_score(details, "education"),
        "score_location": _extract_component_score(details, "location"),
        "score_semantic": _extract_component_score(details, "semantic"),
        "candidate_years": _safe_float(metadata.get("annees_experience_totales"), 0.0),
        "candidate_education_level": _safe_int(metadata.get("niveau_formation_max"), 0),
        "candidate_total_skills": len(competences),
        "required_skills_count": len(required_skills),
        "langue_cv": str(metadata.get("langue_cv") or "").strip().lower(),
        "offer_title_len": len(offer_title),
        "offer_desc_len": len(offer_desc),
        "candidate_text_len": len(raw_text),
        "offer_title": offer_title,
        "offer_description": offer_desc,
        "offer_location": offer_loc,
        "candidate_cv_id": candidate.cv_id if candidate else "",
    }


def _make_synthetic_negative(base_row: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Construit un negatif synthetique a partir d'un exemple positif.

    Utilise uniquement en sandbox pour debloquer un POC quand il manque
    de vrais labels rejected en base.
    """
    r = dict(base_row)
    r["match_id"] = f"synthetic-neg-{idx}-{base_row.get('match_id', 'x')}"
    r["label"] = 0
    r["label_source"] = "synthetic_bootstrap"
    r["match_status"] = "synthetic_rejected"

    # Ecraser les composantes principales vers des valeurs faibles plausibles.
    r["score_skills"] = round(random.uniform(0.0, 0.22), 4)
    r["score_experience"] = round(random.uniform(0.0, 0.35), 4)
    r["score_education"] = round(random.uniform(0.0, 0.45), 4)
    r["score_location"] = round(random.uniform(0.0, 0.35), 4)
    r["score_semantic"] = round(random.uniform(0.18, 0.48), 4)

    # Ajustements de features globales pour separer les classes.
    req_sk = _safe_int(r.get("required_skills_count"), 0)
    cand_sk = _safe_int(r.get("candidate_total_skills"), 0)
    r["candidate_total_skills"] = max(0, min(cand_sk, max(0, req_sk - random.randint(1, 3))))

    cand_years = _safe_float(r.get("candidate_years"), 0.0)
    r["candidate_years"] = round(max(0.0, cand_years - random.uniform(1.0, 3.0)), 2)

    cand_lvl = _safe_int(r.get("candidate_education_level"), 0)
    r["candidate_education_level"] = max(0, cand_lvl - random.randint(0, 2))

    r["current_score"] = round(
        0.45 * _safe_float(r["score_skills"])
        + 0.25 * _safe_float(r["score_experience"])
        + 0.20 * _safe_float(r["score_education"])
        + 0.10 * _safe_float(r["score_location"]),
        4,
    )
    return r


def _iter_labeled_matches() -> Iterable[Dict[str, Any]]:
    db = SessionLocal()
    try:
        matches = db.query(Match).all()
        for match in matches:
            if match.status == MatchStatus.accepted:
                label = 1
            elif match.status == MatchStatus.rejected:
                label = 0
            else:
                # pending/reviewed exclus pour MVP
                continue
            yield _extract_feature_row(match, label)
    finally:
        db.close()


def _default_output_path() -> Path:
    return (
        BACKEND_ROOT
        / "app"
        / "services"
        / "matching_sandbox"
        / "datasets"
        / "matching_dataset_v1.csv"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Construit un dataset sandbox IA matching depuis la base de donnees."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(_default_output_path()),
        help="Chemin de sortie CSV",
    )
    parser.add_argument(
        "--min-negatives",
        type=int,
        default=5,
        help="Nombre minimal de labels 0 vises (synthetiques si necessaire)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Graine aleatoire pour reproductibilite des negatifs synthetiques",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = list(_iter_labeled_matches())
    if not rows:
        print("[sandbox] Aucun exemple labelise (accepted/rejected) trouve.")
        print("[sandbox] Rien a exporter.")
        return 0

    random.seed(args.seed)

    positives = [r for r in rows if r.get("label") == 1]
    negatives = [r for r in rows if r.get("label") == 0]

    # Bootstrap si la base ne contient pas assez de vrais rejected.
    if len(negatives) < max(0, args.min_negatives) and positives:
        missing = max(0, args.min_negatives) - len(negatives)
        synth: list[Dict[str, Any]] = []
        for i in range(missing):
            base = positives[i % len(positives)]
            synth.append(_make_synthetic_negative(base, i + 1))
        rows.extend(synth)

    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    positives_count = sum(1 for r in rows if r.get("label") == 1)
    negatives_count = sum(1 for r in rows if r.get("label") == 0)
    synthetic_count = sum(1 for r in rows if r.get("label_source") == "synthetic_bootstrap")

    print(f"[sandbox] Dataset exporte: {output_path}")
    print(
        f"[sandbox] Lignes: {total} | accepted=1: {positives_count} | rejected=0: {negatives_count}"
        f" | synthetic_rejected: {synthetic_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
