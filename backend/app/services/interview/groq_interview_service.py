"""
Service Groq pour le système d'entretien IA.
Fichier STANDALONE — peut être testé sans FastAPI ni PostgreSQL.

Dépendances :
    pip install groq python-dotenv

Usage direct :
    python groq_interview_service.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Charger .env depuis la racine du backend
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

# Import du profil de domaine + client LLM unifié.
# (chemin relatif si standalone, absolu si intégré)
try:
    from app.services.interview.domain_profiles import get_profile
    from app.services.interview.llm_client import get_llm_client
except ImportError:
    # Fallback standalone : ajoute le path backend au sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from app.services.interview.domain_profiles import get_profile
    from app.services.interview.llm_client import get_llm_client


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    print(
        "⚠️   GROQ_API_KEY manquante.\n"
        "    Ajoute dans backend/.env : GROQ_API_KEY=gsk_xxxxx\n"
        "    Clé gratuite sur : https://console.groq.com/keys",
        file=sys.stderr,
    )


# ─────────────────────────────────────────────
# Structures de données légères (sans SQLAlchemy)
# ─────────────────────────────────────────────
@dataclass
class CVSummary:
    """Résumé du CV du candidat injecté dans les prompts."""
    nom:          str
    competences:  list[str] = field(default_factory=list)
    experiences:  list[str] = field(default_factory=list)  # ["Poste chez Entreprise (2 ans)"]
    formations:   list[str] = field(default_factory=list)  # ["Diplôme — Établissement (année)"]
    email:        str = ""

    @classmethod
    def from_parsed_data(cls, nom: str, email: str, parsed_data: dict) -> "CVSummary":
        """Construit depuis le parsed_data d'un Candidate ORM."""
        raw_skills = parsed_data.get("competences", [])
        skills = []
        for s in raw_skills[:12]:
            if isinstance(s, dict):
                name = s.get("name") or s.get("skill") or s.get("label") or ""
            else:
                name = str(s)
            if name.strip():
                skills.append(name.strip())

        exps = parsed_data.get("experiences", [])
        exp_summary = [
            f"{e.get('poste', '?')} chez {e.get('entreprise', '?')} "
            f"({e.get('duree', e.get('date_fin', '?'))})"
            for e in exps[:4]
        ]

        forms = parsed_data.get("formations", [])
        form_summary = [
            f"{f.get('diplome', '?')} — {f.get('etablissement', '?')} ({f.get('annee', '?')})"
            for f in forms[:3]
        ]

        return cls(
            nom=nom or "Candidat",
            email=email or "",
            competences=skills,
            experiences=exp_summary,
            formations=form_summary,
        )

    def to_prompt_block(self) -> str:
        lines = [
            f"Nom : {self.nom}",
            f"Compétences déclarées : {', '.join(self.competences) or 'Non précisées'}",
            f"Expériences professionnelles :",
        ]
        for exp in self.experiences:
            lines.append(f"  • {exp}")
        lines.append("Formation :")
        for f in self.formations:
            lines.append(f"  • {f}")
        return "\n".join(lines)


