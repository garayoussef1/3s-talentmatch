"""
ClaudeSummarizer — Rapports RH professionnels générés par l'IA.

Deux niveaux de rapport :
  1. Fiche d'évaluation par candidat  → generate_candidate_summary()
  2. Synthèse exécutive du matching    → generate_global_summary()

Principe de fiabilité (Mistral 7B hallucine sur les chiffres) :
  • Le CODE calcule tous les FAITS (verdict, notes /10, répartition, sélection).
  • L'IA (Mistral via Ollama) ne rédige QUE le qualitatif (forces, vigilance, reco).
  • Parsing par marqueurs stricts + few-shot pour un format constant.

Priorité moteur : Ollama (local) → Claude API → fallback règle-based (toujours dispo).
"""
from __future__ import annotations

import os
import re
import json
import urllib.request
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


def _ollama_generate(prompt: str, model: str = OLLAMA_MODEL, num_predict: int = 500) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": num_predict, "top_p": 0.9},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("response", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de parsing / nettoyage
# ─────────────────────────────────────────────────────────────────────────────
def _clean_line(line: str) -> str:
    """Nettoie une ligne : retire puces, numéros, espaces superflus."""
    line = line.strip()
    line = re.sub(r"^[\-\*•·–—\d\.\)\]]+\s*", "", line)
    return line.strip(" .")


def _parse_marked_sections(text: str, markers: List[str]) -> Dict[str, str]:
    """Découpe un texte selon des marqueurs ===NOM=== en sections."""
    sections: Dict[str, str] = {m: "" for m in markers}
    pattern = "|".join(re.escape(f"==={m}===") for m in markers)
    parts = re.split(f"({pattern})", text)
    current = None
    for part in parts:
        stripped = part.strip()
        matched = next((m for m in markers if stripped == f"==={m}==="), None)
        if matched:
            current = matched
        elif current:
            sections[current] += part
    return {k: v.strip() for k, v in sections.items()}


def _bullets(text: str, limit: int = 4) -> List[str]:
    """Extrait des puces propres depuis un bloc de texte."""
    out: List[str] = []
    for line in text.splitlines():
        c = _clean_line(line)
        if len(c) >= 4 and not c.lower().startswith(("aucun", "n/a", "rien")):
            out.append(c)
        if len(out) >= limit:
            break
    return out


