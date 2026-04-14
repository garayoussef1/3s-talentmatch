from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

NUMERIC_FEATURES = [
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


def _build_xy(rows: List[Dict[str, str]]) -> Tuple[List[List[float]], List[int]]:
    x: List[List[float]] = []
    y: List[int] = []
    for row in rows:
        label_raw = row.get("label", "")
        if label_raw not in {"0", "1"}:
            continue
        y.append(int(label_raw))
        x.append([_safe_float(row.get(col, "0")) for col in NUMERIC_FEATURES])
    return x, y


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
    parser = argparse.ArgumentParser(description="Entraine un modele sandbox (Logistic Regression).")
    parser.add_argument("--dataset", type=str, default=str(_default_dataset_path()))
    parser.add_argument("--model-out", type=str, default=str(_default_model_path()))
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    model_out = Path(args.model_out).resolve()

    if not dataset_path.exists():
        print(f"[sandbox-train] Dataset introuvable: {dataset_path}")
        return 1

    rows = _load_rows(dataset_path)
    x, y = _build_xy(rows)
    if len(x) < 2:
        print("[sandbox-train] Pas assez de donnees pour entrainer (min=2).")
        return 1

    classes = set(y)
    if len(classes) < 2:
        print("[sandbox-train] Une seule classe detectee. Ajoute des labels accepted ET rejected.")
        return 1

    try:
        from sklearn.linear_model import LogisticRegression  # type: ignore
        from sklearn.metrics import roc_auc_score, average_precision_score  # type: ignore
        from sklearn.model_selection import train_test_split  # type: ignore
        import joblib  # type: ignore
    except Exception:
        print("[sandbox-train] Dependance manquante: scikit-learn/joblib.")
        print("[sandbox-train] Installe avec: pip install scikit-learn joblib")
        return 1

    class_counts = Counter(y)
    min_class = min(class_counts.values()) if class_counts else 0

    # Petit dataset: fallback robuste pour ne pas bloquer la demo sandbox.
    if len(x) < 8 or min_class < 2:
        x_train, y_train = x, y
        x_val, y_val = x, y
        split_mode = "train_equals_val_small_dataset"
    else:
        x_train, x_val, y_train, y_val = train_test_split(
            x,
            y,
            test_size=0.25,
            random_state=42,
            stratify=y,
        )
        split_mode = "stratified_holdout"

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(x_train, y_train)

    val_proba = model.predict_proba(x_val)[:, 1]
    try:
        auc = float(roc_auc_score(y_val, val_proba))
    except Exception:
        auc = 0.5
    try:
        ap = float(average_precision_score(y_val, val_proba))
    except Exception:
        ap = 0.0

    metrics = {
        "auc": auc,
        "average_precision": ap,
        "train_size": len(x_train),
        "val_size": len(x_val),
        "split_mode": split_mode,
        "class_counts": dict(class_counts),
        "features": NUMERIC_FEATURES,
    }

    model_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": NUMERIC_FEATURES, "metrics": metrics}, model_out)

    metrics_out = model_out.with_suffix(".metrics.json")
    metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"[sandbox-train] Modele sauvegarde: {model_out}")
    print(f"[sandbox-train] Metriques: {metrics_out}")
    print(f"[sandbox-train] AUC={metrics['auc']:.4f} AP={metrics['average_precision']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
