from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rapidfuzz import fuzz, process  # type: ignore

from app.models.candidate import Candidate
from app.models.job_offer import JobOffer


def _clip_for_semantic(text: str, max_chars: int = 3000) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars]


def _offer_text_for_semantic(offer: JobOffer) -> str:
    parts = [offer.titre or "", offer.description or ""]
    req = offer.competences_requises or []
    if isinstance(req, list) and req:
        parts.append("Compétences requises: " + ", ".join([str(x) for x in req if x]))
    if offer.localisation:
        parts.append("Localisation: " + offer.localisation)
    return "\n".join(p for p in parts if p)


def _candidate_text_for_semantic(candidate: Candidate) -> str:
    # Priorité: texte brut (OCR/PDF), sinon un résumé via parsed_data
    if candidate.raw_text:
        return candidate.raw_text

    pd = candidate.parsed_data or {}
    if not isinstance(pd, dict):
        return ""

    parts: List[str] = []
    ident = pd.get("identite") or {}
    if isinstance(ident, dict):
        if ident.get("titre"):
            parts.append(str(ident.get("titre")))
        if ident.get("resume"):
            parts.append(str(ident.get("resume")))

    skills = pd.get("competences") or []
    if isinstance(skills, list) and skills:
        skill_names: List[str] = []
        for s in skills:
            if isinstance(s, dict):
                name = s.get("name") or s.get("skill") or s.get("valeur")
            else:
                name = s
            if isinstance(name, str) and name.strip():
                skill_names.append(name.strip())
        if skill_names:
            parts.append("Compétences: " + ", ".join(skill_names[:50]))

    exps = pd.get("experiences") or []
    if isinstance(exps, list) and exps:
        titles: List[str] = []
        for e in exps[:10]:
            if isinstance(e, dict) and e.get("poste"):
                titles.append(str(e.get("poste")))
        if titles:
            parts.append("Expériences: " + ", ".join(titles))

    forms = pd.get("formations") or []
    if isinstance(forms, list) and forms:
        diplomas: List[str] = []
        for f in forms[:5]:
            if isinstance(f, dict) and f.get("diplome"):
                diplomas.append(str(f.get("diplome")))
        if diplomas:
            parts.append("Formations: " + ", ".join(diplomas))

    return "\n".join(p for p in parts if p)


def _candidate_lang(candidate: Candidate) -> str:
    pd = candidate.parsed_data or {}
    if isinstance(pd, dict):
        meta = pd.get("metadata") or {}
        if isinstance(meta, dict):
            v = str(meta.get("langue_cv") or "").strip().lower()
            if v in {"fr", "en"}:
                return v
    return "fr"


@lru_cache(maxsize=2)
def _get_spacy_nlp(lang: str) -> Tuple[Optional[Any], str, bool]:
    """Charge (lazy + cache) un modèle spaCy avec vecteurs si possible.

    Retourne (nlp, model_name, has_vectors).
    Ne doit jamais lever: si indisponible, retourne (None, 'unavailable', False).
    """
    try:
        import spacy  # type: ignore
    except Exception:
        return None, "not_installed", False

    model = "en_core_web_md" if lang == "en" else "fr_core_news_md"
    try:
        nlp = spacy.load(model)
        has_vec = bool(getattr(getattr(nlp, "vocab", None), "vectors", None)) and getattr(nlp.vocab.vectors, "size", 0) > 0
        return nlp, model, bool(has_vec)
    except Exception:
        # Fallback sans vecteurs
        try:
            nlp = spacy.blank("en" if lang == "en" else "fr")
            return nlp, f"blank:{lang}", False
        except Exception:
            return None, "unavailable", False


def _semantic_similarity_score(offer_text: str, cand_text: str, lang: str = "fr") -> Tuple[float, Dict[str, Any]]:
    """Score sémantique (0..1) basé sur embeddings spaCy.

    - Si pas de modèle/vecteurs: retourne un score neutre 0.5.
    - On clamp la similarité et on la mappe vers [0,1].
    """
    offer_text = _clip_for_semantic(offer_text)
    cand_text = _clip_for_semantic(cand_text)

    detail: Dict[str, Any] = {
        "enabled": True,
        "lang": lang,
        "model": None,
        "has_vectors": False,
        "raw_similarity": None,
        "note": None,
    }

    if len(offer_text) < 50 or len(cand_text) < 50:
        detail["note"] = "text_too_short"
        return 0.5, detail

    nlp, model_name, has_vectors = _get_spacy_nlp(lang)
    detail["model"] = model_name
    detail["has_vectors"] = has_vectors
    if nlp is None or not has_vectors:
        detail["note"] = "no_vectors_or_model"
        return 0.5, detail

    try:
        doc_offer = nlp(offer_text)
        doc_cand = nlp(cand_text)
        if not getattr(doc_offer, "vector_norm", 0.0) or not getattr(doc_cand, "vector_norm", 0.0):
            detail["note"] = "empty_vectors"
            return 0.5, detail

        sim = float(doc_offer.similarity(doc_cand))
        # Clamp et mapping [-1, 1] -> [0, 1]
        sim = max(-1.0, min(1.0, sim))
        mapped = (sim + 1.0) / 2.0
        mapped = max(0.0, min(1.0, mapped))
        detail["raw_similarity"] = round(sim, 4)
        return mapped, detail
    except Exception as e:
        detail["note"] = f"error:{type(e).__name__}"
        return 0.5, detail


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _safe_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _extract_required_years(text: str) -> Optional[float]:
    if not text:
        return None

    # Ex: "3 ans", "2-3 years", "2 years" (on prend le premier nombre)
    m = re.search(r"\b(\d+(?:[\.,]\d+)?)\s*(?:\+\s*)?(?:ans|years?)\b", text, re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).replace(",", ".")
    return _safe_float(val)