def _first_sentence_block(text: str, max_chars: int = 320) -> str:
    """Nettoie un bloc de prose (retire préambules Mistral, limite la longueur)."""
    text = text.strip()
    # Retire les préambules parasites courants de Mistral
    text = re.sub(r"^(voici|bien s[ûu]r|voil[àa])[^:]*:\s*", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        cut = text[:max_chars]
        last_dot = cut.rfind(".")
        text = cut[:last_dot + 1] if last_dot > 40 else cut + "…"
    return text


class ClaudeSummarizer:
    """Génère les rapports RH (fiche candidat + synthèse globale)."""

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

    def _ai_generate(self, prompt: str, num_predict: int = 500) -> Optional[str]:
        """Tente Ollama puis Claude. Retourne None si aucun moteur dispo."""
        if self._use_ollama:
            try:
                return _ollama_generate(prompt, num_predict=num_predict)
            except Exception:
                pass
        if self._claude_client:
            try:
                msg = self._claude_client.messages.create(
                    model=self.CLAUDE_MODEL, max_tokens=num_predict,
                    messages=[{"role": "user", "content": prompt}],
                )
                return msg.content[0].text.strip()
            except Exception:
                pass
        return None

    # ═════════════════════════════════════════════════════════════════════════
    # NIVEAU 1 — FICHE D'ÉVALUATION PAR CANDIDAT
    # ═════════════════════════════════════════════════════════════════════════
    def generate_candidate_summary(
        self,
        candidate_data: Dict[str, Any],
        job_offer_data: Dict[str, Any],
        matching_scores: Dict[str, Any],
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        nom   = candidate_data.get("nom", "Candidat")
        poste = job_offer_data.get("titre", "Poste")
        score = float(matching_scores.get("hybrid", matching_scores.get("bert_score", 0)))
        pct   = round(score * 100, 1)

        # ── FAITS calculés par le code (fiables) ─────────────────────────────
        comp = float(report.get("score_competences", 0))
        exp  = float(report.get("score_experience", 0))
        edu  = float(report.get("score_formation", 0))
        dom  = float(report.get("score_domaine", 0))
        criteres = [
            {"label": "Compétences",       "note": _to_note(comp)},
            {"label": "Expérience",        "note": _to_note(exp)},
            {"label": "Formation",         "note": _to_note(edu)},
            {"label": "Adéquation domaine","note": _to_note(dom)},
        ]
        verdict, level = _verdict_from_score(pct)
        strong  = report.get("strong_points", [])
        missing = report.get("missing_skills", [])

        # ── Rédaction qualitative par l'IA ───────────────────────────────────
        ai_text = self._ai_generate(
            self._build_candidate_prompt(nom, poste, pct, verdict, strong, missing, report),
            num_predict=450,
        )

        if ai_text:
            sec = _parse_marked_sections(ai_text, ["FORCES", "VIGILANCE", "RECO"])
            points_forts     = _bullets(sec["FORCES"], 4)     or _facts_forces(strong, report)
            points_vigilance = _bullets(sec["VIGILANCE"], 3)  or _facts_vigilance(missing, report)
            recommandation   = _first_sentence_block(sec["RECO"]) or _facts_reco(level)
            source = "ollama" if self._use_ollama else "claude"
        else:
            points_forts     = _facts_forces(strong, report)
            points_vigilance = _facts_vigilance(missing, report)
            recommandation   = _facts_reco(level)
            source = "fallback"

        return {
            "type": "candidate",
            "nom": nom, "poste": poste, "score": pct,
            "verdict": verdict, "verdict_level": level,
            "criteres": criteres,
            "points_forts": points_forts,
            "points_vigilance": points_vigilance,
            "recommandation": recommandation,
            "source": source,
        }

    def _build_candidate_prompt(self, nom, poste, pct, verdict, strong, missing, report) -> str:
        strong_s  = ", ".join(strong[:5])  or "aucune compétence clé détectée"
        missing_s = ", ".join(missing[:5]) or "aucune"
        exp_txt = report.get("experience_txt", "")
        dom_txt = report.get("domaine_txt", "")
        return (
            "Tu es un consultant RH senior. À partir des données factuelles ci-dessous, "
            "rédige en FRANÇAIS une évaluation professionnelle et concise.\n"
            "Respecte EXACTEMENT ce format avec les marqueurs (pas de texte avant/après) :\n"
            "===FORCES===\n- <point fort 1>\n- <point fort 2>\n"
            "===VIGILANCE===\n- <point d'attention 1>\n- <point d'attention 2>\n"
            "===RECO===\n<une recommandation d'action en 1-2 phrases>\n\n"
            "Exemple de style attendu :\n"
            "===FORCES===\n- Maîtrise les compétences critiques du poste (Python, ML)\n"
            "- Expérience directement pertinente de 3 ans\n"
            "===VIGILANCE===\n- Compétence TensorFlow à confirmer en entretien\n"
            "===RECO===\nProfil prioritaire. Planifier un entretien technique axé sur les projets.\n\n"
            "── Données du candidat ──\n"
            f"Candidat : {nom}\nPoste : {poste}\nScore global : {pct}%\n"
            f"Verdict système : {verdict}\n"
            f"Compétences présentes : {strong_s}\n"
            f"Compétences manquantes : {missing_s}\n"
            f"{exp_txt}\n{dom_txt}\n\n"
            "Reformule de façon professionnelle (ne recopie pas la liste brute). "
            "Sois factuel, pas de superlatifs creux."
        )

    # ═════════════════════════════════════════════════════════════════════════
    # NIVEAU 2 — SYNTHÈSE EXÉCUTIVE DU MATCHING
    # ═════════════════════════════════════════════════════════════════════════
    def generate_global_summary(
        self,
        offer_data: Dict[str, Any],
        results: List[Dict[str, Any]],
        nb_postes: int = 1,
    ) -> Dict[str, Any]:
        poste = offer_data.get("titre", "Poste")
        ranked = sorted(results, key=lambda r: -float(r.get("score", 0)))
        n = len(ranked)

        # ── FAITS calculés (répartition + sélection) ─────────────────────────
        excellents = [r for r in ranked if float(r.get("score", 0)) >= 0.70]
        a_evaluer  = [r for r in ranked if 0.45 <= float(r.get("score", 0)) < 0.70]
        hors_cible = [r for r in ranked if float(r.get("score", 0)) < 0.45]

        a_recevoir = [{
            "nom": r.get("candidate_name", "Candidat"),
            "score": round(float(r.get("score", 0)) * 100),
            "raison": _candidate_one_liner(r),
        } for r in ranked[:max(nb_postes, len(excellents))][:3]]

        a_considerer = [{
            "nom": r.get("candidate_name", "Candidat"),
            "score": round(float(r.get("score", 0)) * 100),
            "raison": _candidate_one_liner(r),
        } for r in a_evaluer[:3] if r not in ranked[:len(a_recevoir)]]

        repartition = {"excellents": len(excellents), "a_evaluer": len(a_evaluer),
                       "hors_cible": len(hors_cible)}

        # ── Rédaction qualitative par l'IA ───────────────────────────────────
        ai_text = self._ai_generate(
            self._build_global_prompt(poste, n, repartition, a_recevoir, a_considerer, nb_postes),
            num_predict=400,
        )
        if ai_text:
            sec = _parse_marked_sections(ai_text, ["VUE", "RECO"])
            vue = _first_sentence_block(sec["VUE"], 400) or _facts_global_vue(n, repartition)
            reco = _first_sentence_block(sec["RECO"], 300) or _facts_global_reco(a_recevoir, nb_postes)
            source = "ollama" if self._use_ollama else "claude"
        else:
            vue  = _facts_global_vue(n, repartition)
            reco = _facts_global_reco(a_recevoir, nb_postes)
            source = "fallback"

        return {
            "type": "global",
            "poste": poste, "nb_candidats": n, "nb_postes": nb_postes,
            "repartition": repartition,
            "vue_ensemble": vue,
            "a_recevoir": a_recevoir,
            "a_considerer": a_considerer,
            "recommandation": reco,
            "source": source,
        }

    def _build_global_prompt(self, poste, n, rep, a_recevoir, a_considerer, nb_postes) -> str:
        top_s = "; ".join(f"{c['nom']} ({c['score']}%)" for c in a_recevoir) or "aucun"
        return (
            "Tu es un consultant en recrutement. Rédige en FRANÇAIS une synthèse exécutive "
            "du résultat de matching ci-dessous, pour un recruteur.\n"
            "Respecte EXACTEMENT ce format (marqueurs obligatoires, rien avant/après) :\n"
            "===VUE===\n<2-3 phrases : qualité globale du vivier de candidats>\n"
            "===RECO===\n<1-2 phrases : action concrète recommandée au recruteur>\n\n"
            "── Données du matching ──\n"
            f"Poste : {poste} ({nb_postes} à pourvoir)\n"
            f"Candidats analysés : {n}\n"
            f"Profils excellents (≥70%) : {rep['excellents']}\n"
            f"Profils à évaluer (45-70%) : {rep['a_evaluer']}\n"
            f"Profils hors cible (<45%) : {rep['hors_cible']}\n"
            f"Meilleurs profils : {top_s}\n\n"
            "Sois factuel et orienté décision. Pas de superlatifs creux."
        )

    # Compat : ancien nom d'appel
    def generate_summary(self, *a, **k):
        return self.generate_candidate_summary(*a, **k)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de calcul (FAITS — déterministes)
# ─────────────────────────────────────────────────────────────────────────────
def _to_note(pct: float) -> int:
    """Score en % (0-100) → note sur 10."""
    return max(0, min(10, round(pct / 10)))


def _verdict_from_score(pct: float):
    if pct >= 70: return "Recommandé pour entretien", "recommande"
    if pct >= 50: return "À évaluer", "a_evaluer"
    if pct >= 35: return "Profil partiel", "partiel"
    return "Non retenu", "non_retenu"


def _candidate_one_liner(r: Dict[str, Any]) -> str:
    det = r.get("bert_details", r.get("details", {})) or {}
    matched = det.get("skills_matched", [])
    names = [m.get("skill") if isinstance(m, dict) else m for m in matched][:2]
    if names:
        return "maîtrise " + ", ".join(names)
    return "profil à examiner"


def _facts_forces(strong: List[str], report: Dict) -> List[str]:
    out = []
    if strong:
        out.append("Compétences en adéquation : " + ", ".join(strong[:3]))
    if report.get("experience_match"):
        out.append("Expérience conforme aux exigences du poste")
    if report.get("education_match"):
        out.append("Niveau de formation adéquat")
    return out or ["Quelques éléments de profil pertinents identifiés"]


def _facts_vigilance(missing: List[str], report: Dict) -> List[str]:
    out = []
    if missing:
        out.append("Compétences à confirmer : " + ", ".join(missing[:3]))
    if not report.get("experience_match"):
        out.append("Expérience en deçà des attentes du poste")
    return out or ["Aucun point bloquant majeur identifié"]


def _facts_reco(level: str) -> str:
    return {
        "recommande":  "Profil prioritaire — planifier un entretien.",
        "a_evaluer":   "Profil à évaluer en seconde intention selon le vivier.",
        "partiel":     "Profil partiel — entretien uniquement si peu de candidats.",
        "non_retenu":  "Ne correspond pas aux critères — écarter.",
    }.get(level, "À examiner par le recruteur.")


def _facts_global_vue(n: int, rep: Dict) -> str:
    return (f"{n} candidats analysés. Le vivier comprend {rep['excellents']} profil(s) "
            f"excellent(s), {rep['a_evaluer']} à évaluer et {rep['hors_cible']} hors cible.")


def _facts_global_reco(a_recevoir: List[Dict], nb_postes: int) -> str:
    if not a_recevoir:
        return "Aucun profil ne se démarque — élargir le sourcing est recommandé."
    noms = ", ".join(c["nom"] for c in a_recevoir[:nb_postes])
    return f"Recevoir en priorité : {noms}. Élargir le vivier si besoin de profils supplémentaires."
