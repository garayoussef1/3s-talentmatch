"""
ClaudeSummarizer — Synthèse RH professionnelle générée par l'IA.

Priorité :
  1. Ollama (local, zéro internet) — modèle configuré via OLLAMA_MODEL (défaut: mistral)
  2. Claude API (si ANTHROPIC_API_KEY présent)
  3. Fallback règle-based (toujours disponible)
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral")


def _ollama_available() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _ollama_generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 400},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("response", "").strip()


class ClaudeSummarizer:
    """Génère un résumé RH professionnel via Ollama (local) ou Claude API (fallback)."""

    CLAUDE_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._claude_client: Optional[Any] = None
        self._use_ollama = _ollama_available()

        if not self._use_ollama and self._api_key:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                pass

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
        prompt = self._build_prompt(candidate_data, job_offer_data, matching_scores, report)

        if self._use_ollama:
            try:
                text = _ollama_generate(prompt)
                return {"summary": text, "source": "ollama", "model": OLLAMA_MODEL}
            except Exception as exc:
                pass  # tombe sur Claude ou fallback

        if self._claude_client:
            try:
                msg = self._claude_client.messages.create(
                    model=self.CLAUDE_MODEL,
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                return {
                    "summary": msg.content[0].text.strip(),
                    "source": "claude",
                    "model": self.CLAUDE_MODEL,
                }
            except Exception:
                pass

        return self._fallback_summary(candidate_data, matching_scores, report)

    # ─────────────────────────────────────────────
    # Prompt commun
    # ─────────────────────────────────────────────

    def _build_prompt(
        self,
        candidate: Dict[str, Any],
        offer: Dict[str, Any],
        scores: Dict[str, Any],
        report: Dict[str, Any],
    ) -> str:
        nom        = candidate.get("nom", "Candidat inconnu")
        poste      = offer.get("titre", "Poste non précisé")
        score_pct  = round(float(scores.get("hybrid", scores.get("bert_score", 0))) * 100, 1)
        recomm     = report.get("recommendation", "NEUTRE")
        strong     = ", ".join(report.get("strong_points", [])[:4]) or "Aucun"
        missing    = ", ".join(report.get("missing_skills", [])[:3]) or "Aucune"
        exp_ok     = "Oui" if report.get("experience_match") else "Non"
        edu_ok     = "Oui" if report.get("education_match") else "Non"

        return (
            f"Tu es un assistant RH expert. Rédige en français un résumé professionnel "
            f"de 3 phrases maximum pour un recruteur, concernant la candidature suivante.\n\n"
            f"Candidat : {nom}\n"
            f"Poste visé : {poste}\n"
            f"Score de matching : {score_pct}%\n"
            f"Recommandation système : {recomm}\n"
            f"Points forts : {strong}\n"
            f"Compétences manquantes : {missing}\n"
            f"Expérience suffisante : {exp_ok}\n"
            f"Formation suffisante : {edu_ok}\n\n"
            f"Réponds uniquement avec le résumé (3 phrases max, texte fluide, pas de bullet points)."
        )

    # ─────────────────────────────────────────────
    # Fallback règle-based
    # ─────────────────────────────────────────────

    def _fallback_summary(
        self,
        candidate_data: Dict[str, Any],
        matching_scores: Dict[str, Any],
        report: Dict[str, Any],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        nom        = candidate_data.get("nom", "Ce candidat")
        score_pct  = round(float(matching_scores.get("hybrid", matching_scores.get("bert_score", 0))) * 100, 1)
        recomm     = report.get("recommendation", "NEUTRE")
        strong     = report.get("strong_points", [])
        missing    = report.get("missing_skills", [])
        confidence = report.get("confidence", "MOYENNE")

        labels = {
            "HAUTEMENT_RECOMMANDE": "est un profil fortement recommandé",
            "RECOMMANDE":           "correspond aux exigences du poste",
            "NEUTRE":               "présente un profil partiel",
            "NON_RECOMMANDE":       "ne correspond pas aux critères requis",
        }
        p1 = f"{nom} {labels.get(recomm, 'a été évalué')} avec un score de {score_pct}%."
        p2 = f"Points forts identifiés : {', '.join(strong[:3])}." if strong else "Peu de compétences en commun ont été identifiées."
        if missing:
            p3 = f"Compétences à vérifier lors de l'entretien : {', '.join(missing[:3])}."
        elif confidence == "BASSE":
            p3 = "Une revue manuelle est conseillée en raison de la divergence des modèles."
        else:
            p3 = "Le profil couvre l'ensemble des compétences clés du poste."

        result: Dict[str, Any] = {"summary": f"{p1} {p2} {p3}", "source": "fallback", "model": None}
        if error:
            result["error"] = error
        return result
