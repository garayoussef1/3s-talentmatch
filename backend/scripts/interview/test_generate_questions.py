"""
Test standalone — Génération de 15 questions d'entretien via Groq.

Usage :
    cd backend
    python -m scripts.interview.test_generate_questions

Prérequis :
    pip install groq python-dotenv
    GROQ_API_KEY=gsk_xxxxx dans backend/.env
"""

import sys
from pathlib import Path

# Assure que le backend est dans le path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.interview.groq_interview_service import (
    CVSummary,
    OfferSummary,
    GroqInterviewService,
)

# ─────────────────────────────────────────────
# Données de test (faux CVs + fausses offres)
# ─────────────────────────────────────────────

SCENARIOS = [
    {
        "label": "IT / Développement — Backend Python",
        "cv": CVSummary(
            nom="Youssef Garraya",
            email="youssef@example.com",
            competences=["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "Redis", "SQLAlchemy"],
            experiences=[
                "Développeur Backend chez StartupTech (2 ans)",
                "Stagiaire Python chez DataCorp (6 mois)",
            ],
            formations=[
                "Ingénieur Informatique — INSAT Tunis (2024)",
            ],
        ),
        "offer": OfferSummary(
            titre="Développeur Backend Python Senior",
            domaine_metier="IT / Développement",
            type_contrat="CDI",
            competences_requises=["Python", "FastAPI", "PostgreSQL", "Docker"],
            competences_appreciees=["Redis", "Kubernetes", "CI/CD"],
            description="Rejoignez une équipe produit pour concevoir et maintenir des APIs REST haute performance.",
            niveau_seniorite="Senior (5+ ans)",
        ),
    },
    {
        "label": "Data / IA — Data Scientist ML",
        "cv": CVSummary(
            nom="Sarra Ben Ali",
            email="sarra@example.com",
            competences=["Python", "Scikit-learn", "PyTorch", "Pandas", "MLflow", "SQL", "Hugging Face"],
            experiences=[
                "Data Scientist chez Banque Centrale (3 ans)",
                "Analyste Data chez ConsultingGroup (1 an)",
            ],
            formations=[
                "Master Machine Learning — Université Paris-Saclay (2021)",
                "Licence Mathématiques — FST Tunis (2019)",
            ],
        ),
        "offer": OfferSummary(
            titre="Data Scientist NLP / LLM",
            domaine_metier="Data / IA",
            type_contrat="CDI",
            competences_requises=["Python", "PyTorch", "Hugging Face", "NLP"],
            competences_appreciees=["LangChain", "RAG", "fine-tuning LLM", "MLflow"],
            description="Développement de pipelines NLP et fine-tuning de LLMs pour des cas d'usage métier.",
            niveau_seniorite="Confirmé (3-5 ans)",
        ),
    },
    {
        "label": "Finance / Comptabilité — Contrôleur de gestion",
        "cv": CVSummary(
            nom="Ahmed Trabelsi",
            email="ahmed@example.com",
            competences=["Excel", "SAP", "Contrôle de gestion", "Reporting", "Budget", "IFRS"],
            experiences=[
                "Contrôleur de gestion chez Groupe Industriel TN (4 ans)",
                "Auditeur junior chez Cabinet PWC (2 ans)",
            ],
            formations=[
                "Master CCA (Comptabilité Contrôle Audit) — IHEC Carthage (2020)",
            ],
        ),
        "offer": OfferSummary(
            titre="Responsable Contrôle de Gestion",
            domaine_metier="Finance / Comptabilité",
            type_contrat="CDI",
            competences_requises=["Contrôle de gestion", "SAP", "Reporting", "Budget"],
            competences_appreciees=["Power BI", "IFRS", "consolidation"],
            description="Piloter le budget annuel et produire des reportings mensuels pour la direction.",
            niveau_seniorite="Manager (6+ ans)",
        ),
    },
]

PHASE_LABELS = {
    "validation_profil": "PHASE 1 — Validation du profil",
    "technique":         "PHASE 2 — Questions techniques",
    "mise_en_situation": "PHASE 3 — Mise en situation",
    "soft_skill":        "PHASE 4 — Soft skills (STAR)",
    "motivation":        "PHASE 5 — Motivation & culture fit",
    "cloture":           "PHASE 6 — Clôture",
}


def print_questions(questions: list[dict], scenario_label: str) -> None:
    print(f"\n{'═' * 70}")
    print(f"  SCÉNARIO : {scenario_label}")
    print(f"  {len(questions)} questions générées")
    print(f"{'═' * 70}")

    current_phase = None
    for q in questions:
        phase = q.get("phase", "inconnu")
        if phase != current_phase:
            current_phase = phase
            print(f"\n  ── {PHASE_LABELS.get(phase, phase.upper())} ──")

        idx = q.get("index", "?")
        question_text = q.get("question", "N/A")
        skill = q.get("skill_targeted", "N/A")
        cv_ref = q.get("cv_reference", "N/A")
        hint = q.get("context_hint", "")
        greens = q.get("green_flag_keywords", [])
        reds = q.get("red_flag_indicators", [])

        print(f"\n  Q{idx}. {question_text}")
        print(f"       Compétence ciblée : {skill}")
        print(f"       Référence CV      : {cv_ref}")
        if hint:
            print(f"       💡 Conseil candidat : {hint}")
        if greens:
            print(f"       ✅ Green flags attendus : {', '.join(greens[:3])}")
        if reds:
            print(f"       🚩 Red flags à surveiller : {', '.join(reds[:2])}")

    print()


def main() -> None:
    print("\n🚀  Test génération questions — GroqInterviewService")
    print("    Initialisation du service Groq...")

    service = GroqInterviewService()

    # Tester un seul scénario ou tous ? (modifier l'index pour isoler)
    scenarios_to_run = SCENARIOS  # ou SCENARIOS[:1] pour le premier seulement

    for scenario in scenarios_to_run:
        print(f"\n⏳  Appel Groq pour : {scenario['label']} ...")
        try:
            questions = service.generate_questions(
                cv=scenario["cv"],
                offer=scenario["offer"],
            )
            print_questions(questions, scenario["label"])

        except Exception as exc:
            print(f"\n❌  Erreur lors du scénario '{scenario['label']}' : {exc}")
            import traceback
            traceback.print_exc()

    print("\n✅  Tests terminés.")
    print("    Si les questions sont pertinentes et domaine-spécifiques → intégration FastAPI possible.\n")


if __name__ == "__main__":
    main()
