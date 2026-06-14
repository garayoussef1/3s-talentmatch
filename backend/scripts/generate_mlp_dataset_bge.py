"""
generate_mlp_dataset_bge.py
===========================
Génère un dataset d'entraînement pour le MLP en utilisant BGE-M3.

Pour chaque paire (offre, candidat), calcule les 5 features via BGE-M3
et assigne un label OBJECTIF basé sur le chevauchement réel des compétences
(indépendant de BGE-M3 → pas de fuite de données).

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10/Scripts/python backend/scripts/generate_mlp_dataset_bge.py

Sortie : data/mlp_training_bge/dataset.csv
"""
from __future__ import annotations
import sys, os, csv, json, random
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from rapidfuzz import fuzz
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.services.matching.match_engine import _normalize_skill

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "mlp_training_bge"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "dataset.csv"

# ── Profils offres ────────────────────────────────────────────────────────────
OFFRES = [
    {
        "titre": "Ingénieur Backend Python / FastAPI",
        "description": "Poste CDI backend Python FastAPI PostgreSQL Docker Redis SQLAlchemy 3 ans expérience Bac+5",
        "type_contrat": "CDI",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "SQLAlchemy", "Git", "REST API"],
        "exp_requise": 3, "edu_requise": 5,
    },
    {
        "titre": "Data Scientist Machine Learning",
        "description": "Poste CDI data scientist Python TensorFlow scikit-learn Pandas NumPy SQL 2 ans Bac+5",
        "type_contrat": "CDI",
        "skills": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Git"],
        "exp_requise": 2, "edu_requise": 5,
    },
    {
        "titre": "Développeur Frontend React TypeScript",
        "description": "Poste CDI frontend React TypeScript JavaScript HTML CSS Tailwind Git 2 ans Bac+3",
        "type_contrat": "CDI",
        "skills": ["React", "TypeScript", "JavaScript", "HTML", "CSS", "Tailwind", "Git", "REST API"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Ingénieur DevOps Cloud AWS",
        "description": "Poste CDI DevOps AWS Docker Kubernetes Terraform Ansible CI/CD Linux 4 ans Bac+5",
        "type_contrat": "CDI",
        "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "Ansible", "CI/CD", "Git", "Linux"],
        "exp_requise": 4, "edu_requise": 5,
    },
    {
        "titre": "Développeur Full Stack Java Angular Stage",
        "description": "Stage 6 mois Java Spring Boot Angular SQL Git REST API débutant accepté Bac+5",
        "type_contrat": "Stage",
        "skills": ["Java", "Spring Boot", "Angular", "SQL", "Git", "REST API"],
        "exp_requise": 0, "edu_requise": 5,
    },
    {
        "titre": "Développeur PHP Laravel",
        "description": "CDI développeur PHP Laravel MySQL Docker Git API REST 2 ans Bac+3",
        "type_contrat": "CDI",
        "skills": ["PHP", "Laravel", "MySQL", "Docker", "Git", "REST API", "JavaScript"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Analyste Cybersécurité Pentester",
        "description": "CDI sécurité informatique Kali Linux Burp Suite Python réseaux 2 ans Bac+5",
        "type_contrat": "CDI",
        "skills": ["Cybersécurité", "Pentest", "Kali Linux", "Python", "Linux", "Réseaux"],
        "exp_requise": 2, "edu_requise": 5,
    },
    {
        "titre": "Responsable Marketing Digital",
        "description": "CDI marketing digital Google Ads SEO Facebook Ads Google Analytics community management",
        "type_contrat": "CDI",
        "skills": ["Google Ads", "SEO", "Facebook Ads", "Google Analytics", "Community Management"],
        "exp_requise": 2, "edu_requise": 3,
    },
]

# ── Profils candidats ─────────────────────────────────────────────────────────
CANDIDATS = [
    # ── Backend Python ────────────────────────────────────────────────────────
    {
        "nom": "Senior Backend Python",
        "cv_text": "Ingénieur backend Python FastAPI PostgreSQL Docker Redis SQLAlchemy Git REST API pytest CI/CD 6 ans expérience Bac+5 ingénieur informatique",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "SQLAlchemy", "Git", "REST API", "pytest"],
        "exp_years": 6, "edu_level": 5,
    },
    {
        "nom": "Mid Backend Django",
        "cv_text": "Développeur Python Django Django REST Framework PostgreSQL Docker Git JavaScript REST API pytest 2 ans Bac+5 master génie logiciel",
        "skills": ["Python", "Django", "PostgreSQL", "Docker", "Git", "REST API", "JavaScript"],
        "exp_years": 2, "edu_level": 5,
    },
    {
        "nom": "Junior Python Flask",
        "cv_text": "Développeur junior Python Flask MySQL Git HTML CSS REST API 1 an Bac+3 licence informatique",
        "skills": ["Python", "Flask", "MySQL", "Git", "HTML", "CSS"],
        "exp_years": 1, "edu_level": 3,
    },
    # ── Java ──────────────────────────────────────────────────────────────────
    {
        "nom": "Senior Java Spring",
        "cv_text": "Ingénieur Java Spring Boot JPA Hibernate MySQL Docker Kubernetes Git CI/CD Angular TypeScript REST API microservices 5 ans Bac+5",
        "skills": ["Java", "Spring Boot", "MySQL", "Docker", "Kubernetes", "Git", "Angular", "TypeScript", "REST API"],
        "exp_years": 5, "edu_level": 5,
    },
    {
        "nom": "Junior Java Angular Stage",
        "cv_text": "Étudiant ingénieur Java Spring Boot Angular SQL Git REST API stage fin études Bac+5 en cours",
        "skills": ["Java", "Spring Boot", "Angular", "SQL", "Git", "REST API"],
        "exp_years": 0, "edu_level": 4,
    },
    # ── Data Science ──────────────────────────────────────────────────────────
    {
        "nom": "Senior Data Scientist",
        "cv_text": "Data scientist Python TensorFlow PyTorch scikit-learn Pandas NumPy SQL Docker MLflow Git machine learning NLP 4 ans Bac+5 master data science",
        "skills": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Docker", "MLflow", "Git"],
        "exp_years": 4, "edu_level": 5,
    },
    {
        "nom": "Data Analyst Junior",
        "cv_text": "Data analyst Python Pandas NumPy SQL scikit-learn Excel Power BI Tableau Git statistiques 1 an Bac+3",
        "skills": ["Python", "Pandas", "NumPy", "SQL", "scikit-learn", "Excel", "Power BI", "Git"],
        "exp_years": 1, "edu_level": 3,
    },
    # ── Frontend ──────────────────────────────────────────────────────────────
    {
        "nom": "Senior Frontend React",
        "cv_text": "Développeur frontend React TypeScript JavaScript HTML CSS Tailwind Next.js Redux Git REST API Figma 3 ans Bac+3",
        "skills": ["React", "TypeScript", "JavaScript", "HTML", "CSS", "Tailwind", "Next.js", "Git", "REST API"],
        "exp_years": 3, "edu_level": 3,
    },
    {
        "nom": "Junior Frontend Vue",
        "cv_text": "Développeur web JavaScript HTML CSS Vue.js Bootstrap Git 1 an Bac+2",
        "skills": ["JavaScript", "HTML", "CSS", "Vue.js", "Bootstrap", "Git"],
        "exp_years": 1, "edu_level": 2,
    },
    # ── DevOps ────────────────────────────────────────────────────────────────
    {
        "nom": "Senior DevOps AWS",
        "cv_text": "Ingénieur DevOps AWS Docker Kubernetes Terraform Ansible CI/CD Jenkins GitLab Linux Prometheus Grafana 6 ans Bac+5",
        "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "Ansible", "CI/CD", "Git", "Linux", "Prometheus"],
        "exp_years": 6, "edu_level": 5,
    },
    # ── PHP ───────────────────────────────────────────────────────────────────
    {
        "nom": "Développeur PHP Laravel",
        "cv_text": "Développeur PHP Laravel MySQL Docker Git JavaScript REST API Vue.js Composer 3 ans Bac+3",
        "skills": ["PHP", "Laravel", "MySQL", "Docker", "Git", "JavaScript", "REST API"],
        "exp_years": 3, "edu_level": 3,
    },
    # ── Cybersécurité ─────────────────────────────────────────────────────────
    {
        "nom": "Analyste Sécurité",
        "cv_text": "Analyste cybersécurité Kali Linux Burp Suite Metasploit Python Linux réseaux firewall ISO 27001 OWASP pentest 3 ans Bac+5",
        "skills": ["Cybersécurité", "Pentest", "Kali Linux", "Python", "Linux", "Réseaux", "Burp Suite"],
        "exp_years": 3, "edu_level": 5,
    },
    # ── Marketing ────────────────────────────────────────────────────────────
    {
        "nom": "Marketing Digital Expert",
        "cv_text": "Responsable marketing digital Google Ads SEO Facebook Ads Google Analytics community management email marketing Excel 3 ans Bac+3",
        "skills": ["Google Ads", "SEO", "Facebook Ads", "Google Analytics", "Community Management", "Excel"],
        "exp_years": 3, "edu_level": 3,
    },
    # ── Hors domaine ──────────────────────────────────────────────────────────
    {
        "nom": "Comptable",
        "cv_text": "Comptable Excel comptabilité générale bilan TVA audit fiscalité paie 5 ans Bac+3",
        "skills": ["Excel", "Comptabilité", "Audit", "Fiscalité"],
        "exp_years": 5, "edu_level": 3,
    },
    {
        "nom": "Commercial Vente",
        "cv_text": "Commercial vente prospection négociation CRM PowerPoint Excel relation client 4 ans Bac+3",
        "skills": ["CRM", "Négociation", "Excel", "PowerPoint"],
        "exp_years": 4, "edu_level": 3,
    },
]