def _extract_required_education_level(text: str) -> Optional[int]:
    if not text:
        return None

    # Bac+X
    m = re.search(r"\bbac\s*\+\s*(\d)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    low = text.lower()
    # Heuristiques simples (pas de NLP ici)
    if re.search(r"\b(master|m\.?sc\.?|msc|dipl[oô]me\s+d['`’]?ing[ée]nieur|ing[ée]nieur)\b", low, re.IGNORECASE):
        return 5
    if re.search(r"\b(licence|bachelor|b\.?sc\.?|bsc|b\.?eng\.?|but|iut)\b", low, re.IGNORECASE):
        return 3
    if re.search(r"\b(bts|dut|deust)\b", low, re.IGNORECASE):
        return 2

    return None


def _candidate_years(candidate: Candidate) -> float:
    pd = candidate.parsed_data or {}
    meta = (pd.get("metadata") or {}) if isinstance(pd, dict) else {}
    years = _safe_float(meta.get("annees_experience_totales"))
    return max(0.0, years or 0.0)


def _candidate_education_level(candidate: Candidate) -> int:
    pd = candidate.parsed_data or {}
    meta = (pd.get("metadata") or {}) if isinstance(pd, dict) else {}
    try:
        lvl = int(meta.get("niveau_formation_max") or 0)
        return max(0, lvl)
    except Exception:
        return 0


def _candidate_skills(candidate: Candidate) -> List[str]:
    pd = candidate.parsed_data or {}
    if not isinstance(pd, dict):
        return []
    skills = pd.get("competences") or []
    out: List[str] = []
    seen = set()
    if isinstance(skills, list):
        for s in skills:
            if isinstance(s, dict):
                name = s.get("name") or s.get("skill") or s.get("valeur")
            else:
                name = s
            if not isinstance(name, str):
                continue
            n = _norm(name)
            if n and n not in seen:
                seen.add(n)
                out.append(name.strip())
    return out


def _extract_offer_skills(offer: JobOffer) -> List[str]:
    req = offer.competences_requises or []
    if not req:
        return []
    out: List[str] = []
    seen = set()
    for s in req:
        if not isinstance(s, str):
            continue
        n = _norm(s)
        if n and n not in seen:
            seen.add(n)
            out.append(s.strip())
    return out


def _location_score(offer: JobOffer, candidate: Candidate) -> float:
    loc = (offer.localisation or "").strip()
    if not loc:
        return 1.0

    text = candidate.raw_text or ""
    if not text:
        # On n'invente pas une localisation
        return 0.0

    low_text = text.lower()
    # On teste d'abord la localisation complète, puis des tokens ("Tunis, Tunisia" -> "tunis")
    if loc.lower() in low_text:
        return 1.0

    parts = [p.strip() for p in re.split(r"[,/\-|]", loc) if p.strip()]
    for p in parts:
        if len(p) >= 3 and p.lower() in low_text:
            return 1.0

    return 0.0


@dataclass(frozen=True)
class MatchWeights:
    skills: float = 0.45
    experience: float = 0.25
    education: float = 0.20
    location: float = 0.10
    semantic: float = 0.12


class MatchEngine:
    """Matching engine déterministe basé sur similarité + heuristiques.

    - Skills: fuzzy matching (RapidFuzz) entre compétences requises et compétences du candidat
    - Experience: ratio années_candidat / années_requises (si détectées dans le texte)
    - Education: comparaison niveau Bac+X (si détecté)
    - Location: présence de la localisation de l'offre dans le texte du candidat

    Sortie: score 0..1 + breakdown JSON-serializable.
    """

    def __init__(
        self,
        weights: MatchWeights | None = None,
        *,
        enable_semantic: bool = True,
        semantic_lang: Optional[str] = None,
    ):
        self._w = weights or MatchWeights()
        self._enable_semantic = enable_semantic
        self._semantic_lang = semantic_lang

    def score(self, offer: JobOffer, candidate: Candidate) -> Tuple[float, Dict[str, Any]]:
        required_skills = _extract_offer_skills(offer)
        candidate_skills = _candidate_skills(candidate)

        # ── Skills (0..1)
        skills_detail: Dict[str, Any] = {
            "required": required_skills,
            "matched": [],
        }

        if required_skills:
            # matching best effort par compétence requise
            cand_norm = {_norm(s): s for s in candidate_skills}
            cand_norm_keys = list(cand_norm.keys())

            per_req: List[float] = []
            for req in required_skills:
                req_n = _norm(req)
                best = None
                if cand_norm_keys:
                    best = process.extractOne(req_n, cand_norm_keys, scorer=fuzz.token_set_ratio)

                if best:
                    best_key, best_score, _ = best
                    skills_detail["matched"].append(
                        {
                            "required": req,
                            "candidate": cand_norm.get(best_key),
                            "ratio": round(best_score / 100.0, 3),
                        }
                    )
                    per_req.append(best_score / 100.0)
                else:
                    skills_detail["matched"].append(
                        {"required": req, "candidate": None, "ratio": 0.0}
                    )
                    per_req.append(0.0)

            skills_score = sum(per_req) / max(1, len(per_req))
        else:
            # pas de compétences requises structurées -> score neutre
            skills_score = 0.5

        # ── Experience (0..1)
        required_years = _extract_required_years((offer.description or "") + "\n" + (offer.titre or ""))
        cand_years = _candidate_years(candidate)
        if required_years and required_years > 0:
            exp_score = min(1.0, cand_years / required_years)
        else:
            exp_score = 0.5

        # ── Education (0..1)
        req_edu = _extract_required_education_level((offer.description or "") + "\n" + (offer.titre or ""))
        cand_edu = _candidate_education_level(candidate)
        if req_edu and req_edu > 0:
            edu_score = min(1.0, cand_edu / req_edu) if cand_edu > 0 else 0.0
        else:
            edu_score = 0.5

        # ── Location (0..1)
        loc_score = _location_score(offer, candidate)

        # ── Semantic (IA) (0..1)
        semantic_detail: Dict[str, Any] = {"enabled": False}
        if self._enable_semantic:
            if self._semantic_lang is not None:
                lang = (self._semantic_lang or "fr").strip().lower()
                if lang not in {"fr", "en"}:
                    lang = "fr"
            else:
                lang = _candidate_lang(candidate)
            semantic_offer = _offer_text_for_semantic(offer)
            semantic_cand = _candidate_text_for_semantic(candidate)
            semantic_score, semantic_detail = _semantic_similarity_score(
                offer_text=semantic_offer,
                cand_text=semantic_cand,
                lang=lang,
            )
        else:
            semantic_score = 0.5

        # ── Weighted total
        weights_raw = {
            "skills": float(self._w.skills),
            "experience": float(self._w.experience),
            "education": float(self._w.education),
            "location": float(self._w.location),
            "semantic": float(self._w.semantic) if self._enable_semantic else 0.0,
        }
        sum_w = sum(weights_raw.values())
        if sum_w <= 0:
            weights_norm = {k: 0.0 for k in weights_raw}
            weights_norm["skills"] = 1.0
            sum_w = 1.0
        else:
            weights_norm = {k: (v / sum_w) for k, v in weights_raw.items()}

        total = (
            weights_norm["skills"] * skills_score
            + weights_norm["experience"] * exp_score
            + weights_norm["education"] * edu_score
            + weights_norm["location"] * loc_score
            + weights_norm["semantic"] * semantic_score
        )
        total = max(0.0, min(1.0, float(total)))

        details = {
            "weights_raw": {k: round(v, 6) for k, v in weights_raw.items()},
            "weights": {k: round(v, 6) for k, v in weights_norm.items()},
            "components": {
                "skills": {"score": round(skills_score, 4), **skills_detail},
                "experience": {
                    "score": round(exp_score, 4),
                    "candidate_years": cand_years,
                    "required_years": required_years,
                },
                "education": {
                    "score": round(edu_score, 4),
                    "candidate_level": cand_edu,
                    "required_level": req_edu,
                },
                "location": {
                    "score": round(loc_score, 4),
                    "offer_location": offer.localisation,
                },
                "semantic": {
                    "score": round(semantic_score, 4),
                    **(semantic_detail or {}),
                },
            },
            "total": round(total, 4),
        }

        return total, details

    @staticmethod
    def details_to_text(details: Dict[str, Any]) -> str:
        return json.dumps(details, ensure_ascii=False)
