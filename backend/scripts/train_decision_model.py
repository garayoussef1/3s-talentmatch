from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.models.match import Match
from app.services.matching.match_engine import MatchEngine
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.services.matching_sandbox.decision_scorer import DEFAULT_MODEL_PATH, DEFAULT_FEATURES
from app.services.matching_sandbox.decision_scorer import DecisionScorer

ANNOTATIONS_PATH = Path(__file__).resolve().parents[2] / "data" / "annotations.json"


def _load_annotations() -> Dict[str, Any]:
    if not ANNOTATIONS_PATH.exists():
        return {}
    with ANNOTATIONS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _iter_annotated_pairs(data: Dict[str, Any]) -> List[Tuple[str, str, int]]:
    pairs: List[Tuple[str, str, int]] = []
    for offer_id, payload in (data or {}).items():
        for item in payload.get("candidates", []):
            rel = int(item.get("relevance", -1))
            if rel < 0:
                continue
            pairs.append((offer_id, str(item.get("candidate_id")), rel))
    return pairs


def _label_from_relevance(rel: int) -> int:
    return 1 if rel >= 1 else 0


def build_dataset(db: Session) -> Tuple[List[List[float]], List[int]]:
    annotations = _load_annotations()
    pairs = _iter_annotated_pairs(annotations)
    if not pairs:
        pairs = []

    engine = MatchEngine()
    bert = BERTMatchingScorer()

    x: List[List[float]] = []
    y: List[int] = []

    for offer_id, candidate_id, rel in pairs:
        offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not offer or not candidate:
            continue

        h_score, h_details = engine.score(offer, candidate)
        b_score, b_details = bert.score(offer, candidate)

        feature_dict = DecisionScorer.build_feature_dict(
            heuristic_details=h_details,
            bert_details=b_details,
            candidate=candidate,
            offer=offer,
        )

        x.append([float(feature_dict.get(name, 0.0)) for name in DEFAULT_FEATURES])
        y.append(_label_from_relevance(rel))

    # Fallback: generate pseudo-labels if annotated set is too small
    if len(x) < 10:
        matches = (
            db.query(Match)
            .join(Candidate, Match.candidate_id == Candidate.id)
            .join(JobOffer, Match.job_offer_id == JobOffer.id)
            .all()
        )

        def add_sample(label: int, h_details: Dict[str, Any], b_details: Dict[str, Any], candidate: Candidate, offer: JobOffer) -> None:
            feature_dict = DecisionScorer.build_feature_dict(
                heuristic_details=h_details,
                bert_details=b_details,
                candidate=candidate,
                offer=offer,
            )
            x.append([float(feature_dict.get(name, 0.0)) for name in DEFAULT_FEATURES])
            y.append(label)

        def pass_thresholds(pos_b: float, pos_h: float, neg_b: float, neg_h: float) -> Tuple[int, int]:
            pos_count = 0
            neg_count = 0
            for m in matches:
                offer = m.job_offer
                candidate = m.candidate
                if not offer or not candidate:
                    continue

                h_score, h_details = engine.score(offer, candidate)
                b_score, b_details = bert.score(offer, candidate)

                if b_score >= pos_b and h_score >= pos_h:
                    add_sample(1, h_details, b_details, candidate, offer)
                    pos_count += 1
                elif b_score <= neg_b and h_score <= neg_h:
                    add_sample(0, h_details, b_details, candidate, offer)
                    neg_count += 1
            return pos_count, neg_count

        # Pass 1: strict
        pos_count, neg_count = pass_thresholds(0.70, 0.60, 0.30, 0.40)

        # Pass 2: relaxed if still too small
        if len(x) < 10:
            p2, n2 = pass_thresholds(0.65, 0.55, 0.35, 0.45)
            pos_count += p2
            neg_count += n2

        # Pass 3: very confident single-model if still too small
        if len(x) < 6:
            for m in matches:
                offer = m.job_offer
                candidate = m.candidate
                if not offer or not candidate:
                    continue

                h_score, h_details = engine.score(offer, candidate)
                b_score, b_details = bert.score(offer, candidate)

                if b_score >= 0.78 or h_score >= 0.85:
                    add_sample(1, h_details, b_details, candidate, offer)
                    pos_count += 1
                elif b_score <= 0.22 or h_score <= 0.25:
                    add_sample(0, h_details, b_details, candidate, offer)
                    neg_count += 1

        # Rank-based fallback to ensure both classes
        if len(set(y)) < 2 and matches:
            by_offer: Dict[str, List[Tuple[float, Match]]] = {}
            for m in matches:
                offer = m.job_offer
                candidate = m.candidate
                if not offer or not candidate:
                    continue
                h_score, h_details = engine.score(offer, candidate)
                b_score, b_details = bert.score(offer, candidate)
                hybrid = (0.6 * b_score) + (0.4 * h_score)
                by_offer.setdefault(str(offer.id), []).append((hybrid, m))

            for items in by_offer.values():
                items.sort(key=lambda t: t[0], reverse=True)
                top = items[:2]
                bottom = items[-2:] if len(items) >= 2 else []

                for score, m in top:
                    offer = m.job_offer
                    candidate = m.candidate
                    if not offer or not candidate:
                        continue
                    h_score, h_details = engine.score(offer, candidate)
                    b_score, b_details = bert.score(offer, candidate)
                    add_sample(1, h_details, b_details, candidate, offer)
                    pos_count += 1

                for score, m in bottom:
                    offer = m.job_offer
                    candidate = m.candidate
                    if not offer or not candidate:
                        continue
                    h_score, h_details = engine.score(offer, candidate)
                    b_score, b_details = bert.score(offer, candidate)
                    add_sample(0, h_details, b_details, candidate, offer)
                    neg_count += 1

        if not x:
            raise RuntimeError("No annotations and no pseudo-labels were found.")
        print(f"Pseudo-labels added: pos={pos_count} neg={neg_count}")

    return x, y


def main() -> int:
    try:
        from sklearn.linear_model import LogisticRegression  # type: ignore
        from sklearn.metrics import roc_auc_score, average_precision_score  # type: ignore
        import joblib  # type: ignore
    except Exception:
        print("Install scikit-learn and joblib: pip install scikit-learn joblib")
        return 1

    db = SessionLocal()
    try:
        x, y = build_dataset(db)
    finally:
        db.close()

    # Minimum size and class balance checks
    if len(x) < 4 or len(set(y)) < 2:
        print("Not enough samples with both classes (need >=4 and 2 classes).")
        return 1
    if len(x) < 10:
        print("Warning: small dataset, model may overfit.")

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(x, y)

    probs = model.predict_proba(x)[:, 1]
    auc = float(roc_auc_score(y, probs)) if len(set(y)) > 1 else 0.5
    ap = float(average_precision_score(y, probs)) if len(set(y)) > 1 else 0.0

    DEFAULT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": DEFAULT_FEATURES, "metrics": {"auc": auc, "ap": ap}}, DEFAULT_MODEL_PATH)

    print(f"Decision model saved: {DEFAULT_MODEL_PATH}")
    print(f"AUC={auc:.4f}  AP={ap:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