def skill_overlap(offer_skills: list, cv_skills: list) -> float:
    """Taux de chevauchement réel des compétences — indépendant de BGE-M3."""
    if not offer_skills:
        return 0.5
    matches = 0
    for req in offer_skills:
        req_n = _normalize_skill(req)
        for cv_s in cv_skills:
            cv_n = _normalize_skill(cv_s)
            if req_n == cv_n or fuzz.token_set_ratio(req_n, cv_n) >= 80:
                matches += 1
                break
    return round(min(1.0, matches / len(offer_skills)), 4)


def compute_label(offre: dict, candidat: dict) -> float:
    """
    Label objectif 0.0→1.0 basé sur des critères mesurables,
    INDÉPENDANT de BGE-M3 (pas de fuite de données).
    """
    # 1. Chevauchement compétences (50%)
    s_skills = skill_overlap(offre["skills"], candidat["skills"])

    # 2. Expérience (25%)
    req_exp = offre["exp_requise"]
    if req_exp <= 0:
        s_exp = 1.0
    elif candidat["exp_years"] >= req_exp:
        s_exp = 1.0
    else:
        s_exp = min(1.0, candidat["exp_years"] / req_exp)

    # 3. Formation (15%)
    req_edu = offre["edu_requise"]
    if req_edu <= 0:
        s_edu = 1.0
    elif candidat["edu_level"] >= req_edu:
        s_edu = 1.0
    else:
        s_edu = round(candidat["edu_level"] / req_edu, 4)

    # 4. Bonus domaine (10%) — même domaine = bonus
    s_domain = 0.5  # neutre par défaut

    label = (s_skills * 0.50 + s_exp * 0.25 + s_edu * 0.15 + s_domain * 0.10)
    return round(max(0.10, min(0.95, label)), 4)


