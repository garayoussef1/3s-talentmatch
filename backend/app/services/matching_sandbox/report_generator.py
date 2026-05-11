"""
ReportGenerator — Rapport explicatif par candidat pour le recruteur.

Pour chaque candidat scoré, génère un rapport structuré qui explique :
  - Pourquoi ce score (points forts / faibles)
  - Compétences manquantes vs requises
  - Niveau de confiance du système (cohérence entre modèles)
  - Recommandation actionnable pour le recruteur
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.services.matching.match_engine import (
    _candidate_education_level,
    _candidate_skills,
    _candidate_years,
    _extract_offer_skills,
    _extract_required_education_level,
    _extract_required_years,
    _normalize_skill,
)


class ReportGenerator:
    """Génère un rapport RH explicatif à partir des scores de matching."""

    # ─────────────────────────────────────────────
    # Point d'entrée principal
    # ─────────────────────────────────────────────

    def generate_candidate_report(
        self,
        candidate: Candidate,
        job_offer: JobOffer,
        scores: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Génère le rapport complet pour un candidat.

        scores attendu :
          {
            "heuristic": float,
            "bert_base": float,
            "talentmatch": float,
            "hybrid": float,
            "inconsistencies": [...],
            "bert_details": {...}
          }
        """
        hybrid     = float(scores.get("hybrid", 0))
        heuristic  = float(scores.get("heuristic", 0))
        bert_base  = float(scores.get("bert_base", 0))
        talentmatch = float(scores.get("talentmatch", 0))

        strong_points  = self._get_strong_points(candidate, job_offer)
        missing_skills = self._get_missing_skills(candidate, job_offer)
        weak_points    = self._get_weak_points(candidate, job_offer, scores)

        recommendation = self._get_recommendation(hybrid)
        confidence     = self._compute_confidence(heuristic, bert_base, talentmatch)

        desc_blob = ((job_offer.description or "") + "\n" + (job_offer.titre or "")).strip()
        req_years  = _extract_required_years(desc_blob)
        req_edu    = _extract_required_education_level(desc_blob)
        cand_years = _candidate_years(candidate)
        cand_edu   = _candidate_education_level(candidate)

        exp_match = (req_years is None or req_years == 0 or cand_years >= req_years)
        edu_match = (req_edu  is None or req_edu  == 0 or cand_edu  >= req_edu)

        explanation = self._build_explanation(
            candidate, job_offer, hybrid, strong_points,
            missing_skills, exp_match, edu_match, confidence
        )
        action = self._build_action(recommendation, confidence, missing_skills)

        return {
            "recommendation":   recommendation,
            "confidence":       confidence,
            "strong_points":    strong_points,
            "weak_points":      weak_points,
            "missing_skills":   missing_skills,
            "experience_match": exp_match,
            "education_match":  edu_match,
            "explanation":      explanation,
            "action":           action,
            "scores_summary": {
                "hybrid":      round(hybrid,      3),
                "heuristic":   round(heuristic,   3),
                "talentmatch": round(talentmatch,  3),
            },
        }

    # ─────────────────────────────────────────────
    # Recommandation selon score hybride
    # ─────────────────────────────────────────────

    def _get_recommendation(self, hybrid_score: float) -> str:
        """
        >= 0.70 → HAUTEMENT_RECOMMANDE
        >= 0.50 → RECOMMANDE
        >= 0.30 → NEUTRE
        <  0.30 → NON_RECOMMANDE
        """
        if hybrid_score >= 0.70:
            return "HAUTEMENT_RECOMMANDE"
        if hybrid_score >= 0.50:
            return "RECOMMANDE"
        if hybrid_score >= 0.30:
            return "NEUTRE"
        return "NON_RECOMMANDE"

    # ─────────────────────────────────────────────
    # Niveau de confiance (cohérence entre modèles)
    # ─────────────────────────────────────────────

    def _compute_confidence(
        self,
        heuristic: float,
        bert_base: float,
        talentmatch: float,
    ) -> str:
        """
        HAUTE   : écart max entre les 3 scores < 0.15
        MOYENNE : écart max entre les 3 scores < 0.30
        BASSE   : écart max entre les 3 scores >= 0.30
        """
        scores = [s for s in [heuristic, bert_base, talentmatch] if s > 0]
        if len(scores) < 2:
            return "BASSE"
        ecart = max(scores) - min(scores)
        if ecart < 0.15:
            return "HAUTE"
        if ecart < 0.30:
            return "MOYENNE"
        return "BASSE"

    # ─────────────────────────────────────────────
    # Points forts
    # ─────────────────────────────────────────────

    def _get_strong_points(
        self,
        candidate: Candidate,
        job_offer: JobOffer,
    ) -> List[str]:
        """
        Skills présentes dans l'offre ET dans le CV = points forts.
        Années exp et niveau éducation sont aussi évalués.
        """
        points: List[str] = []

        offer_skills = {_normalize_skill(s) for s in _extract_offer_skills(job_offer)}
        cv_skills    = {_normalize_skill(s): s for s in _candidate_skills(candidate)}

        for norm, original in cv_skills.items():
            if norm in offer_skills:
                points.append(f"{original} ✓")

        # Expérience suffisante
        desc_blob  = ((job_offer.description or "") + "\n" + (job_offer.titre or "")).strip()
        req_years  = _extract_required_years(desc_blob)
        cand_years = _candidate_years(candidate)
        if req_years and req_years > 0 and cand_years >= req_years:
            points.append(f"{cand_years} ans d'expérience ✓")

        # Formation suffisante
        req_edu  = _extract_required_education_level(desc_blob)
        cand_edu = _candidate_education_level(candidate)
        if req_edu and req_edu > 0 and cand_edu >= req_edu:
            edu_labels = {3: "Bac+3", 4: "Bac+4", 5: "Bac+5", 6: "Bac+6+"}
            points.append(f"{edu_labels.get(cand_edu, f'Bac+{cand_edu}')} ✓")

        return points[:8]  # max 8 points forts

    # ─────────────────────────────────────────────
    # Compétences manquantes
    # ─────────────────────────────────────────────

    def _get_missing_skills(
        self,
        candidate: Candidate,
        job_offer: JobOffer,
    ) -> List[str]:
        """
        Skills requises dans l'offre mais absentes du CV.
        """
        offer_skills = _extract_offer_skills(job_offer)
        cv_norms     = {_normalize_skill(s) for s in _candidate_skills(candidate)}

        missing = []
        for s in offer_skills:
            if _normalize_skill(s) not in cv_norms:
                missing.append(s)

        return missing[:6]  # max 6 compétences manquantes

    # ─────────────────────────────────────────────
    # Points d'attention
    # ─────────────────────────────────────────────

    def _get_weak_points(
        self,
        candidate: Candidate,
        job_offer: JobOffer,
        scores: Dict[str, Any],
    ) -> List[str]:
        """
        Points d'attention : expérience insuffisante, incohérences, domaine éloigné.
        """
        points: List[str] = []

        desc_blob  = ((job_offer.description or "") + "\n" + (job_offer.titre or "")).strip()
        req_years  = _extract_required_years(desc_blob)
        cand_years = _candidate_years(candidate)
        if req_years and req_years > 0 and cand_years < req_years:
            points.append(f"Expérience insuffisante ({cand_years} ans / {req_years} requis)")

        req_edu  = _extract_required_education_level(desc_blob)
        cand_edu = _candidate_education_level(candidate)
        if req_edu and req_edu > 0 and cand_edu < req_edu:
            points.append(f"Formation en dessous du requis (Bac+{cand_edu} / Bac+{req_edu} requis)")

        # Incohérences de skills
        inco = scores.get("inconsistencies", [])
        if isinstance(inco, list):
            for inc in inco[:3]:
                skill  = inc.get("skill", "")
                reason = inc.get("reason", "")
                if reason == "absent_from_experiences":
                    points.append(f"{skill} : non confirmé par les expériences")
                elif reason == "absent_from_text":
                    points.append(f"{skill} : absent du texte du CV")
                elif reason.startswith("missing_ecosystem"):
                    eco = reason.split(":")[-1]
                    points.append(f"{skill} : écosystème {eco} manquant")

        return points[:5]

    # ─────────────────────────────────────────────
    # Texte d'explication (français)
    # ─────────────────────────────────────────────

    def _build_explanation(
        self,
        candidate: Candidate,
        job_offer: JobOffer,
        hybrid: float,
        strong_points: List[str],
        missing_skills: List[str],
        exp_match: bool,
        edu_match: bool,
        confidence: str,
    ) -> str:
        nom   = candidate.nom or "Ce candidat"
        titre = job_offer.titre or "ce poste"
        pct   = round(hybrid * 100, 1)

        # Phrase d'intro selon le score
        if hybrid >= 0.70:
            intro = f"{nom} présente un profil très bien aligné avec {titre} (score {pct}%)."
        elif hybrid >= 0.50:
            intro = f"{nom} correspond bien aux exigences de {titre} (score {pct}%)."
        elif hybrid >= 0.30:
            intro = f"{nom} présente un profil partiel pour {titre} (score {pct}%)."
        else:
            intro = f"{nom} présente un faible alignement avec {titre} (score {pct}%)."

        # Points forts
        if strong_points:
            skills_str = ", ".join(strong_points[:3])
            detail = f" Points forts : {skills_str}."
        else:
            detail = " Peu de compétences en commun avec l'offre."

        # Manques
        if missing_skills:
            manques = ", ".join(missing_skills[:3])
            manque_str = f" Compétences manquantes : {manques}."
        else:
            manque_str = " Toutes les compétences clés sont présentes."

        # Confiance
        if confidence == "BASSE":
            conf_str = " Les différents modèles donnent des scores divergents — vérification humaine recommandée."
        else:
            conf_str = ""

        return intro + detail + manque_str + conf_str

    # ─────────────────────────────────────────────
    # Action conseillée au recruteur
    # ─────────────────────────────────────────────

    def _build_action(
        self,
        recommendation: str,
        confidence: str,
        missing_skills: List[str],
    ) -> str:
        if recommendation == "HAUTEMENT_RECOMMANDE":
            return "Entretien technique recommandé en priorité."
        if recommendation == "RECOMMANDE":
            if missing_skills:
                manques = ", ".join(missing_skills[:2])
                return f"Entretien recommandé. Vérifier les compétences : {manques}."
            return "Entretien recommandé pour valider les compétences clés."
        if recommendation == "NEUTRE":
            if confidence == "BASSE":
                return "Revue manuelle du CV conseillée avant décision. Scores divergents."
            return "Profil partiel — à considérer si peu de candidats disponibles."
        # NON_RECOMMANDE
        return "Profil insuffisant pour ce poste. Recommander d'autres offres si disponibles."
