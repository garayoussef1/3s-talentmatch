"""
ClaudeSummarizer — Synthèse RH professionnelle générée par l'IA.

Utilise l'API Claude (claude-haiku-4-5) pour produire un résumé structuré
en français destiné au recruteur, basé sur les scores et le rapport de matching.

Fallback automatique si ANTHROPIC_API_KEY est absent : génère un résumé
règle-based sans appel API.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


class ClaudeSummarizer:
    """Génère un résumé RH professionnel via Claude API (avec fallback règle-based)."""

    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client: Optional[Any] = None

        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                self._client = None

    # ─────────────────────────────────────────────
    # Point d'entrée principal
    # ─────────────────────────────────────────────

    def generate_candidate_summary(
        self,
        candidate_data: Dict[str, Any],
        job_offer_data: Dict[str, Any],
        matching_scores: Dict[str, Any],
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Génère un résumé RH pour un candidat.

        Retourne :
          {
            "summary": str,           # texte du résumé
            "source": "claude" | "fallback",
            "model": str | None,
          }
        """
        if self._client:
            try:
                return self._claude_summary(
                    candidate_data, job_offer_data, matching_scores, report
                )
            except Exception as exc:
                return self._fallback_summary(
                    candidate_data, matching_scores, report,
                    error=str(exc)
                )
        return self._fallback_summary(candidate_data, matching_scores, report)

    # ─────────────────────────────────────────────
    # Résumé via Claude API
    # ─────────────────────────────────────────────

    def _claude_summary(
        self,
        candidate_data: Dict[str, Any],
        job_offer_data: Dict[str, Any],
        matching_scores: Dict[str, Any],
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(
            candidate_data, job_offer_data, matching_scores, report
        )

        message = self._client.messages.create(
            model=self.MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()

        return {
            "summary": text,
            "source": "claude",
            "model": self.MODEL,
        }

    def _build_prompt(
        self,
        candidate: Dict[str, Any],
        offer: Dict[str, Any],
        scores: Dict[str, Any],
        report: Dict[str, Any],
    ) -> str:
        nom         = candidate.get("nom", "Candidat inconnu")
        poste       = offer.get("titre", "Poste non précisé")
        hybrid_pct  = round(float(scores.get("hybrid", 0)) * 100, 1)
        recomm      = report.get("recommendation", "NEUTRE")
        strong      = ", ".join(report.get("strong_points", [])[:4]) or "Aucun"
        missing     = ", ".join(report.get("missing_skills", [])[:3]) or "Aucune"
        confidence  = report.get("confidence", "MOYENNE")
        exp_ok      = "Oui" if report.get("experience_match") else "Non"
        edu_ok      = "Oui" if report.get("education_match") else "Non"

        return (
            f"Tu es un assistant RH expert. Rédige en français un résumé professionnel "
            f"de 3 phrases maximum pour un recruteur, concernant la candidature suivante.\n\n"
            f"Candidat : {nom}\n"
            f"Poste visé : {poste}\n"
            f"Score de matching : {hybrid_pct}%\n"
            f"Recommandation système : {recomm}\n"
            f"Points forts : {strong}\n"
            f"Compétences manquantes : {missing}\n"
            f"Expérience suffisante : {exp_ok}\n"
            f"Formation suffisante : {edu_ok}\n"
            f"Confiance du modèle : {confidence}\n\n"
            f"Le résumé doit être direct, factuel et aider le recruteur à prendre "
            f"une décision rapide. Pas de bullet points, uniquement du texte fluide."
        )

    # ─────────────────────────────────────────────
    # Résumé règle-based (fallback)
    # ─────────────────────────────────────────────

    def _fallback_summary(
        self,
        candidate_data: Dict[str, Any],
        matching_scores: Dict[str, Any],
        report: Dict[str, Any],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        nom        = candidate_data.get("nom", "Ce candidat")
        hybrid_pct = round(float(matching_scores.get("hybrid", 0)) * 100, 1)
        recomm     = report.get("recommendation", "NEUTRE")
        strong     = report.get("strong_points", [])
        missing    = report.get("missing_skills", [])
        confidence = report.get("confidence", "MOYENNE")

        # Phrase 1 — score et recommandation
        labels = {
            "HAUTEMENT_RECOMMANDE": "est un profil fortement recommandé",
            "RECOMMANDE":           "correspond aux exigences du poste",
            "NEUTRE":               "présente un profil partiel",
            "NON_RECOMMANDE":       "ne correspond pas aux critères requis",
        }
        p1 = f"{nom} {labels.get(recomm, 'a été évalué')} avec un score de {hybrid_pct}%."

        # Phrase 2 — points forts
        if strong:
            p2 = f"Points forts identifiés : {', '.join(strong[:3])}."
        else:
            p2 = "Peu de compétences en commun avec l'offre ont été identifiées."

        # Phrase 3 — manques ou confiance
        if missing:
            p3 = f"Compétences à vérifier lors de l'entretien : {', '.join(missing[:3])}."
        elif confidence == "BASSE":
            p3 = "Les scores des différents modèles divergent — une revue manuelle est conseillée."
        else:
            p3 = "Le profil couvre l'ensemble des compétences clés du poste."

        summary = f"{p1} {p2} {p3}"

        result: Dict[str, Any] = {
            "summary": summary,
            "source": "fallback",
            "model": None,
        }
        if error:
            result["error"] = error
        return result
