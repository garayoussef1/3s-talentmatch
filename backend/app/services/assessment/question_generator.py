"""
Générateur DYNAMIQUE de questions d'évaluation (via LLM local Ollama).

Objectif : ne PAS dépendre d'une banque figée. Pour n'importe quelle compétence
d'une offre/CV, on génère à la volée :
  • des QCM de difficulté variée (test adaptatif IRT)
  • des questions ouvertes + 3 réponses de référence (scoring sémantique BGE-M3)

CONFIDENTIALITÉ : on n'envoie au LLM QUE le nom de la compétence (information
publique) — jamais le CV ni les données candidat. Le LLM tourne en local (Ollama).

Les questions générées sont mises en CACHE en base (assessment_questions,
open_questions) → générées une fois, réutilisées ensuite.
"""
from __future__ import annotations

import json
import logging

from app.services.interview.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# On force Ollama (100% local) pour la génération.
_PREFER = "ollama"


def _client():
    return get_llm_client(prefer=_PREFER)


def _extract_json(raw: str) -> dict:
    """Parse le JSON renvoyé par le LLM (tolérant aux ``` et texte autour)."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw.strip("`")
        raw = raw.replace("json", "", 1).strip() if raw.lower().startswith("json") else raw
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Génération PAR ENTRETIEN (offre + CV) — questions uniques à chaque session
# ─────────────────────────────────────────────────────────────────────────────
def generate_session_questions(offer_titre: str, competences: list[str],
                               cv_resume: str, n_qcm: int = 10, n_open: int = 3) -> dict:
    """Génère en UN appel le questionnaire complet d'un entretien.

    Intelligent : ciblé sur le POSTE (offre) et adapté au PROFIL (résumé CV
    anonymisé : compétences + expériences, PAS de données personnelles).
    Chaque session reçoit des questions fraîches (pas de banque partagée).

    Retourne {"qcm": [...], "open": [...]}.
    """
    comp_str = ", ".join(competences[:8]) or "les compétences du poste"
    prompt = f"""Tu es un examinateur technique senior qui prépare un entretien
d'évaluation pour le poste « {offer_titre} ».

COMPÉTENCES CLÉS DU POSTE : {comp_str}

PROFIL DU CANDIDAT (résumé) :
{cv_resume[:900]}

Génère un questionnaire ADAPTÉ à ce poste et à ce profil :

1) EXACTEMENT {n_qcm} QCM techniques sur les compétences clés du poste,
   difficulté croissante (échelle 1-10 répartie), 4 options dont UNE correcte.
   Les questions testent la compréhension réelle (pas de la culture générale).

2) EXACTEMENT {n_open} questions OUVERTES de RAISONNEMENT (mise en situation,
   résolution de problème, choix justifié) liées au poste — le candidat devra
   RÉDIGER et expliquer sa démarche. Pour chacune, fournis 3 réponses de
   référence : "ref_faible" (vague), "ref_correct" (basique), "ref_expert"
   (structurée, compromis, vocabulaire précis).

Réponds UNIQUEMENT avec ce JSON :
{{"qcm": [
  {{"competence": "...", "question": "...", "options": ["...","...","...","..."], "correct": 0, "difficulte": 3}}
],
"open": [
  {{"competence": "...", "question": "...", "ref_faible": "...", "ref_correct": "...", "ref_expert": "..."}}
]}}"""

    client = _client()
    resp = client.chat.completions.create(
        model=client.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,   # un peu de variété entre sessions
        max_tokens=3500,
        response_format={"type": "json_object"},
    )
    data = _extract_json(resp.choices[0].message.content)

    qcm = []
    for q in data.get("qcm", []):
        opts = q.get("options") or []
        try:
            correct = int(q.get("correct", 0))
            diff = max(1, min(10, int(q.get("difficulte", 5))))
        except (TypeError, ValueError):
            continue
        if len(opts) != 4 or not (0 <= correct <= 3) or not q.get("question"):
            continue
        qcm.append({
            "competence": str(q.get("competence", "")).strip() or "générale",
            "question": str(q["question"]).strip(),
            "options": [str(o).strip() for o in opts],
            "correct": correct,
            "difficulte": diff,
        })

    open_qs = []
    for q in data.get("open", []):
        if not all(q.get(k) for k in ("question", "ref_faible", "ref_correct", "ref_expert")):
            continue
        open_qs.append({
            "competence": str(q.get("competence", "")).strip() or "générale",
            "question": str(q["question"]).strip(),
            "ref_faible": str(q["ref_faible"]).strip(),
            "ref_correct": str(q["ref_correct"]).strip(),
            "ref_expert": str(q["ref_expert"]).strip(),
        })

    return {"qcm": qcm, "open": open_qs}


# ─────────────────────────────────────────────────────────────────────────────
# Génération de QCM (Module 1)
# ─────────────────────────────────────────────────────────────────────────────
def generate_qcm(competence: str, n: int = 6) -> list[dict]:
    """Génère n QCM techniques sur `competence`, difficulté croissante 1-10.

    Retourne : [{question, options[4], correct(index 0-3), difficulte(1-10)}].
    """
    prompt = f"""Tu es un examinateur technique. Génère EXACTEMENT {n} questions à choix
