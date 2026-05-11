from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ml_scorer import SandboxMLScorer

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent / "models" / "decision_logreg.joblib"
)

DEFAULT_FEATURES = [
    "bert_raw",
    "bert_semantic",
    "bert_skills",
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class DecisionScorer:
    """Decision scorer that learns a final percentage from multiple signals."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self._model = None
        self._features: List[str] = list(DEFAULT_FEATURES)
        self._ready = False
        self._load_error: Optional[str] = None
        self._load()

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _load(self) -> None:
        if not self.model_path.exists():
            self._ready = False
            self._load_error = f"model_not_found:{self.model_path}"
            return
        try:
            import joblib  # type: ignore

            artifact = joblib.load(self.model_path)
            self._model = artifact.get("model") if isinstance(artifact, dict) else artifact
            if isinstance(artifact, dict):
                features = artifact.get("features")
                if isinstance(features, list) and features:
                    self._features = [str(f) for f in features]
            self._ready = self._model is not None
            if not self._ready:
                self._load_error = "invalid_artifact"
        except Exception as e:
            self._ready = False
            self._load_error = f"load_error:{type(e).__name__}"

    @staticmethod
    def build_feature_dict(
        *,
        heuristic_details: Dict[str, Any],
        bert_details: Dict[str, Any],
        candidate: Any,
        offer: Any,
    ) -> Dict[str, float]:
        base_features = SandboxMLScorer.build_feature_dict(
            details=heuristic_details,
            candidate=candidate,
            offer=offer,
        )

        bert_sem = _safe_float(bert_details.get("bert_semantic"), 0.0)
        bert_skills = _safe_float(bert_details.get("bert_skills"), 0.0)
        bert_raw = _safe_float(bert_details.get("total_raw"), _safe_float(bert_details.get("total"), 0.0))

        return {
            **base_features,
            "bert_raw": bert_raw,
            "bert_semantic": bert_sem,
            "bert_skills": bert_skills,
        }

    def predict(self, feature_dict: Dict[str, float]) -> Tuple[float, Dict[str, Any]]:
        if not self._ready or self._model is None:
            return 0.5, {
                "ready": False,
                "reason": self._load_error or "model_unavailable",
                "model_path": str(self.model_path),
            }

        try:
            x = [[_safe_float(feature_dict.get(name), 0.0) for name in self._features]]
            score = float(self._model.predict_proba(x)[0][1])
            score = max(0.0, min(1.0, score))
            return score, {
                "ready": True,
                "model_path": str(self.model_path),
                "features_used": list(self._features),
            }
        except Exception as e:
            return 0.5, {
                "ready": False,
                "reason": f"predict_error:{type(e).__name__}",
                "model_path": str(self.model_path),
            }