def main():
    print("=" * 55)
    print("  Génération dataset MLP avec BGE-M3")
    print("=" * 55)

    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    scorer._ensure_reranker_loaded()

    if not scorer.ready:
        print("[ERREUR] BGE-M3 non disponible.")
        sys.exit(1)

    print(f"[OK] BGE-M3 chargé — {scorer.model_name}")
    print(f"[OK] Reranker chargé — {scorer.reranker_ready}")
    print(f"[INFO] {len(OFFRES)} offres × {len(CANDIDATS)} candidats = {len(OFFRES)*len(CANDIDATS)} paires\n")

    rows = []
    total = len(OFFRES) * len(CANDIDATS)
    done = 0

    for offre in OFFRES:
        offer_text = f"{offre['titre']} {offre['description']} {' '.join(offre['skills'])}"

        for cand in CANDIDATS:
            cv_text = cand["cv_text"]

            # ── Features BGE-M3 ───────────────────────────────────
            sem_sim = scorer.score_semantique(offer_text, cv_text)
            skill_rate = scorer.score_skills_bert(offre["skills"], cand["skills"])[0]
            exp_score = scorer.score_experience(
                cand["exp_years"], offre["exp_requise"], offer_text, cv_text
            )
            formation_score = scorer.score_formation(cand["edu_level"], offre["edu_requise"])

            # taux appréciées = 0.5 (neutre, pas d'info)
            apr_rate = 0.5

            # ── Label objectif (indépendant BGE-M3) ──────────────
            label = compute_label(offre, cand)

            rows.append({
                "offre":          offre["titre"],
                "candidat":       cand["nom"],
                "sem_sim":        round(sem_sim, 6),
                "skill_rate":     round(skill_rate, 6),
                "exp_score":      round(exp_score, 6),
                "formation_score":round(formation_score, 6),
                "apr_rate":       apr_rate,
                "label":          label,
            })

            done += 1
            print(f"  [{done:3d}/{total}] {offre['titre'][:30]:<30} + {cand['nom']:<28} label={label:.2f}")

    # Sauvegarder CSV
    fieldnames = ["offre", "candidat", "sem_sim", "skill_rate", "exp_score", "formation_score", "apr_rate", "label"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[OK] {len(rows)} paires sauvegardees : {OUT_CSV}")
    print("Lancez maintenant : .venv-10/Scripts/python backend/scripts/train_mlp_bge.py")


if __name__ == "__main__":
    main()
