from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

NUMERIC_FEATURES_FALLBACK = [
    "score_skills",
    "score_experience",
    "score_education",
    "score_location",
    "score_semantic",
    "candidate_years",
    "candidate_education_level",
    "candidate_total_skills",
    "required_skills_count",
    "offer_title_len",
    "offer_desc_len",
    "candidate_text_len",
]


def _safe_float(v: str) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _load_rows(dataset_path: Path) -> List[Dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def _precision_at_k(rows: List[Tuple[float, int]], k: int) -> float:
    if not rows:
        return 0.0
    top = sorted(rows, key=lambda r: r[0], reverse=True)[:k]
    if not top:
        return 0.0
    return sum(lbl for _, lbl in top) / len(top)


def _dcg(labels: List[int]) -> float:
    score = 0.0
    for i, rel in enumerate(labels, start=1):
        score += (2 ** rel - 1) / (1 if i == 1 else __import__("math").log2(i))
    return score


def _ndcg_at_k(rows: List[Tuple[float, int]], k: int) -> float:
    if not rows:
        return 0.0
    ranked = sorted(rows, key=lambda r: r[0], reverse=True)[:k]
    ideal = sorted(rows, key=lambda r: r[1], reverse=True)[:k]
    dcg = _dcg([lbl for _, lbl in ranked])
    idcg = _dcg([lbl for _, lbl in ideal])
    return dcg / idcg if idcg > 0 else 0.0


def _default_dataset_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "matching_sandbox"
        / "datasets"
        / "matching_dataset_v1.csv"
    )


def _default_model_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "matching_sandbox"
        / "models"
        / "logreg_v1.joblib"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalue un modele sandbox sur un dataset CSV.")
    parser.add_argument("--dataset", type=str, default=str(_default_dataset_path()))
    parser.add_argument("--model", type=str, default=str(_default_model_path()))
    parser.add_argument("--report-out", type=str, default="")
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    model_path = Path(args.model).resolve()

    if not dataset_path.exists() or not model_path.exists():
        print("[sandbox-eval] Dataset ou modele introuvable.")
        return 1

    try:
        import joblib  # type: ignore
    except Exception:
        print("[sandbox-eval] Dependance manquante: joblib")
        return 1

    artifact = joblib.load(model_path)
    model = artifact.get("model")
    features = artifact.get("features") or NUMERIC_FEATURES_FALLBACK

    rows = _load_rows(dataset_path)
    scored: List[Tuple[float, int]] = []

    for row in rows:
        label_raw = row.get("label", "")
        if label_raw not in {"0", "1"}:
            continue
        label = int(label_raw)
        x = [[_safe_float(row.get(col, "0")) for col in features]]
        proba = float(model.predict_proba(x)[0][1])
        scored.append((proba, label))

    if not scored:
        print("[sandbox-eval] Aucun exemple valide pour evaluation.")
        return 1

    report = {
        "samples": len(scored),
        "precision_at_5": _precision_at_k(scored, 5),
        "ndcg_at_10": _ndcg_at_k(scored, 10),
    }

    report_out = Path(args.report_out).resolve() if args.report_out else model_path.with_suffix(".eval.json")
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[sandbox-eval] Report: {report_out}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
