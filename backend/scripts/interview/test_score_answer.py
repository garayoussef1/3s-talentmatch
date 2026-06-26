"""
Test standalone — Scoring de réponses d'entretien via Groq.

Usage :
    cd backend
    python -m scripts.interview.test_score_answer

Prérequis :
    pip install groq python-dotenv
    GROQ_API_KEY=gsk_xxxxx dans backend/.env
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.interview.groq_interview_service import (
    CVSummary,
    GroqInterviewService,
)

# ─────────────────────────────────────────────
# CV fictif commun aux tests
# ─────────────────────────────────────────────
CV = CVSummary(
    nom="Youssef Garraya",
    email="youssef@example.com",
    competences=["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "Git"],
    experiences=[
        "Développeur Backend chez StartupTech (2 ans)",
        "Stagiaire Python chez DataCorp (6 mois)",
    ],
    formations=["Ingénieur Informatique — INSAT Tunis (2024)"],
)

# ─────────────────────────────────────────────
# Question de référence
# ─────────────────────────────────────────────
QUESTION = {
    "index": 3,
    "phase": "technique",
    "question": (
        "Chez StartupTech, vous avez utilisé FastAPI et PostgreSQL. "
        "Décrivez comment vous avez conçu une API REST performante avec gestion de la concurrence "
        "et expliquez les choix d'architecture que vous avez faits."
    ),
    "skill_targeted": "Développement d'API REST / Architecture backend",
    "cv_reference": "Développeur Backend chez StartupTech (2 ans) — FastAPI, PostgreSQL",
    "context_hint": "Appuyez-vous sur un projet concret avec des métriques si possible.",
    "green_flag_keywords": [
        "async/await", "connection pooling", "index", "middleware",
        "load testing", "pagination", "rate limiting",
    ],
    "red_flag_indicators": [
        "Réponse trop théorique sans exemple concret",
        "Confusion entre FastAPI et Flask",
        "Pas de mention de la gestion des erreurs",
    ],
}

# ─────────────────────────────────────────────
# 4 niveaux de réponses à scorer
# ─────────────────────────────────────────────
ANSWERS = [
    {
        "label": "RÉPONSE EXCELLENTE — Experte avec métriques",
        "text": (
            "Chez StartupTech, j'ai conçu une API de traitement de commandes gérant 2000 req/s "
            "en pic. J'ai utilisé FastAPI avec async/await pour les handlers, SQLAlchemy AsyncSession "
            "avec un pool de 20 connexions PostgreSQL, et Redis pour le cache des référentiels produits "
            "(TTL 5min). J'ai mis en place du rate limiting via SlowAPI, une pagination curseur pour "
            "les listes longues, et des index B-tree sur les colonnes de filtre fréquent. "
            "Les tests de charge avec Locust ont validé une latence P99 < 120ms sous 500 utilisateurs concurrents."
        ),
    },
    {
        "label": "RÉPONSE BONNE — Structurée mais sans chiffres",
        "text": (
            "Sur le projet FastAPI chez StartupTech, j'ai utilisé des routes async pour ne pas "
            "bloquer le serveur. J'ai configuré un pool de connexions SQLAlchemy et mis du cache Redis "
            "pour les données qui ne changent pas souvent. J'ai aussi ajouté une pagination sur les "
            "endpoints qui retournent beaucoup de données. La gestion des erreurs se fait avec des "
            "HTTPException et des middleware personnalisés."
        ),
    },
    {
        "label": "RÉPONSE MOYENNE — Vague et générique",
        "text": (
            "J'ai fait des APIs avec FastAPI et PostgreSQL pendant mon expérience. "
            "En général, pour les performances, il faut bien indexer la base de données "
            "et éviter les requêtes N+1. J'utilisais des bonnes pratiques comme la séparation "
            "des concerns et je documentais bien mon code."
        ),
    },
    {
        "label": "RÉPONSE MAUVAISE — Hors sujet / incohérente",
        "text": (
            "Je connais FastAPI, j'en ai entendu parler. En général pour les APIs on utilise REST "
            "avec des GET et POST. La concurrence c'est quand plusieurs utilisateurs utilisent l'API "
            "en même temps, ce qui peut poser des problèmes. Je pense que Docker aide pour ça."
        ),
    },
]


def print_score_result(answer_label: str, answer_text: str, result: dict) -> None:
    print(f"\n{'─' * 65}")
    print(f"  {answer_label}")
    print(f"{'─' * 65}")
    print(f"  Réponse : \"{answer_text[:120]}...\"")

    scores = result.get("scores", {})
    justifs = result.get("scores_justifications", {})
    flags = result.get("flags", {})
    contradiction = result.get("cv_contradiction", False)

    score_global = round(
        scores.get("technique",     0) * 0.40 +
        scores.get("star",          0) * 0.20 +
        scores.get("coherence",     0) * 0.15 +
        scores.get("specificite",   0) * 0.15 +
        scores.get("communication", 0) * 0.10,
        1,
    )

    print(f"\n  SCORES (pondéré global : {score_global}/10) :")
    dims = [
        ("technique",     "Technique     (40%)"),
        ("star",          "STAR          (20%)"),
        ("coherence",     "Cohérence CV  (15%)"),
        ("specificite",   "Spécificité   (15%)"),
        ("communication", "Communication (10%)"),
    ]
    for key, label in dims:
        bar_val = int(scores.get(key, 0))
        bar = "█" * bar_val + "░" * (10 - bar_val)
        justif = justifs.get(key, "")
        print(f"    {label} : {bar} {scores.get(key, 0)}/10")
        if justif:
            print(f"      → {justif}")

    if flags.get("green"):
        print(f"\n  ✅ Green flags : {', '.join(flags['green'][:3])}")
    if flags.get("yellow"):
        print(f"  🟡 Yellow flags : {', '.join(flags['yellow'][:2])}")
    if flags.get("red"):
        print(f"  🚩 Red flags : {', '.join(flags['red'][:2])}")

    if contradiction:
        detail = result.get("contradiction_detail", "")
        print(f"\n  ⚠️  CONTRADICTION CV détectée : {detail}")

    print()


def main() -> None:
    print("\n🚀  Test scoring réponses — GroqInterviewService")
    print(f"    Question : {QUESTION['question'][:100]}...")
    print(f"    Domaine  : IT / Développement\n")

    service = GroqInterviewService()

    for answer_data in ANSWERS:
        print(f"⏳  Scoring de : {answer_data['label']} ...")
        try:
            result = service.score_answer(
                question=QUESTION,
                answer=answer_data["text"],
                cv=CV,
                domaine_metier="IT / Développement",
            )
            print_score_result(answer_data["label"], answer_data["text"], result)

        except Exception as exc:
            print(f"\n❌  Erreur : {exc}")
            import traceback
            traceback.print_exc()

    print("✅  Tests de scoring terminés.")
    print("    Vérifiez que les scores décroissent bien : Excellente > Bonne > Moyenne > Mauvaise.\n")


if __name__ == "__main__":
    main()
