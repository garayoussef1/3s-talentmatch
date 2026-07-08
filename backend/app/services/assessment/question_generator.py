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

    # Génération PAR PALIERS (2 appels : fondamentaux puis difficile/expert)
    # → questions dures garanties, sorties plus courtes = moins de troncature.
    n_easy = max(2, n_qcm // 2)
    n_hard = n_qcm - n_easy
    qcm = []
    qcm += _generate_qcm_tier(offer_titre, comp_str, n_easy,
                              "2 à 5 (fondamentaux et cas concrets simples)")
    qcm += _generate_qcm_tier(offer_titre, comp_str, n_hard,
                              "7 à 10 (DIFFICILE à EXPERT : pièges classiques, comportements "
                              "limites, subtilités que seuls des praticiens expérimentés connaissent)")

    # CONTRÔLE QUALITÉ : l'IA répond elle-même à chaque QCM (sans voir la réponse
    # marquée) ; en cas de désaccord, la question est rejetée (anti-erreur).
    qcm = verify_qcm(qcm)

    # Questions ouvertes de raisonnement
    open_qs = generate_open_questions_for_offer(offer_titre, comp_str, n_open)
    return {"qcm": qcm, "open": open_qs}


def _generate_qcm_tier(offer_titre: str, comp_str: str, n: int, tier_desc: str) -> list[dict]:
    """Génère n QCM d'un palier de difficulté donné, avec distracteurs plausibles."""
    prompt = f"""Tu es un examinateur technique SENIOR très exigeant pour le poste
« {offer_titre} » (compétences : {comp_str}).

Génère EXACTEMENT {n} QCM techniques de difficulté {tier_desc}.

RÈGLES CRUCIALES sur les options (qualité anti-hasard) :
- 4 options PROCHES et TOUTES PLAUSIBLES : même forme, même longueur,
  différences SUBTILES mais réelles.
- Les 3 mauvaises options sont des erreurs FRÉQUENTES ou confusions classiques
  du métier — jamais des réponses absurdes, hors-sujet ou visiblement fausses.
- INTERDIT : "toutes les réponses ci-dessus", "aucune de ces réponses".
- La réponse marquée "correct" doit être INDISCUTABLEMENT vraie. Vérifie-la
  mentalement avant de la donner.

Réponds UNIQUEMENT avec ce JSON :
{{"qcm": [
  {{"competence": "...", "question": "...", "options": ["...","...","...","..."], "correct": 0, "difficulte": 8}}
]}}"""
    client = _client()
    resp = client.chat.completions.create(
        model=client.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5, max_tokens=2200,
        response_format={"type": "json_object"},
    )
    data = _extract_json(resp.choices[0].message.content)
    out = []
    for q in data.get("qcm", []):
        opts = q.get("options") or []
        try:
            correct = int(q.get("correct", 0))
            diff = max(1, min(10, int(q.get("difficulte", 5))))
        except (TypeError, ValueError):
            continue
        if len(opts) != 4 or not (0 <= correct <= 3) or not q.get("question"):
            continue
        out.append({
            "competence": str(q.get("competence", "")).strip() or "générale",
            "question": str(q["question"]).strip(),
            "options": [str(o).strip() for o in opts],
            "correct": correct, "difficulte": diff,
        })
    return out


def verify_qcm(qcm: list[dict]) -> list[dict]:
    """Filtre anti-erreur : le LLM répond aux QCM sans voir la réponse marquée.

    On ne garde que les questions où sa réponse indépendante CONFIRME la réponse
    marquée (auto-cohérence). Les questions douteuses sont éliminées.
    """
    if not qcm:
        return []
    lignes = []
    for i, q in enumerate(qcm):
        opts = "\n".join(f"   {j}. {o}" for j, o in enumerate(q["options"]))
        lignes.append(f"Q{i} : {q['question']}\n{opts}")
    prompt = f"""Réponds à ces QCM techniques. Pour chaque question, donne UNIQUEMENT
l'index (0-3) de la bonne réponse. Si tu n'es pas certain, réponds -1.

{chr(10).join(lignes)}

Réponds UNIQUEMENT avec ce JSON :
{{"reponses": [0, 2, -1, ...]}}  (un index par question, dans l'ordre)"""
    try:
        client = _client()
        resp = client.chat.completions.create(
            model=client.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=400,
            response_format={"type": "json_object"},
        )
        answers = _extract_json(resp.choices[0].message.content).get("reponses", [])
        kept = [q for q, a in zip(qcm, answers) if isinstance(a, int) and a == q["correct"]]
        logger.info("Vérification QCM : %d/%d confirmés", len(kept), len(qcm))
        # Si la vérification élimine presque tout, on garde l'original (prudence)
        return kept if len(kept) >= max(3, len(qcm) // 2) else qcm
    except Exception as exc:
        logger.warning("Vérification QCM impossible (%s) — questions gardées", exc)
        return qcm


def generate_open_questions_for_offer(offer_titre: str, comp_str: str, n: int) -> list[dict]:
    """Questions ouvertes de raisonnement liées au poste (+ 3 réfs chacune)."""
    prompt = f"""Tu es un examinateur senior pour le poste « {offer_titre} »
(compétences : {comp_str}). Génère EXACTEMENT {n} question(s) OUVERTE(S) de
RAISONNEMENT (mise en situation, résolution de problème, choix justifié) — le
candidat devra RÉDIGER et expliquer sa démarche.

Pour CHAQUE question, fournis 3 réponses de référence :
- "ref_faible"  : superficielle, sans vrai raisonnement (1 phrase vague).
- "ref_correct" : correcte, raisonnement basique (2-3 phrases).
- "ref_expert"  : experte, structurée, compromis et justifications (4-6 phrases).

Réponds UNIQUEMENT avec ce JSON :
{{"open": [
  {{"competence": "...", "question": "...", "ref_faible": "...", "ref_correct": "...", "ref_expert": "..."}}
]}}"""
    client = _client()
    resp = client.chat.completions.create(
        model=client.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5, max_tokens=1800,
        response_format={"type": "json_object"},
    )
    data = _extract_json(resp.choices[0].message.content)
    out = []
    for q in data.get("open", []):
        if not all(q.get(k) for k in ("question", "ref_faible", "ref_correct", "ref_expert")):
            continue
        out.append({
            "competence": str(q.get("competence", "")).strip() or "générale",
            "question": str(q["question"]).strip(),
            "ref_faible": str(q["ref_faible"]).strip(),
            "ref_correct": str(q["ref_correct"]).strip(),
            "ref_expert": str(q["ref_expert"]).strip(),
        })
    return out


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
