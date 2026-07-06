"""
Rapport d'évaluation généré par IA LOCALE (Ollama).

Synthétise en un rapport écrit pour le recruteur :
  • le niveau technique démontré (QCM adaptatif, par compétence),
  • la QUALITÉ DU RAISONNEMENT (réponses ouvertes notées sémantiquement),
  • l'écart CV déclaré vs démontré (Reality Gap),
et rend un verdict actionnable.

100% local : le LLM tourne sur la machine (Ollama). On ne lui transmet que des
résultats d'évaluation et les réponses écrites du candidat (aucune fuite externe).
"""
from __future__ import annotations

import json
import logging

from app.services.interview.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip() if raw.lower().startswith("json") else raw
    a, b = raw.find("{"), raw.rfind("}")
    if a != -1 and b != -1:
        raw = raw[a:b + 1]
    return json.loads(raw)


def generate_report(candidate_name: str, offer_titre: str,
                    competence_scores: dict, open_answers: list[dict],
                    reality_gap: dict | None) -> dict:
    """Génère un rapport d'évaluation structuré (JSON) via Ollama."""
    # Bloc niveaux techniques
    niveaux = "\n".join(f"  - {c} : {v}/10" for c, v in (competence_scores or {}).items()) or "  (aucun)"

    # Bloc réponses ouvertes (raisonnement)
    qr = []
    for oa in (open_answers or []):
        qr.append(
            f"  • [{oa.get('competence','?')}] Q: {oa.get('question','')[:160]}\n"
            f"    Réponse (score {oa.get('score','?')}/100) : {oa.get('answer','')[:300]}"
        )
    qr_block = "\n".join(qr) or "  (aucune réponse ouverte)"

    # Bloc écart CV
    if reality_gap:
        gap_block = (
            f"  reality_gap_score={reality_gap.get('reality_gap_score')} | "
            f"fiabilité_cv={reality_gap.get('fiabilite_cv')}/100 | "
            f"verdict={reality_gap.get('niveau_label')}\n"
            + "\n".join(
                f"    - {d['competence']}: déclaré {d['niveau_declare']} vs démontré {d['niveau_demontre']}"
                for d in (reality_gap.get("details") or [])
            )
        )
    else:
        gap_block = "  (non calculé)"

    prompt = f"""Tu es un consultant technique senior. Rédige un rapport d'évaluation
FACTUEL et actionnable pour un recruteur, à partir des résultats ci-dessous.

CANDIDAT : {candidate_name}
POSTE : {offer_titre}

NIVEAU TECHNIQUE DÉMONTRÉ (test adaptatif, /10) :
{niveaux}

RÉPONSES OUVERTES (raisonnement, notées /100) :
{qr_block}

ÉCART CV DÉCLARÉ vs DÉMONTRÉ (Reality Gap) :
{gap_block}

Analyse la maîtrise technique ET la qualité du raisonnement. Signale les écarts
importants entre le CV et le niveau réellement démontré. Sois factuel.

Réponds UNIQUEMENT avec ce JSON :
{{
  "synthese": "Résumé exécutif en 3-4 phrases",
  "niveau_technique": "Faible|Moyen|Bon|Excellent",
  "qualite_raisonnement": "Faible|Moyenne|Bonne|Excellente",
  "points_forts": ["...", "..."],
  "points_faibles": ["...", "..."],
  "coherence_cv": "Commentaire sur l'écart CV vs démontré",
  "recommandation": "RECRUTER|A_APPROFONDIR|REJETER",
  "justification": "Justification en 2 phrases"
}}"""

    client = get_llm_client(prefer="ollama")
    resp = client.chat.completions.create(
        model=client.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return _extract_json(resp.choices[0].message.content)