multiple (QCM) pour évaluer la compétence « {competence} », de difficulté CROISSANTE
(de facile à très difficile, échelle 1-10 répartie).

Règles STRICTES :
- Chaque question a EXACTEMENT 4 options, une seule correcte.
- Les questions doivent tester une vraie compréhension (pas de culture générale).
- "correct" = index (0 à 3) de la bonne option.
- "difficulte" = entier 1-10.

Réponds UNIQUEMENT avec ce JSON :
{{"questions": [
  {{"question": "...", "options": ["...","...","...","..."], "correct": 0, "difficulte": 2}}
]}}"""

    client = _client()
    resp = client.chat.completions.create(
        model=client.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    data = _extract_json(resp.choices[0].message.content)
    out = []
    for q in data.get("questions", []):
        opts = q.get("options") or []
        if len(opts) != 4:
            continue
        try:
            correct = int(q.get("correct", 0))
            diff = max(1, min(10, int(q.get("difficulte", 5))))
        except (TypeError, ValueError):
            continue
        if not (0 <= correct <= 3) or not q.get("question"):
            continue
        out.append({
            "question": str(q["question"]).strip(),
            "options": [str(o).strip() for o in opts],
            "correct": correct,
            "difficulte": diff,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Génération de questions ouvertes (Module 2)
# ─────────────────────────────────────────────────────────────────────────────
def generate_open_questions(competence: str, n: int = 1) -> list[dict]:
    """Génère n questions ouvertes de RAISONNEMENT + 3 réponses de référence.

    On privilégie des questions qui révèlent la FAÇON DE PENSER du candidat
    (mise en situation, résolution de problème, analyse), pas de simples
    définitions — pour un vrai entretien technique.
    """
    prompt = f"""Tu es un examinateur senior qui mène un entretien technique sur
la compétence « {competence} ». Génère EXACTEMENT {n} question(s) OUVERTE(S) de
RAISONNEMENT, qui obligent le candidat à EXPLIQUER sa démarche (pas une définition).

Varie les styles selon la question :
- Mise en situation : « Vous devez… comment vous y prenez-vous et pourquoi ? »
- Résolution de problème : « Face à [problème concret], quelle est votre approche ? »
- Analyse critique : « Quels sont les compromis / risques de… ? »
- Choix justifié : « Entre A et B, que choisissez-vous et pourquoi ? »

Pour CHAQUE question, fournis 3 réponses de référence de qualité croissante :
- "ref_faible"  : réponse superficielle, sans vrai raisonnement (1 phrase vague).
- "ref_correct" : réponse correcte avec un raisonnement basique (2-3 phrases).
- "ref_expert"  : réponse experte, raisonnement structuré, compromis et justifications
                  (4-6 phrases, vocabulaire technique précis).

Réponds UNIQUEMENT avec ce JSON :
{{"questions": [
  {{"question": "...", "ref_faible": "...", "ref_correct": "...", "ref_expert": "..."}}
]}}"""

    client = _client()
    resp = client.chat.completions.create(
        model=client.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    data = _extract_json(resp.choices[0].message.content)
    out = []
    for q in data.get("questions", []):
        if not all(q.get(k) for k in ("question", "ref_faible", "ref_correct", "ref_expert")):
            continue
        out.append({
            "question": str(q["question"]).strip(),
            "ref_faible": str(q["ref_faible"]).strip(),
            "ref_correct": str(q["ref_correct"]).strip(),
            "ref_expert": str(q["ref_expert"]).strip(),
        })
    return out
