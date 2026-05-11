from __future__ import annotations

import os

# Forcer le mode offline — modèle chargé depuis le cache local uniquement
os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",   "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rapidfuzz import fuzz  # type: ignore

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
    _normalize_skill,
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


_MODELS_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "data", "models"
)
_TALENTMATCH_PATHS = [
    os.path.join(_MODELS_ROOT, "talentmatch-bert"),       # prod (v1.3 en priorité)
    os.path.join(_MODELS_ROOT, "talentmatch-bert-v1.2"),  # fallback
]
_BASE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class BERTMatchingScorer:
    def __init__(self, model_name: str = _BASE_MODEL):
        # Utiliser TalentMatch-BERT le plus récent si disponible, sinon modèle de base
        selected_path = None
        for candidate_path in _TALENTMATCH_PATHS:
            talentmatch_config = os.path.join(candidate_path, "config.json")
            if os.path.exists(talentmatch_config):
                selected_path = candidate_path
                break

        if selected_path:
            self.model_name    = selected_path
            # Lire la version depuis le rapport d'entraînement si disponible
            _version = "v1.0"
            for _report in ["training_report_v1.3.json", "training_report_v1.2.json", "training_report.json"]:
                _report_path = os.path.join(selected_path, _report)
                if os.path.exists(_report_path):
                    try:
                        import json as _json
                        with open(_report_path, encoding="utf-8") as _f:
                            _data = _json.load(_f)
                        _version = _data.get("version", "v1.0").replace("TalentMatch-BERT ", "")
                    except Exception:
                        pass
                    break
            self.model_version = f"TalentMatch-BERT {_version}"
        else:
            self.model_name    = model_name
            self.model_version = "paraphrase-multilingual-MiniLM-L12-v2 (base)"

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
            # Fallback sur le modèle de base si TalentMatch-BERT échoue
            if self.model_name != _BASE_MODEL:
                try:
                    self._model    = SentenceTransformer(_BASE_MODEL)
                    self.model_name    = _BASE_MODEL
                    self.model_version = _BASE_MODEL + " (fallback)"
                    self.ready     = True
                    self.load_error = None
                    return self._model
                except Exception:
                    pass
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
            # Encoding sans préfixe — le modèle TalentMatch-BERT a été entraîné
            # sur des paires texte brut (sans préfixes de rôle). Ajouter des
            # préfixes non vus à l'entraînement compresse les embeddings dans
            # une zone similaire et annule la discrimination fine-tunée.
            # Les textes sont clipsés à 128 mots pour rester dans la même
            # distribution que les triplets d'entraînement (~20-80 mots).
            offer_input = _clip_words(offer_text, 128)
            cv_input    = _clip_words(cv_text,    128)

            emb = model.encode(
                [offer_input, cv_input],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            # normalize_embeddings=True → cosine = produit scalaire ∈ [0, 1]
            # (en pratique positif pour des textes professionnels)
            sim = float(np.dot(emb[0], emb[1]))
            sim = max(0.0, min(1.0, sim))
            return float(sim), {
                "ready": True,
                "model": self.model_name,
                "method": "direct_cosine",
                "raw_similarity": round(sim, 4),
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
            # Encoding direct — noms de compétences bruts sans préfixe.
            # Les préfixes contextuels différents ("requise" vs "maîtrisée")
            # réduisent systématiquement la similarité cosinus sous le seuil
            # et produisent des scores nuls uniformes (= cap 25% pour tous).
            offer_emb = model.encode(
                [_normalize_skill(s) for s in offer_skills],
                convert_to_numpy=True, normalize_embeddings=True,
            )
            cv_emb = model.encode(
                [_normalize_skill(s) for s in cv_skills],
                convert_to_numpy=True, normalize_embeddings=True,
            )

            # Seuil 0.65 : suffisant pour Python≈Pandas ou TF≈PyTorch,
            # mais bloque Java≈Python (~0.55) et Jenkins≈TensorFlow (~0.45).
            THRESHOLD = 0.65

            per_skill: List[Dict[str, Any]] = []
            max_scores: List[float] = []
            for i, req in enumerate(offer_skills):
                best_sim, best_cv_skill = 0.0, None
                for j, cv_s in enumerate(cv_skills):
                    sim = float(np.dot(offer_emb[i], cv_emb[j]))
                    sim = max(0.0, min(1.0, sim))
                    if sim > best_sim:
                        best_sim = sim
                        best_cv_skill = cv_s

                # Rescaling : [THRESHOLD, 1] → [0, 1]  (en-dessous = 0)
                if best_sim >= THRESHOLD:
                    calibrated = (best_sim - THRESHOLD) / (1.0 - THRESHOLD)
                else:
                    calibrated = 0.0

                per_skill.append({
                    "required": req,
                    "best_match": best_cv_skill if best_sim >= THRESHOLD else None,
                    "raw_similarity": round(best_sim, 4),
                    "calibrated": round(calibrated, 4),
                    "matched": best_sim >= THRESHOLD,
                })
                max_scores.append(calibrated)

            score = float(np.mean(max_scores)) if max_scores else 0.5
            score = max(0.0, min(1.0, score))
            return score, {
                "ready": True,
                "model": self.model_name,
                "method": "contextual_bert",
                "offer_skills_count": len(offer_skills),
                "cv_skills_count": len(cv_skills),
                "per_skill": per_skill,
                "threshold": THRESHOLD,
                "matched_count": sum(1 for p in per_skill if p["matched"]),
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
            # Chercher aussi la forme normalisée (alias) dans le texte
            s_low = s.lower()
            s_norm = _normalize_skill(s)

            in_raw = s_low in raw_low or s_norm in raw_low
            if not in_raw:
                keep_most_severe({"skill": s, "level": 1, "reason": "absent_from_text"})

            in_exp = s_low in exp_low_joined or s_norm in exp_low_joined
            if experiences_texts and not in_exp:
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

    def compute_confidence(
        self,
        talentmatch_score: float,
        bert_base_score: float,
        heuristic_score: float,
    ) -> Dict[str, Any]:
        """
        Mesure l'accord entre les 3 composantes du matching.

        Si les 3 scores sont proches  → HAUTE  confiance
        Si légère divergence          → MOYENNE confiance
        Si forte divergence           → BASSE   confiance (vérif. humaine)

        Utilisé pour signaler au recruteur que le système est incertain.
        """
        scores = [
            max(0.0, min(1.0, float(talentmatch_score))),
            max(0.0, min(1.0, float(bert_base_score))),
            max(0.0, min(1.0, float(heuristic_score))),
        ]
        ecart = max(scores) - min(scores)

        if ecart < 0.15:
            niveau  = "HAUTE"
            message = "Les 3 modèles sont d'accord"
        elif ecart < 0.30:
            niveau  = "MOYENNE"
            message = "Légère divergence entre modèles"
        else:
            niveau  = "BASSE"
            message = "Vérification humaine recommandée"

        return {
            "niveau":   niveau,
            "ecart":    round(ecart, 3),
            "message":  message,
        }

    # ══════════════════════════════════════════════════════════════
    # SCORING MULTI-DIMENSIONNEL — 4 dimensions indépendantes
    # ══════════════════════════════════════════════════════════════

    def score_competences(
        self,
        offer_skills: List[str],
        cv_skills: List[str],
    ) -> float:
        """
        Dimension 1 — Compétences (40% du score final).

        Compte combien de compétences requises le candidat possède.
        RapidFuzz (seuil 80%) gère les variantes orthographiques :
        "Reactjs" ≈ "React.js", "PostgreSQL" ≈ "Postgres", etc.

        Exemples :
            Offre [Python, FastAPI, React, Docker] / CV [Python, FastAPI] → 0.50
            Offre [Python] / CV [Python, Django, Git]                     → 1.00
        """
        if not offer_skills:
            return 0.5

        matches = 0
        for required in offer_skills:
            req_norm = _normalize_skill(required)
            for cv_s in cv_skills:
                cv_norm = _normalize_skill(cv_s)
                # Alias-exact : "ReactJS" == "react" == "React.js" après normalisation
                if req_norm == cv_norm:
                    matches += 1
                    break
                # token_set_ratio gère les inversions ("REST API" ≈ "API REST")
                if fuzz.token_set_ratio(req_norm, cv_norm) >= 80:
                    matches += 1
                    break

        return round(min(1.0, matches / len(offer_skills)), 4)

    def score_experience(
        self,
        cv_years: float,
        required_years: float,
        offer_text: str = "",
        cv_experience_text: str = "",
    ) -> float:
        """
        Dimension 2 — Expérience (20% du score final).

        50% ratio années  +  50% similarité sémantique BERT du domaine d'expérience.
        Si le modèle est indisponible, repli sur le ratio seul.

        Exemples :
            Requis 2 ans dev Python, CV 3 ans dev Python → 1.00 (ratio OK + domaine OK)
            Requis 2 ans dev Python, CV 3 ans marketing  → ~0.55 (ratio OK, domaine éloigné)
            Requis 0 ans                                 → 1.00 (pas de prérequis)
        """
        # Composante 1 : ratio années
        if not required_years or required_years <= 0:
            years_ratio = 1.0
        elif cv_years >= required_years:
            years_ratio = 1.0
        else:
            years_ratio = max(0.0, cv_years / required_years)

        # Composante 2 : pertinence sémantique du domaine d'expérience
        if offer_text and cv_experience_text:
            domain_sim, _ = self.score_semantic(offer_text, cv_experience_text)
        else:
            domain_sim = years_ratio  # fallback : repli sur le ratio

        score = years_ratio * 0.50 + domain_sim * 0.50
        return round(max(0.0, min(1.0, score)), 4)

    def score_formation(
        self,
        cv_edu: float,
        required_edu: float,
    ) -> float:
        """
        Dimension 3 — Formation (15% du score final).

        Comparaison niveaux diplôme (Bac=1 … Doctorat=6).
        Dépasser le niveau requis → 100%.

        Exemples :
            Requis Bac+5, CV Bac+3 → 0.60
            Requis Bac+3, CV Bac+5 → 1.00
            Requis 0               → 1.00
        """
        if not required_edu or required_edu <= 0:
            return 1.0
        if cv_edu >= required_edu:
            return 1.0
        return round(max(0.0, cv_edu / required_edu), 4)

    def score_semantique(
        self,
        offer_text: str,
        cv_text: str,
    ) -> float:
        """
        Dimension 4 — Sémantique BERT (25% du score final).

        Similarité cosinus entre le vecteur offre et le vecteur CV.
        Score brut — aucune calibration.
        Fallback 0.5 si le modèle n'est pas disponible.
        """
        raw, _ = self.score_semantic(offer_text, cv_text)
        return float(raw)

    def _analyze_offer_profile(
        self,
        offer: "JobOffer",
        required_years: float,
        required_edu: float,
        offer_skills_count: int,
    ) -> Dict[str, Any]:
        """
        Analyse tous les signaux de l'offre pour déterminer le profil réel.
        Retourne un dict de flags utilisés par _dynamic_weights.
        """
        titre   = (offer.titre        or "").lower()
        desc    = (offer.description  or "").lower()
        contrat = (offer.type_contrat or "").lower()
        full    = titre + " " + desc

        # ── Type de poste ─────────────────────────────────────────
        is_stage       = any(k in contrat or k in full for k in ["stage", "internship", "stagiaire"])
        is_alternance  = any(k in contrat or k in full for k in ["alternance", "apprentissage", "alternant"])
        is_junior      = any(k in full for k in ["junior", "débutant", "debutant", "entry level", "sans expérience", "1ère expérience", "premiere experience"])
        is_senior      = any(k in full for k in ["senior", "lead", "expert", "confirmé", "confirme", "principal", "architect", "responsable", "manager", "chef de projet", "directeur"])

        # ── Domaine du poste ──────────────────────────────────────
        TECHNICAL_KEYWORDS = ["développeur", "developpeur", "developer", "ingénieur logiciel",
                               "data", "devops", "backend", "frontend", "fullstack",
                               "machine learning", "ia ", "ai ", "mlops", "cloud", "sécurité", "securite",
                               "python", "java", "react", "angular", "node", ".net", "php"]
        MANAGEMENT_KEYWORDS = ["manager", "directeur", "chef de projet", "responsable",
                                "commercial", "business", "vente", "marketing", "rh ",
                                "ressources humaines", "consultant", "account"]
        is_technical   = any(k in full for k in TECHNICAL_KEYWORDS) or offer_skills_count >= 4
        is_management  = any(k in full for k in MANAGEMENT_KEYWORDS)

        # ── Formation explicitement requise ───────────────────────
        STRONG_EDU = ["bac+5", "master", "ingénieur", "ingenieur", "grande école",
                      "grande ecole", "doctorat", "mba", "bac +5"]
        NO_EDU     = ["sans diplôme", "sans diplome", "niveau bac", "autodidacte",
                      "formation non requise", "pas de diplôme"]
        edu_required_explicit  = any(k in full for k in STRONG_EDU) or required_edu >= 5
        edu_not_required       = any(k in full for k in NO_EDU) or required_edu == 0

        return {
            "is_stage":              is_stage,
            "is_alternance":         is_alternance,
            "is_junior":             is_junior,
            "is_senior":             is_senior,
            "is_technical":          is_technical,
            "is_management":         is_management,
            "edu_required_explicit": edu_required_explicit,
            "edu_not_required":      edu_not_required,
            "required_years":        required_years,
            "offer_skills_count":    offer_skills_count,
        }

    def _dynamic_weights(
        self,
        profile: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Poids adaptatifs — s'adapte à CE QUE L'OFFRE DEMANDE réellement.

        Exemples :
          Stage/Alternance  → exp≈0%, formation monte, compétences + sémantique priment
          Junior (0 ans)    → exp très faible, compétences + sémantique fortes
          Confirmé (2-4 ans)→ poids équilibrés
          Senior (5+ ans)   → exp très forte
          Technique (dev)   → compétences forte
          Management        → sémantique forte
          Diplôme exigé     → formation monte
          Pas de diplôme    → formation ≈ 0%
          Peu de skills     → sémantique compensatrice
        """
        # ── Poids initiaux de base ────────────────────────────────
        w_comp = 0.40
        w_exp  = 0.20
        w_form = 0.15
        w_sem  = 0.25

        required_years      = profile["required_years"]
        offer_skills_count  = profile["offer_skills_count"]

        # ── 1. Adapter selon le type de poste ────────────────────
        if profile["is_stage"] or profile["is_alternance"]:
            # Étudiant : exp quasi nulle, formation importante, skills + sémantique
            w_exp  = 0.03
            w_comp = 0.42
            w_form = 0.22
            w_sem  = 0.33

        elif profile["is_junior"] or required_years == 0:
            # Junior : peu d'exp attendue
            w_exp  = 0.06
            w_comp = 0.44
            w_form = 0.15
            w_sem  = 0.35

        elif profile["is_senior"] or required_years >= 5:
            # Senior : expérience très importante
            w_exp  = 0.33
            w_comp = 0.34
            w_form = 0.13
            w_sem  = 0.20

        elif required_years >= 3:
            # Confirmé
            w_exp  = 0.25
            w_comp = 0.38
            w_form = 0.14
            w_sem  = 0.23

        else:
            # Débutant / 1-2 ans
            w_exp  = 0.12
            w_comp = 0.43
            w_form = 0.15
            w_sem  = 0.30

        # ── 2. Adapter selon le domaine ──────────────────────────
        if profile["is_technical"] and not profile["is_management"]:
            # Poste technique → compétences techniques priment
            w_comp += 0.05
            w_sem  -= 0.05
        elif profile["is_management"] and not profile["is_technical"]:
            # Poste management/commercial → sémantique et soft skills priment
            w_sem  += 0.08
            w_comp -= 0.08

        # ── 3. Adapter selon la formation ────────────────────────
        if profile["edu_required_explicit"]:
            # Diplôme clairement exigé → formation pèse plus
            w_form += 0.08
            w_sem  -= 0.08
        elif profile["edu_not_required"]:
            # Pas de diplôme requis → formation quasi nulle
            delta   = w_form * 0.80
            w_form -= delta
            w_comp += delta * 0.5
            w_sem  += delta * 0.5

        # ── 4. Adapter selon le nombre de skills ─────────────────
        if offer_skills_count < 3:
            # Peu de skills listées → sémantique compensatrice
            delta   = w_comp * 0.35
            w_comp -= delta
            w_sem  += delta
        elif offer_skills_count >= 8:
            # Beaucoup de skills → les compétences sont le critère principal
            w_comp += 0.04
            w_sem  -= 0.04

        # ── Normaliser pour que la somme = 1.0 ───────────────────
        w_comp = max(0.05, w_comp)
        w_exp  = max(0.02, w_exp)
        w_form = max(0.02, w_form)
        w_sem  = max(0.05, w_sem)
        total  = w_comp + w_exp + w_form + w_sem
        return {
            "competences": round(w_comp / total, 4),
            "experience":  round(w_exp  / total, 4),
            "formation":   round(w_form / total, 4),
            "semantique":  round(w_sem  / total, 4),
        }

    def score(
        self,
        offer: JobOffer,
        candidate: Candidate,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Score final multi-dimensionnel TalentMatch — poids adaptatifs.

        Les poids changent selon ce que l'offre exige réellement :
        junior → expérience quasi-nulle, senior → expérience forte.

        Résultat absolu — indépendant des autres candidats.
        """
        # ── Extraction des données ────────────────────────────────
        offer_skills   = _extract_offer_skills(offer)
        cv_skills      = _candidate_skills(candidate)
        cand_years     = _candidate_years(candidate)
        cand_edu       = _candidate_education_level(candidate)
        desc_blob      = ((offer.description or "") + "\n" + (offer.titre or "")).strip()
        required_years = _extract_required_years(desc_blob) or 0
        required_edu   = _extract_required_education_level(desc_blob) or 0
        offer_text     = _offer_text_for_semantic(offer)
        cv_text        = _candidate_text_for_semantic(candidate)

        # ── Texte d'expérience candidat (pour BERT expérience) ───
        parsed_for_exp = candidate.parsed_data if isinstance(candidate.parsed_data, dict) else {}
        exp_parts: List[str] = []
        for exp in (parsed_for_exp.get("experiences") or []):
            if not isinstance(exp, dict):
                continue
            for key in ("poste", "title", "entreprise", "company", "description"):
                val = exp.get(key)
                if isinstance(val, str) and val.strip():
                    exp_parts.append(val.strip())
        cv_experience_text = _clip_words(" ".join(exp_parts), 128) if exp_parts else ""

        # ── 4 dimensions ─────────────────────────────────────────
        # Compétences : hybride RapidFuzz + BERT + fallback texte brut
        # Normaliser les apostrophes typographiques (U+2019) → ASCII (U+0027)
        # pour que "pas d'expérience" soit détecté même dans les PDFs reportlab.
        raw_lower = (candidate.raw_text or "").lower().replace("’", "'").replace("‘", "'")

        # Filtrer les skills extraits par le parseur NLP mais mentionnés
        # uniquement dans un contexte négatif ("Aucune compétence en Python").
        # Le parseur détecte les mots-clés sans comprendre la négation.
        _NEGATIONS_CTX = ("pas de", "pas d'", "sans ", "aucune", "aucun",
                          "jamais", "no ", "not ", "without", "non ",
                          "zero", "n'ai pas", "n'a pas", "ne pas",
                          "peu utilis", "peu d'exp")

        def _is_negated(skill_name: str) -> bool:
            s_low  = skill_name.lower()
            s_norm = _normalize_skill(skill_name)
            all_negated = True
            for term in {s_low, s_norm}:
                idx = 0
                found_any = False
                while True:
                    pos = raw_lower.find(term, idx)
                    if pos == -1:
                        break
                    found_any = True
                    ctx = raw_lower[max(0, pos - 60): pos]
                    if not any(neg in ctx for neg in _NEGATIONS_CTX):
                        return False  # au moins une occurrence positive
                    idx = pos + 1
                if found_any:
                    all_negated = True
            # Si le skill n'est pas dans le texte brut du tout → non nié (extrait d'une section structurée)
            return raw_lower.count(s_low) > 0 and all_negated

        cv_skills_filtered = [s for s in cv_skills if not _is_negated(s)]
        cv_norms  = {_normalize_skill(s): s for s in cv_skills_filtered}

        skills_matched: List[Dict[str, str]] = []
        skills_missing: List[str] = []
        total_comp = 0.0

        for skill in offer_skills:
            norm = _normalize_skill(skill)
            # 1) Match exact après normalisation alias
            if norm in cv_norms:
                skills_matched.append({"skill": skill, "source": "extrait"})
                total_comp += 1.0
                continue
            # 2) Fuzzy match sur les skills parsés (filtrés — sans les niés)
            best_fz = max(
                (fuzz.token_set_ratio(norm, _normalize_skill(s)) for s in cv_skills_filtered),
                default=0,
            )
            if best_fz >= 80:
                skills_matched.append({"skill": skill, "source": "fuzzy"})
                total_comp += 1.0
                continue
            # 3) Fallback texte brut — uniquement si la mention n'est pas niée.
            # Cherche la skill dans le texte brut, puis vérifie qu'aucun mot de
            # négation n'apparaît dans les 60 caractères qui précèdent.
            skill_lower = skill.lower()
            idx = raw_lower.find(norm) if norm in raw_lower else (
                raw_lower.find(skill_lower) if skill_lower in raw_lower else -1
            )
            if idx != -1:
                context_before = raw_lower[max(0, idx - 60):idx]
                if not any(neg in context_before for neg in _NEGATIONS_CTX):
                    skills_matched.append({"skill": skill, "source": "texte_brut"})
                    total_comp += 0.7
                    continue
            skills_missing.append(skill)

        s_fuzzy_v2    = round(min(1.0, total_comp / max(1, len(offer_skills))), 4) if offer_skills else 0.5
        s_bert_skills, _ = self.score_skills_bert(offer_skills, cv_skills_filtered)
        # Fuzzy est le signal principal (exact + alias + texte brut).
        # BERT peut ajouter au max +10% pour les synonymes proches (PyTorch ≈ TensorFlow)
        # mais ne peut pas compenser des skills complètement absents.
        _bert_bonus   = max(0.0, s_bert_skills - s_fuzzy_v2) * 0.20
        s_competences = round(min(1.0, s_fuzzy_v2 + _bert_bonus), 4)
        # Expérience  : ratio années + BERT domaine
        s_experience  = self.score_experience(cand_years, required_years, offer_text, cv_experience_text)
        s_formation   = self.score_formation(cand_edu, required_edu)
        s_semantique  = self.score_semantique(offer_text, cv_text)

        # ── Poids dynamiques selon le profil de l'offre ─────────
        offer_profile = self._analyze_offer_profile(offer, required_years, required_edu, len(offer_skills))
        W = self._dynamic_weights(offer_profile)

        # Fix 2 — Formation pénalisée si compétences faibles.
        # Un Bac+5 en Java ne compense pas un poste Python.
        if s_competences <= 0.50:
            s_formation = s_formation * 0.5

        # Fix 5 — Expérience pénalisée si domaine incompatible.
        # 5 ans de Java ne valent pas grand chose pour un poste Python/ML.
        if s_competences <= 0.40:
            s_experience = s_experience * (0.5 + s_competences)  # réduit graduellement

        # ── Score final pondéré ──────────────────────────────────
        score_final = (
            s_competences * W["competences"]
            + s_experience  * W["experience"]
            + s_formation   * W["formation"]
            + s_semantique  * W["semantique"]
        )

        # Fix 1 — Cap progressif selon la cohérence du domaine.
        # < 25% compétences → hors domaine total → max 32%
        # < 40% compétences → match très partiel → max 42%
        # <= 50% compétences → domaine incompatible → max 52%
        if s_competences < 0.25:
            score_final = min(score_final, 0.32)
        elif s_competences < 0.40:
            score_final = min(score_final, 0.42)
        elif s_competences <= 0.50:
            score_final = min(score_final, 0.52)

        # Plancher 20% : tout candidat ayant soumis un CV mérite au moins 20%.
        # Plafond 95% : aucun CV n'est parfait à 100%.
        score_final = round(max(0.20, min(0.95, score_final)), 4)

        # ── Détection incohérences (signal qualitatif) ───────────
        parsed = candidate.parsed_data if isinstance(candidate.parsed_data, dict) else {}
        experiences = parsed.get("experiences") if isinstance(parsed, dict) else []
        cv_skills_lower = {s.lower() for s in cv_skills}
        skills_to_check = [s for s in offer_skills if s.lower() in cv_skills_lower]
        inconsistencies = self.detect_skill_inconsistencies(
            cv_skills=skills_to_check if skills_to_check else offer_skills[:5],
            cv_experiences=experiences,
            cv_raw_text=(candidate.raw_text or ""),
        )

        # ── Breakdown détaillé ───────────────────────────────────
        details: Dict[str, Any] = {
            # Dimensions en pourcentage
            "competences": round(s_competences * 100, 1),
            "experience":  round(s_experience  * 100, 1),
            "formation":   round(s_formation   * 100, 1),
            "semantique":  round(s_semantique  * 100, 1),
            "total":       round(score_final   * 100, 1),
            "poids": {
                "competences": f"{round(W['competences']*100)}% (BERT skills)",
                "experience":  f"{round(W['experience']*100)}% (BERT domaine + années)",
                "formation":   f"{round(W['formation']*100)}% (niveau diplôme)",
                "semantique":  f"{round(W['semantique']*100)}% (BERT global)",
            },
            "profil_offre": {
                "type":    "stage/alternance" if (offer_profile["is_stage"] or offer_profile["is_alternance"])
                           else "junior"    if (offer_profile["is_junior"] or required_years == 0)
                           else "senior"    if (offer_profile["is_senior"] or required_years >= 5)
                           else "confirmé"  if required_years >= 3
                           else "débutant",
                "domaine": "technique"  if offer_profile["is_technical"]
                           else "management" if offer_profile["is_management"]
                           else "général",
                "required_years":      required_years,
                "edu_explicite":       offer_profile["edu_required_explicit"],
            },
            # Explication par skills
            "skills_matched":      skills_matched,
            "skills_missing":      skills_missing,
            "skills_match_rate":   round(len(skills_matched) / max(1, len(offer_skills)) * 100, 1),
            # Détails contextuels
            "offer_skills_count":  len(offer_skills),
            "cv_skills_count":     len(cv_skills),
            "required_years":      required_years,
            "candidate_years":     cand_years,
            "required_edu":        required_edu,
            "candidate_edu":       cand_edu,
            "inconsistencies":     inconsistencies,
            # Compat backend/frontend
            "ready":               bool(self.ready),
            "model":               self.model_name,
            "bert_semantic":       round(s_semantique, 4),
            "bert_skills":         round(s_competences, 4),
        }

        return score_final, details