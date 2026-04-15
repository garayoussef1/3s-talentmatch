from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.services.matching.match_engine import (
    _candidate_education_level,
    _candidate_skills,
    _candidate_text_for_semantic,
    _candidate_years,
    _extract_offer_skills,
    _extract_required_education_level,
    _extract_required_years,
    _offer_text_for_semantic,
)


def _clip_words(text: str, max_tokens: int = 512) -> str:
    words = (text or "").split()
    if len(words) <= max_tokens:
        return " ".join(words)
    return " ".join(words[:max_tokens])


def _safe_list_of_strings(values: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(values, list):
        return out
    for v in values:
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
        elif isinstance(v, dict):
            name = v.get("name") or v.get("skill") or v.get("valeur")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
    return out


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = float(np.linalg.norm(a))
    b_norm = float(np.linalg.norm(b))
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


class BERTMatchingScorer:
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self._model = None
        self._load_attempted = False
        self.ready = False
        self.load_error: Optional[str] = None

    def _get_model(self):
        if self._model is not None:
            return self._model
        if self._load_attempted:
            return None

        self._load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception:
            self.ready = False
            self.load_error = "sentence_transformers_not_installed"
            return None

        try:
            self._model = SentenceTransformer(self.model_name)
            self.ready = True
            self.load_error = None
            return self._model
        except Exception as e:
            self.ready = False
            self.load_error = f"model_load_error:{type(e).__name__}"
            return None

    def score_semantic(self, offer_text: str, cv_text: str) -> Tuple[float, Dict[str, Any]]:
        model = self._get_model()
        if model is None:
            return 0.5, {
                "ready": False,
                "reason": self.load_error or "model_unavailable",
                "model": self.model_name,
            }

        try:
            offer_clip = _clip_words(offer_text, 512)
            cv_clip = _clip_words(cv_text, 512)
            emb = model.encode([offer_clip, cv_clip], convert_to_numpy=True)
            sim = _cosine(np.asarray(emb[0], dtype=float), np.asarray(emb[1], dtype=float))
            sim = max(-1.0, min(1.0, sim))
            mapped = (sim + 1.0) / 2.0
            mapped = max(0.0, min(1.0, mapped))
            return float(mapped), {
                "ready": True,
                "model": self.model_name,
                "raw_similarity": round(float(sim), 4),
            }
        except Exception as e:
            return 0.5, {
                "ready": False,
                "reason": f"semantic_error:{type(e).__name__}",
                "model": self.model_name,
            }

    def score_skills_bert(
        self,
        offer_skills: List[str],
        cv_skills: List[str],
    ) -> Tuple[float, Dict[str, Any]]:
        if not offer_skills or not cv_skills:
            return 0.5, {"note": "no_skills", "ready": self.ready, "model": self.model_name}

        model = self._get_model()
        if model is None:
            return 0.5, {
                "ready": False,
                "reason": self.load_error or "model_unavailable",
                "model": self.model_name,
            }

        try:
            offer_emb = model.encode(offer_skills, convert_to_numpy=True)
            cv_emb = model.encode(cv_skills, convert_to_numpy=True)

            max_scores: List[float] = []
            for i in range(len(offer_skills)):
                sims = []
                for j in range(len(cv_skills)):
                    sims.append(
                        _cosine(
                            np.asarray(offer_emb[i], dtype=float),
                            np.asarray(cv_emb[j], dtype=float),
                        )
                    )
                best = max(sims) if sims else 0.0
                best = max(-1.0, min(1.0, float(best)))
                max_scores.append((best + 1.0) / 2.0)

            score = float(np.mean(max_scores)) if max_scores else 0.5
            score = max(0.0, min(1.0, score))
            return score, {
                "ready": True,
                "model": self.model_name,
                "offer_skills_count": len(offer_skills),
                "cv_skills_count": len(cv_skills),
            }
        except Exception as e:
            return 0.5, {
                "ready": False,
                "reason": f"skills_error:{type(e).__name__}",
                "model": self.model_name,
            }

    def detect_skill_inconsistencies(
        self,
        cv_skills: List[str],
        cv_experiences: Any,
        cv_raw_text: str,
    ) -> List[Dict[str, Any]]:
        ecosystems = {
            "react": "javascript",
            "angular": "typescript",
            "spring": "java",
            "django": "python",
            "laravel": "php",
        }

        raw_low = (cv_raw_text or "").lower()
        experiences_texts: List[str] = []
        if isinstance(cv_experiences, list):
            for exp in cv_experiences:
                if not isinstance(exp, dict):
                    continue
                parts: List[str] = []
                for key in ("poste", "title", "entreprise", "company", "description"):
                    val = exp.get(key)
                    if isinstance(val, str) and val.strip():
                        parts.append(val.strip())
                missions = exp.get("missions")
                if isinstance(missions, list):
                    for m in missions:
                        if isinstance(m, str) and m.strip():
                            parts.append(m.strip())
                if parts:
                    experiences_texts.append(" ".join(parts))

        exp_low_joined = "\n".join(experiences_texts).lower()

        by_skill: Dict[str, Dict[str, Any]] = {}

        def keep_most_severe(item: Dict[str, Any]) -> None:
            skill = str(item.get("skill") or "").strip()
            if not skill:
                return
            prev = by_skill.get(skill)
            if prev is None or int(item.get("level", 0)) > int(prev.get("level", 0)):
                by_skill[skill] = item

        for skill in cv_skills:
            s = (skill or "").strip()
            if not s:
                continue
            s_low = s.lower()

            if s_low not in raw_low:
                keep_most_severe({"skill": s, "level": 1, "reason": "absent_from_text"})

            if experiences_texts and s_low not in exp_low_joined:
                keep_most_severe(
                    {"skill": s, "level": 2, "reason": "absent_from_experiences"}
                )

            if s_low in ecosystems:
                need = ecosystems[s_low]
                if need not in raw_low:
                    keep_most_severe(
                        {
                            "skill": s,
                            "level": 3,
                            "reason": f"missing_ecosystem:{need}",
                        }
                    )

            model = self._get_model()
            if model is not None and experiences_texts:
                try:
                    exp_context = " ".join(experiences_texts)
                    emb = model.encode([s, _clip_words(exp_context, 512)], convert_to_numpy=True)
                    sim = _cosine(np.asarray(emb[0], dtype=float), np.asarray(emb[1], dtype=float))
                    if float(sim) < 0.25:
                        keep_most_severe(
                            {
                                "skill": s,
                                "level": 4,
                                "reason": "low_context_similarity",
                            }
                        )
                except Exception:
                    pass

        out = list(by_skill.values())
        out.sort(key=lambda x: int(x.get("level", 0)), reverse=True)
        return out

    def score(self, offer: JobOffer, candidate: Candidate) -> Tuple[float, Dict[str, Any]]:
        offer_text = _offer_text_for_semantic(offer)
        cv_text = _candidate_text_for_semantic(candidate)
        offer_skills = _extract_offer_skills(offer)
        cv_skills = _candidate_skills(candidate)

        semantic_score, semantic_info = self.score_semantic(offer_text, cv_text)
        skills_score, skills_info = self.score_skills_bert(offer_skills, cv_skills)

        desc_blob = ((offer.description or "") + "\n" + (offer.titre or "")).strip()
        required_years = _extract_required_years(desc_blob)
        req_edu = _extract_required_education_level(desc_blob)
        cand_years = _candidate_years(candidate)
        cand_edu = _candidate_education_level(candidate)

        if required_years and required_years > 0:
            exp_score = min(1.0, cand_years / required_years)
        else:
            exp_score = 0.5

        if req_edu and req_edu > 0:
            edu_score = min(1.0, cand_edu / req_edu)
        else:
            edu_score = 0.5

        base = (float(exp_score) + float(edu_score)) / 2.0

        parsed = candidate.parsed_data if isinstance(candidate.parsed_data, dict) else {}
        experiences = parsed.get("experiences") if isinstance(parsed, dict) else []
        inconsistencies = self.detect_skill_inconsistencies(
            cv_skills=cv_skills,
            cv_experiences=experiences,
            cv_raw_text=(candidate.raw_text or ""),
        )
        penalty = min(0.15, len(inconsistencies) * 0.05)

        total = (0.5 * float(semantic_score)) + (0.3 * float(skills_score)) + (0.2 * float(base)) - float(
            penalty
        )
        total = max(0.0, min(1.0, float(total)))

        details = {
            "bert_semantic": round(float(semantic_score), 4),
            "bert_skills": round(float(skills_score), 4),
            "base": round(float(base), 4),
            "penalty": round(float(penalty), 4),
            "inconsistencies": inconsistencies,
            "total": round(float(total), 4),
            "model": self.model_name,
            "ready": bool(self.ready),
            "semantic": semantic_info,
            "skills": skills_info,
            "experience": {
                "score": round(float(exp_score), 4),
                "candidate_years": cand_years,
                "required_years": required_years,
            },
            "education": {
                "score": round(float(edu_score), 4),
                "candidate_level": cand_edu,
                "required_level": req_edu,
            },
        }

        return total, details