from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent / "models" / "logreg_v1.joblib"
)

DEFAULT_FEATURES = [
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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


class SandboxMLScorer:
    """Scorer ML sandbox pour prediction locale non-destructive.

    - Ne leve pas d'exception en cas de modele absent.
    - Retourne (score, details) avec fallback neutre si indisponible.
    """

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
        details: Dict[str, Any],
        candidate: Any,
        offer: Any,
    ) -> Dict[str, float]:
        components = details.get("components") if isinstance(details, dict) else {}
        components = components if isinstance(components, dict) else {}

        def comp_score(name: str) -> float:
            block = components.get(name)
            if not isinstance(block, dict):
                return 0.0
            return _safe_float(block.get("score"), 0.0)

        parsed_data = getattr(candidate, "parsed_data", None)
        if not isinstance(parsed_data, dict):
            parsed_data = {}
        metadata = parsed_data.get("metadata") if isinstance(parsed_data, dict) else {}
        metadata = metadata if isinstance(metadata, dict) else {}
        competences = parsed_data.get("competences") if isinstance(parsed_data, dict) else []
        if not isinstance(competences, list):
            competences = []

        required = getattr(offer, "competences_requises", None)
        if not isinstance(required, list):
            required = []

        offer_title = str(getattr(offer, "titre", "") or "")
        offer_desc = str(getattr(offer, "description", "") or "")
        candidate_text = str(getattr(candidate, "raw_text", "") or "")

        return {
            "score_skills": comp_score("skills"),
            "score_experience": comp_score("experience"),
            "score_education": comp_score("education"),
            "score_location": comp_score("location"),
            "score_semantic": comp_score("semantic"),
            "candidate_years": _safe_float(metadata.get("annees_experience_totales"), 0.0),
            "candidate_education_level": float(_safe_int(metadata.get("niveau_formation_max"), 0)),
            "candidate_total_skills": float(len(competences)),
            "required_skills_count": float(len(required)),
            "offer_title_len": float(len(offer_title)),
            "offer_desc_len": float(len(offer_desc)),
            "candidate_text_len": float(len(candidate_text)),
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