@dataclass
class OfferSummary:
    """Résumé de l'offre d'emploi."""
    titre:                   str
    domaine_metier:          str = "IT / Développement"
    type_contrat:            str = "CDI"
    competences_requises:    list[str] = field(default_factory=list)
    competences_appreciees:  list[str] = field(default_factory=list)
    description:             str = ""
    niveau_seniorite:        str = ""

    def to_prompt_block(self) -> str:
        lines = [
            f"Titre : {self.titre}",
            f"Contrat : {self.type_contrat}",
            f"Domaine : {self.domaine_metier}",
        ]
        if self.niveau_seniorite:
            lines.append(f"Séniorité attendue : {self.niveau_seniorite}")
        if self.competences_requises:
            lines.append(f"Compétences REQUISES : {', '.join(self.competences_requises)}")
        if self.competences_appreciees:
            lines.append(f"Compétences APPRÉCIÉES : {', '.join(self.competences_appreciees)}")
        if self.description:
            lines.append(f"Description (extrait) : {self.description[:300]}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
# Service principal
# ─────────────────────────────────────────────
class GroqInterviewService:
    """
    Service standalone de génération et scoring d'entretien via Groq API.

    Méthodes principales :
        generate_questions(cv, offer) → list[dict]  (15 questions JSON)
        score_answer(question, answer, cv) → dict    (scores + flags)
        generate_report(qa_pairs, scores) → dict     (rapport final)
    """

    def __init__(self, prefer_provider: str | None = None):
        # Client unifié : Groq (si GROQ_API_KEY) sinon Ollama local (RGPD).
        self.client = get_llm_client(prefer=prefer_provider)
        self.model  = self.client.model_name
        self.provider = self.client.provider
        self.max_tokens_questions = 5000
        self.max_tokens_scoring   = 700
        self.max_tokens_report    = 2500

    # ─────────────────────────────────────────
    # MÉTHODE 1 — Génération des 15 questions
    # ─────────────────────────────────────────
    def generate_questions(self, cv: CVSummary, offer: OfferSummary) -> list[dict]:
        """
        Génère 15 questions d'entretien personnalisées en 1 appel Groq.

        Retourne une liste de 15 dicts :
        {
            "index": 0,
            "phase": "validation_profil",
            "question": "...",
            "skill_targeted": "...",
            "cv_reference": "...",
            "context_hint": "...",
            "green_flag_keywords": [...],
            "red_flag_indicators": [...]
        }
        """
        profile = get_profile(offer.domaine_metier)

        # ── Priorisation CŒUR vs SECONDAIRE (basée sur l'OFFRE, pas le CV) ──
        # Les questions DÉTAILLÉES doivent cibler le cœur du poste (compétences
        # requises par l'offre), pas les technos périphériques du CV.
        offer_skills_lower = {s.lower() for s in offer.competences_requises}
        cv_skills_lower = {s.lower() for s in cv.competences}

        # CŒUR = compétences requises par l'offre (ordre = priorité de l'offre).
        # On garde TOUTES les requises (le poste passe avant le CV) ; à défaut,
        # on retombe sur le titre du poste + les premières compétences du CV.
        core_skills = list(offer.competences_requises[:6])
        if not core_skills:
            core_skills = cv.competences[:4]
        # Marque celles confirmées par le CV (pour personnaliser les questions)
        core_confirmed = [s for s in core_skills if s.lower() in cv_skills_lower]

        # SECONDAIRE = technos présentes dans le CV mais NON requises par l'offre
        # → questions générales / de survol uniquement (ex: AWS sur un poste backend).
        secondary_skills = [
            s for s in cv.competences
            if s.lower() not in offer_skills_lower
        ][:5]

        skills_to_target = core_skills  # rétro-compat (phase 2 ci-dessous)

        system_prompt = f"""Tu es {profile['expert_persona']}.
Tu conduis un entretien de recrutement structuré, professionnel et rigoureux.
Tu maîtrises les méthodologies STAR (Situation-Tâche-Action-Résultat),
le Criterion-Based Interviewing (CBI) et le référentiel de compétences ESCO.

━━━ POSTE ━━━
{offer.to_prompt_block()}

━━━ PROFIL CANDIDAT ━━━
{cv.to_prompt_block()}

━━━ COMPÉTENCES CŒUR DU POSTE (questions techniques DÉTAILLÉES et pointues) ━━━
(ce sont les compétences REQUISES par l'offre — c'est sur elles qu'il faut creuser
en profondeur : concepts, choix techniques, cas concrets, résolution de problèmes)
{', '.join(core_skills) or 'À déduire du titre du poste'}
{('Confirmées dans le CV : ' + ', '.join(core_confirmed)) if core_confirmed else ''}

━━━ COMPÉTENCES SECONDAIRES (questions GÉNÉRALES de survol uniquement) ━━━
(présentes dans le CV mais PAS au cœur du poste : reste général, ne creuse PAS,
1 question légère maximum, sans entrer dans les détails d'expert)
{', '.join(secondary_skills) or 'aucune'}

━━━ DOMAINE — ZONES TECHNIQUES OBLIGATOIRES (à couvrir pour le cœur du poste) ━━━
{chr(10).join(f'  • {z}' for z in profile['technical_areas'])}

━━━ VOCABULAIRE ATTENDU DANS LES BONNES RÉPONSES ━━━
{', '.join(profile['green_flag_keywords'][:12])}

━━━ RED FLAGS À DÉTECTER ━━━
{chr(10).join(f'  • {r}' for r in profile['red_flags'])}

━━━ FOCUS ÉVALUATION DE CE DOMAINE ━━━
{profile['evaluation_focus']}"""

        user_prompt = f"""Génère EXACTEMENT 15 questions d'entretien selon cette répartition :

PHASE 1 "validation_profil"    → 2 questions  (Q0, Q1)
  But : Vérifier la cohérence du parcours et l'expérience la plus récente

PHASE 2 "technique"            → 5 questions  (Q2, Q3, Q4, Q5, Q6)
  But : Valider EN PROFONDEUR les compétences CŒUR du poste : {', '.join(core_skills)}
  Répartition OBLIGATOIRE des 5 questions :
    • 4 questions DÉTAILLÉES/pointues sur le cœur du poste ({', '.join(core_skills[:4])})
      → concepts avancés, choix d'architecture, débogage, optimisation, cas concrets
    • 1 question GÉNÉRALE de survol sur une compétence secondaire{(' (ex: ' + secondary_skills[0] + ')') if secondary_skills else ''}
      → rester en surface, NE PAS demander de détails d'expert
  Règle : sur le cœur, exige une vraie démonstration de savoir-faire (pas une définition)

PHASE 3 "mise_en_situation"    → 3 questions  (Q7, Q8, Q9)
  But : Évaluer la prise de décision et la résolution de problèmes
  Inspire-toi de : {profile['phase3_scenario_focus']}
  Règle : Commence par "Imaginez que..." ou "Comment réagissez-vous si..."

PHASE 4 "soft_skill"           → 2 questions  (Q10, Q11)
  But : {profile['phase4_softskill_focus']}
  Règle : Méthode STAR obligatoire → commence par "Décrivez une situation professionnelle où..."

PHASE 5 "motivation"           → 2 questions  (Q12, Q13)
  But : Vérifier l'adéquation culturelle et les aspirations

PHASE 6 "cloture"              → 1 question   (Q14)
  But : Inviter le candidat à poser des questions ou à ajouter quelque chose

━━━ RÈGLES ABSOLUES (violations = questions refusées) ━━━
1. Chaque question DOIT mentionner un élément SPÉCIFIQUE du CV :
   nom d'entreprise, projet, technologie citée, diplôme, durée d'expérience...
2. Les questions techniques exigent une DÉMONSTRATION de savoir-faire, pas une définition
3. Les questions STAR (phase 4) commencent par "Décrivez une situation professionnelle où..."
4. INTERDIT : "Parlez-moi de vous", "Quels sont vos points forts/faibles ?", questions fermées
5. Le "context_hint" est un conseil bienveillant affiché au candidat (1 phrase courte)

Réponds UNIQUEMENT avec ce JSON valide (rien d'autre) :
{{
  "questions": [
    {{
      "index": 0,
      "phase": "validation_profil",
      "question": "Question complète ici",
      "skill_targeted": "Compétence ESCO ciblée",
      "cv_reference": "Élément précis du CV qui justifie cette question",
      "context_hint": "Conseil affiché au candidat (ex: Appuyez-vous sur un exemple concret de votre parcours)",
      "green_flag_keywords": ["terme technique attendu 1", "terme 2", "terme 3"],
      "red_flag_indicators": ["réponse trop vague", "incohérence avec le CV"]
    }}
  ]
}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.45,
            max_tokens=self.max_tokens_questions,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)
        questions = data.get("questions", [])

        # Validation basique
        if len(questions) != 15:
            print(f"⚠️  Groq a généré {len(questions)} questions (attendu 15). Vérifier le prompt.")

        return questions

    # ─────────────────────────────────────────
    # MÉTHODE 2 — Scoring d'une réponse
    # ─────────────────────────────────────────
    def score_answer(
        self,
        question: dict,
        answer: str,
        cv: CVSummary,
        domaine_metier: str = "IT / Développement",
    ) -> dict:
        """
        Score une réponse sur 5 dimensions (0-10 chacune).

        Retourne :
        {
            "scores": {
                "technique": 0-10,
                "star": 0-10,
                "coherence": 0-10,
                "specificite": 0-10,
                "communication": 0-10
            },
            "flags": {
                "green": [...],
                "yellow": [...],
                "red": [...]
            },
            "cv_contradiction": true/false,
            "contradiction_detail": "..." ou null
        }
        """
        profile = get_profile(domaine_metier)

        prompt = f"""Tu es un évaluateur RH expert en {domaine_metier}.
Évalue objectivement cette réponse d'entretien.

QUESTION : {question['question']}
PHASE : {question['phase']}
COMPÉTENCE CIBLÉE : {question.get('skill_targeted', 'N/A')}
RÉFÉRENCE CV : {question.get('cv_reference', 'N/A')}
GREEN FLAGS ATTENDUS : {', '.join(question.get('green_flag_keywords', []))}
RED FLAGS À DÉTECTER : {', '.join(question.get('red_flag_indicators', []))}

CV DU CANDIDAT (résumé) :
  Compétences : {', '.join(cv.competences)}
  Expériences : {'; '.join(cv.experiences)}

RÉPONSE DU CANDIDAT :
"{answer}"

━━━ BARÈME STRICT ━━━
Applique des standards professionnels élevés. Dans un vrai recrutement,
environ 30% des réponses sont en dessous de 5/10.

9-10 : Réponse avec métriques chiffrées, exemples précis et vérifiables,
       vocabulaire technique {domaine_metier} maîtrisé, structure parfaite
7-8  : Bonne réponse structurée, exemples concrets mais incomplets
5-6  : Réponse correcte, vague, peu concrète ou sans chiffres
3-4  : Superficiel, théorique sans pratique démontrée
0-2  : Réponse hors-sujet, incohérente avec le CV, refus de répondre

━━━ DIMENSIONS À SCORER ━━━
- technique     : Maîtrise du contenu {domaine_metier} (le plus important)
- star          : Structure Situation-Tâche-Action-Résultat (si applicable)
- coherence     : Cohérence avec le CV déclaré (vérifie les contradictions)
- specificite   : Concrétude, exemples réels vs réponses génériques
- communication : Clarté, organisation des idées, vocabulaire

Réponds UNIQUEMENT avec ce JSON (rien d'autre) :
{{
  "scores": {{
    "technique":     <entier 0-10>,
    "star":          <entier 0-10>,
    "coherence":     <entier 0-10>,
    "specificite":   <entier 0-10>,
    "communication": <entier 0-10>
  }},
  "scores_justifications": {{
    "technique":     "Justification courte (1 phrase)",
    "star":          "Justification courte (1 phrase)",
    "coherence":     "Justification courte (1 phrase)",
    "specificite":   "Justification courte (1 phrase)",
    "communication": "Justification courte (1 phrase)"
  }},
  "flags": {{
    "green":  ["Point positif détecté 1", "Point positif 2"],
    "yellow": ["Point mitigé 1"],
    "red":    ["Problème détecté 1"]
  }},
  "cv_contradiction": <true ou false>,
  "contradiction_detail": "<explication si contradiction, sinon null>"
}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=self.max_tokens_scoring,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)

    # ─────────────────────────────────────────
    # MÉTHODE 3 — Rapport final
    # ─────────────────────────────────────────
    def generate_report(
        self,
        cv: CVSummary,
        offer: OfferSummary,
        qa_pairs: list[dict],
        aggregated_scores: dict,
    ) -> dict:
        """
        Génère le rapport final après les 15 questions.

        Args:
            qa_pairs: liste de {"question": ..., "answer": ..., "scores": ..., "flags": ...}
            aggregated_scores: {"technique": float, "star": float, ...}

        Retourne le rapport complet en JSON.
        """
        score_global = round(
            aggregated_scores.get("technique",     0) * 0.40 +
            aggregated_scores.get("star",           0) * 0.20 +
            aggregated_scores.get("coherence",      0) * 0.15 +
            aggregated_scores.get("specificite",    0) * 0.15 +
            aggregated_scores.get("communication",  0) * 0.10,
            2,
        )
        score_100 = round(score_global * 10)

        # Synthèse Q&A (on tronque pour rester dans le contexte)
        qa_summary = []
        for i, pair in enumerate(qa_pairs):
            qa_summary.append({
                "q_index":  i,
                "phase":    pair.get("phase", ""),
                "question": pair["question"][:200],
                "answer":   pair["answer"][:300],
                "scores":   pair.get("scores", {}),
                "flags":    pair.get("flags", {}),
                "contradiction": pair.get("cv_contradiction", False),
            })

        prompt = f"""Tu es un consultant RH senior. Génère un rapport de recrutement professionnel.

CANDIDAT : {cv.nom}
POSTE : {offer.titre} ({offer.type_contrat})
DOMAINE : {offer.domaine_metier}

SCORES CALCULÉS :
  Technique (40%)      : {aggregated_scores.get('technique', 0):.1f}/10
  Méthode STAR (20%)   : {aggregated_scores.get('star', 0):.1f}/10
  Cohérence CV (15%)   : {aggregated_scores.get('coherence', 0):.1f}/10
  Spécificité (15%)    : {aggregated_scores.get('specificite', 0):.1f}/10
  Communication (10%)  : {aggregated_scores.get('communication', 0):.1f}/10
  SCORE GLOBAL         : {score_global:.1f}/10 → {score_100}/100

ENTRETIEN (résumé des {len(qa_pairs)} questions) :
{json.dumps(qa_summary, ensure_ascii=False, indent=2)[:5000]}

Génère un rapport professionnel, factuel et actionnable.
Cite des extraits de réponses pour appuyer tes points.

La recommandation doit être CATÉGORIQUE :
- RECRUTER   : score ≥ 7/10 ET pas de red flag critique
- HESITER    : score entre 5 et 6.9/10 OU des gaps identifiés
- REJETER    : score < 5/10 OU contradiction CV majeure OU refus de répondre

Réponds UNIQUEMENT avec ce JSON :
{{
  "score_global_10": {score_global},
  "score_global_100": {score_100},
  "recommandation": "RECRUTER|HESITER|REJETER",
  "recommandation_justification": "Justification factuelle en 2-3 phrases",
  "synthese_executive": "Résumé exécutif du candidat en 3-4 phrases",
  "competences": {{
    "validees": [
      {{"competence": "...", "preuve": "Citation de réponse"}}
    ],
    "partiellement_validees": [
      {{"competence": "...", "nuance": "Ce qui manque"}}
    ],
    "non_validees": [
      {{"competence": "...", "raison": "Pourquoi non validée"}}
    ]
  }},
  "soft_skills_detectes": [
    {{"label": "Leadership", "niveau": "Fort|Moyen|Faible", "citation": "..."}}
  ],
  "points_forts": ["Point fort 1", "Point fort 2", "Point fort 3"],
  "points_faibles": ["Point faible 1", "Point faible 2"],
  "contradictions_cv": ["Contradiction détectée (si applicable)"],
  "prochaines_etapes": [
    "Action concrète recommandée 1",
    "Action concrète recommandée 2"
  ]
}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=self.max_tokens_report,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)
