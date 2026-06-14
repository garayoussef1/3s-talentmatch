# -*- coding: utf-8 -*-
"""
Seed multi-offres + candidats fictifs puis lance le matching via API.

Usage (depuis la racine du projet) :
  .venv-10\Scripts\python.exe backend\scripts\seed_test_matching.py

Prérequis : backend en cours d'exécution sur http://localhost:8000
            Un compte admin existant (par défaut admin@local.test / Admin123!)
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# ── Bootstrap path ────────────────────────────────────────────────────────────
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        env = backend_dir / ".env"
        if env.exists():
            load_dotenv(env, override=False)
    except Exception:
        pass


_load_env()

import argparse
import os
import requests
from app.database import SessionLocal
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.models.match import Match, MatchStatus
from app.models.user import User

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE    = "http://localhost:8000/api"

def _parse_args():
    p = argparse.ArgumentParser(description="Seed test matching")
    p.add_argument("--email",    default=os.getenv("SEED_ADMIN_EMAIL", "admin1@esprit.tn"))
    p.add_argument("--password", default=os.getenv("SEED_ADMIN_PASS",  ""))
    return p.parse_args()

# ═══════════════════════════════════════════════════════════════════════════════
# OFFRES FICTIVES — 4 domaines différents
# ═══════════════════════════════════════════════════════════════════════════════
OFFERS = [
    {
        "titre":               "Ingénieur Backend Python / FastAPI",
        "description":         (
            "Rejoignez notre équipe pour développer des APIs REST performantes. "
            "Vous maîtrisez Python, FastAPI, PostgreSQL, Docker et SQLAlchemy. "
            "Expérience requise : 3 ans. Formation Bac+5 Informatique."
        ),
        "competences_requises": ["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "Redis", "SQLAlchemy", "REST API"],
        "type_contrat":        "CDI",
        "localisation":        "Tunis",
        "experience_requise":  3,
        "nb_postes":           1,
    },
    {
        "titre":               "Data Scientist / Machine Learning",
        "description":         (
            "Poste de Data Scientist pour développer des modèles de ML en production. "
            "Compétences : Python, scikit-learn, TensorFlow, Pandas, SQL, Jupyter. "
            "Expérience requise : 2 ans. Formation Bac+5 requis."
        ),
        "competences_requises": ["Python", "Machine Learning", "scikit-learn", "TensorFlow", "Pandas", "SQL", "Jupyter", "NLP"],
        "type_contrat":        "CDI",
        "localisation":        "Tunis",
        "experience_requise":  2,
        "nb_postes":           1,
    },
    {
        "titre":               "Développeur Frontend React",
        "description":         (
            "Développeur Frontend React pour construire des interfaces utilisateur modernes. "
            "Stack : React, TypeScript, Tailwind CSS, Vite, Jest, REST API. "
            "Expérience requise : 2 ans. Formation Bac+3 minimum."
        ),
        "competences_requises": ["React", "TypeScript", "JavaScript", "Tailwind CSS", "HTML", "CSS", "Git", "REST API"],
        "type_contrat":        "CDD",
        "localisation":        "Sfax",
        "experience_requise":  2,
        "nb_postes":           2,
    },
    {
        "titre":               "Stage Développement Web Full Stack",
        "description":         (
            "Stage de 6 mois pour étudiant en informatique. "
            "Technologies utilisées : React, Node.js, Python, PostgreSQL, Git. "
            "Aucune expérience professionnelle requise. Formation Bac+3 minimum."
        ),
        "competences_requises": ["Python", "JavaScript", "React", "Node.js", "Git", "HTML", "CSS"],
        "type_contrat":        "Stage",
        "localisation":        "Tunis",
        "experience_requise":  0,
        "nb_postes":           2,
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATS FICTIFS — 12 profils variés
# ═══════════════════════════════════════════════════════════════════════════════
def _cv_id() -> str:
    return f"fake-{uuid.uuid4().hex[:12]}"

CANDIDATES = [
    # ── Backend Python experts ─────────────────────────────────────────────
    {
        "nom": "Aymen Belhaj", "email": "aymen.belhaj@test.tn",
        "competences": ["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "Redis", "SQLAlchemy", "REST API", "pytest"],
        "experience_ans": 4, "formation_bac": 5,
        "experiences": [
            {"poste": "Ingénieur Backend Senior", "entreprise": "DataFlow Solutions",
             "dates": "2022-2026", "description": "FastAPI Python PostgreSQL Redis Docker CI/CD"},
            {"poste": "Développeur Python", "entreprise": "TechStartup",
             "dates": "2020-2022", "description": "Python REST API PostgreSQL Git"},
        ],
        "raw_text": "Python FastAPI PostgreSQL Docker Redis SQLAlchemy REST API Git pytest ingénieur backend 4 ans expérience Bac+5",
    },
    {
        "nom": "Sonia Trabelsi", "email": "sonia.trabelsi@test.tn",
        "competences": ["Python", "Django", "PostgreSQL", "Docker", "Git", "REST API", "Flask"],
        "experience_ans": 2, "formation_bac": 5,
        "experiences": [
            {"poste": "Développeuse Backend", "entreprise": "WebAgency",
             "dates": "2024-2026", "description": "Django Python PostgreSQL Docker Git REST API"},
        ],
        "raw_text": "Python Django PostgreSQL Docker Git REST API Flask développeuse backend 2 ans Bac+5",
    },
    {
        "nom": "Omar Hamdi", "email": "omar.hamdi@test.tn",
        "competences": ["Python", "Flask", "MySQL", "Git", "HTML", "CSS"],
        "experience_ans": 1, "formation_bac": 3,
        "experiences": [
            {"poste": "Développeur Junior", "entreprise": "WebDev Sfax",
             "dates": "2025-2026", "description": "Python Flask MySQL Git développeur junior"},
        ],
        "raw_text": "Python Flask MySQL Git HTML CSS développeur junior 1 an Bac+3",
    },
    # ── Java / autres stacks ────────────────────────────────────────────────
    {
        "nom": "Karim Mansouri", "email": "karim.mansouri@test.tn",
        "competences": ["Java", "Spring Boot", "MySQL", "Oracle", "Docker", "Git", "REST API", "Microservices"],
        "experience_ans": 3, "formation_bac": 5,
        "experiences": [
            {"poste": "Ingénieur Backend Java", "entreprise": "Banque de Tunisie",
             "dates": "2023-2026", "description": "Java Spring Boot MySQL Docker Git REST"},
        ],
        "raw_text": "Java Spring Boot MySQL Oracle Docker Git REST API microservices ingénieur 3 ans Bac+5",
    },
    # ── Data Science ────────────────────────────────────────────────────────
    {
        "nom": "Nadia Khelifi", "email": "nadia.khelifi@test.tn",
        "competences": ["Python", "Machine Learning", "scikit-learn", "TensorFlow", "Pandas", "SQL", "Jupyter", "NLP", "Deep Learning"],
        "experience_ans": 3, "formation_bac": 5,
        "experiences": [
            {"poste": "Data Scientist", "entreprise": "AI Lab Tunis",
             "dates": "2023-2026", "description": "Machine Learning Python scikit-learn TensorFlow NLP Pandas SQL"},
            {"poste": "Ingénieure ML", "entreprise": "Startup Data",
             "dates": "2021-2023", "description": "Deep Learning Jupyter Python data science"},
        ],
        "raw_text": "Machine Learning Python scikit-learn TensorFlow Pandas SQL NLP Deep Learning Data Science Bac+5 3 ans",
    },
    {
        "nom": "Mehdi Zouari", "email": "mehdi.zouari@test.tn",
        "competences": ["Python", "Pandas", "SQL", "Excel", "Power BI", "Statistics"],
        "experience_ans": 1, "formation_bac": 4,
        "experiences": [
            {"poste": "Analyste Data Junior", "entreprise": "Consulting TN",
             "dates": "2025-2026", "description": "Python Pandas SQL Power BI Excel statistiques"},
        ],
        "raw_text": "Python Pandas SQL Excel Power BI statistiques analyste data 1 an Bac+4",
    },
    # ── Frontend React ──────────────────────────────────────────────────────
    {
        "nom": "Ines Bouazizi", "email": "ines.bouazizi@test.tn",
        "competences": ["React", "TypeScript", "JavaScript", "Tailwind CSS", "HTML", "CSS", "Git", "REST API", "Vite"],
        "experience_ans": 2, "formation_bac": 3,
        "experiences": [
            {"poste": "Développeuse Frontend", "entreprise": "DigitalAgency",
             "dates": "2024-2026", "description": "React TypeScript Tailwind CSS JavaScript HTML Vite Git"},
        ],
        "raw_text": "React TypeScript JavaScript Tailwind CSS HTML CSS Git REST API Vite frontend développeuse 2 ans Bac+3",
    },
    {
        "nom": "Youssef Gharbi", "email": "youssef.gharbi@test.tn",
        "competences": ["JavaScript", "Vue.js", "HTML", "CSS", "Bootstrap", "Git"],
        "experience_ans": 1, "formation_bac": 3,
        "experiences": [
            {"poste": "Développeur Web Junior", "entreprise": "Web Studio",
             "dates": "2025-2026", "description": "JavaScript Vue.js HTML CSS Bootstrap Git"},
        ],
        "raw_text": "JavaScript Vue.js HTML CSS Bootstrap Git développeur web junior 1 an Bac+3",
    },
    # ── Profils Stage ───────────────────────────────────────────────────────
    {
        "nom": "Amira Saidi", "email": "amira.saidi@test.tn",
        "competences": ["Python", "JavaScript", "React", "HTML", "CSS", "Git", "Node.js"],
        "experience_ans": 0, "formation_bac": 3,
        "experiences": [],
        "raw_text": "Python JavaScript React HTML CSS Git Node.js étudiant Bac+3 stage développement web full stack",
    },
    {
        "nom": "Fares Mejri", "email": "fares.mejri@test.tn",
        "competences": ["Python", "C++", "HTML", "CSS", "Git"],
        "experience_ans": 0, "formation_bac": 2,
        "experiences": [],
        "raw_text": "Python C++ HTML CSS Git étudiant licence informatique stage développeur",
    },
    # ── Hors domaine ────────────────────────────────────────────────────────
    {
        "nom": "Rania Jebali", "email": "rania.jebali@test.tn",
        "competences": ["Google Ads", "SEO", "Facebook Ads", "Canva", "Excel", "Community Management"],
        "experience_ans": 3, "formation_bac": 3,
        "experiences": [
            {"poste": "Responsable Marketing Digital", "entreprise": "E-commerce TN",
             "dates": "2023-2026", "description": "Google Ads SEO Facebook Ads marketing digital"},
        ],
        "raw_text": "Google Ads SEO Facebook Ads Canva Excel marketing digital community management Bac+3 3 ans",
    },
    {
        "nom": "Tarek Jelassi", "email": "tarek.jelassi@test.tn",
        "competences": ["AutoCAD", "SolidWorks", "Matlab", "C", "Électronique"],
        "experience_ans": 2, "formation_bac": 5,
        "experiences": [
            {"poste": "Ingénieur Électronique", "entreprise": "Industrie TN",
             "dates": "2024-2026", "description": "AutoCAD SolidWorks Matlab électronique embarquée C"},
        ],
        "raw_text": "AutoCAD SolidWorks Matlab C électronique ingénieur industriel Bac+5 2 ans",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers DB
# ═══════════════════════════════════════════════════════════════════════════════

def _build_parsed_data(c: dict) -> dict:
    return {
        "competences": [{"name": s} for s in c["competences"]],
        "formations":  [{"diplome": f"Bac+{c['formation_bac']}", "niveau": c["formation_bac"]}],
        "experiences": c["experiences"],
        "contact":     {"nom": c["nom"], "email": c["email"]},
        "metadata": {
            "annees_experience_totales": float(c["experience_ans"]),
            "niveau_formation_max":      c["formation_bac"],
        },
    }


def seed_db(db) -> tuple[list, list]:
    """Insère offres + candidats en base, retourne (offers, candidates)."""

    # Récupérer un user admin existant pour lier les offres
    admin = db.query(User).filter(User.role == "admin").first()
    if not admin:
        print("  ⚠ Aucun admin trouvé — les offres seront créées sans owner.")

    # ── Offres ────────────────────────────────────────────────────────────
    print("\n[1/3] Création des offres...")
    offers = []
    for od in OFFERS:
        existing = db.query(JobOffer).filter(JobOffer.titre == od["titre"]).first()
        if existing:
            print(f"  → Existe déjà : {od['titre']}")
            offers.append(existing)
            continue
        offer = JobOffer(
            id=uuid.uuid4(),
            titre=od["titre"],
            description=od["description"],
            competences_requises=od["competences_requises"],
            type_contrat=od["type_contrat"],
            localisation=od["localisation"],
            experience_requise=od["experience_requise"],
            nb_postes=od["nb_postes"],
            status="active",
            recruiter_id=admin.id if admin else None,
        )
        db.add(offer)
        db.flush()
        print(f"  [OK] {od['titre']}")
        offers.append(offer)

    # ── Candidats ─────────────────────────────────────────────────────────
    print("\n[2/3] Creation des candidats...")
    candidates = []
    for cd in CANDIDATES:
        existing = db.query(Candidate).filter(Candidate.email == cd["email"]).first()
        if existing:
            print(f"  [--] Existe deja : {cd['nom']}")
            candidates.append(existing)
            continue
        cand = Candidate(
            id=uuid.uuid4(),
            cv_id=_cv_id(),
            filename=f"{cd['nom'].replace(' ', '_')}_fake.pdf",
            nom=cd["nom"],
            email=cd["email"],
            parsed_data=_build_parsed_data(cd),
            raw_text=cd["raw_text"],
            extraction_method="seed_script",
            information_acknowledged=True,
            user_id=admin.id if admin else None,
        )
        db.add(cand)
        db.flush()
        print(f"  [OK] {cd['nom']} ({len(cd['competences'])} competences, {cd['experience_ans']} ans, Bac+{cd['formation_bac']})")
        candidates.append(cand)

    # ── Candidatures (Match) — tous les candidats postulent a toutes les offres ──
    print("\n[3/3] Creation des candidatures...")
    created = 0
    for offer in offers:
        for cand in candidates:
            exists = db.query(Match).filter(
                Match.candidate_id == cand.id,
                Match.job_offer_id == offer.id,
            ).first()
            if not exists:
                db.add(Match(
                    id=uuid.uuid4(),
                    candidate_id=cand.id,
                    job_offer_id=offer.id,
                    score=0.0,
                    status=MatchStatus.pending,
                ))
                created += 1
    print(f"  [OK] {created} candidatures creees")

    db.commit()
    return offers, candidates


# ═══════════════════════════════════════════════════════════════════════════════
# Appel API matching
# ═══════════════════════════════════════════════════════════════════════════════

def get_token(email: str, password: str) -> str:
    r = requests.post(f"{API_BASE}/auth/login",
                      json={"email": email, "password": password},
                      timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def run_matching(offer_id: str, token: str) -> list[dict]:
    r = requests.post(
        f"{API_BASE}/match-sandbox/{offer_id}?engine=bert",
        headers={"Authorization": f"Bearer {token}"},
        timeout=300,
    )
    if r.status_code != 200:
        print(f"    ⚠ Matching API error {r.status_code}: {r.text[:200]}")
        return []
    data = r.json()
    results = data.get("bert_results") or data.get("results") or []
    return sorted(results, key=lambda x: x.get("bert_score", 0), reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Affichage
# ═══════════════════════════════════════════════════════════════════════════════

def _bar(pct: int, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _label(pct: int) -> str:
    if pct >= 75: return "Excellent "
    if pct >= 55: return "Bon       "
    if pct >= 35: return "Partiel   "
    return "Insuffisant"


def print_results(offer_title: str, results: list[dict]) -> None:
    print(f"\n{'═'*80}")
    print(f"  OFFRE : {offer_title}")
    print(f"{'═'*80}")
    print(f"  {'#':<3} {'Candidat':<22} {'Score':>5}  {'Barre':<22} {'Niveau':<12} {'Comp':>5} {'Exp':>5} {'Form':>5}")
    print(f"  {'-'*75}")
    for i, r in enumerate(results, 1):
        name  = (r.get("candidate_name") or "?")[:21]
        pct   = round((r.get("bert_score") or 0) * 100)
        bd    = r.get("bert_details") or {}
        comp  = int(bd.get("competences") or 0)
        exp   = int(bd.get("experience") or 0)
        form  = int(bd.get("formation") or 0)
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"  {medal}{i:<3} {name:<22} {pct:>4}%  {_bar(pct):<22} {_label(pct):<12} {comp:>4}% {exp:>4}% {form:>4}%")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    args = _parse_args()

    if not args.password:
        print("Usage: python seed_test_matching.py --email admin1@esprit.tn --password VOTRE_MOT_DE_PASSE")
        sys.exit(1)

    ADMIN_EMAIL = args.email
    ADMIN_PASS  = args.password
    print("=" * 80)
    print("  3S TalentMatch — Seed & Test Matching Multi-Offres")
    print("=" * 80)

    # 1. Seed DB
    db = SessionLocal()
    try:
        offers, _ = seed_db(db)
    finally:
        db.close()

    # 2. Login
    print("\n[4/4] Lancement du matching via API...")
    try:
        token = get_token(ADMIN_EMAIL, ADMIN_PASS)
        print(f"  [OK] Connecte en tant que {ADMIN_EMAIL}")
    except Exception as e:
        print(f"  [X] Impossible de se connecter : {e}")
        print("  --> Verifiez votre mot de passe avec --password")
        sys.exit(1)

    # 3. Matching pour chaque offre
    all_results = {}
    for offer in offers:
        print(f"\n  Matching : {offer.titre}...")
        results = run_matching(str(offer.id), token)
        all_results[offer.titre] = results
        if results:
            print(f"    {len(results)} candidats scorés")
        else:
            print("    Aucun résultat (BERT peut prendre 30-60s, réessayez si timeout)")

    # 4. Affichage
    print("\n\n" + "═" * 80)
    print("  RÉSULTATS COMPLETS")
    print("═" * 80)
    for title, results in all_results.items():
        if results:
            print_results(title, results)

    print(f"\n{'═'*80}")
    print("  Terminé. Ouvrez l'interface web pour voir les détails.")
    print("  http://localhost:3000")
    print("═" * 80)


if __name__ == "__main__":
    main()
