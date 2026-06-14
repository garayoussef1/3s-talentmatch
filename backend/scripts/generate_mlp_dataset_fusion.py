"""
generate_mlp_dataset_fusion.py  — v2.0
=======================================
Génère le dataset d'entraînement pour le MLP Fusion.

v2.0 : dataset étendu — 30 offres × 50 candidats = 1500 paires
Couvre tous les domaines : backend, frontend, data/IA, devops,
cybersécurité, mobile, QA, marketing, finance, RH, gestion de projet.

Features (5, identiques à celles de l'inférence depuis bert_details) :
  sem_bge  | comp_bge | exp_bge | form_bge  →  BGE-M3
  sem_v2                                     →  BERT v2 (fine-tuné)

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10\\Scripts\\python backend/scripts/generate_mlp_dataset_fusion.py
"""
from __future__ import annotations
import sys, os, csv
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",   "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from rapidfuzz import fuzz
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.services.matching.match_engine import _normalize_skill

REPO_ROOT    = Path(__file__).resolve().parents[2]
OUT_DIR      = REPO_ROOT / "data" / "mlp_training_fusion"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV      = OUT_DIR / "dataset_fusion.csv"
BERT_V2_PATH = str(REPO_ROOT / "data" / "models" / "talentmatch-bert-v2.0")


# ── Objets mock pour appeler scorer.score() sans ORM ─────────────────────────
class _MockOffer:
    def __init__(self, d: dict):
        self.titre                  = d["titre"]
        self.description            = d["description"]
        self.competences_requises   = d["skills"]
        self.competences_appreciees = d.get("skills_apr", [])
        self.experience_requise     = d["exp_requise"]
        self.raw_text               = d["description"] + " " + " ".join(d["skills"])
        self.localisation           = d.get("localisation", None)
        self.type_contrat           = d.get("type_contrat", "CDI")
        self.status                 = "active"


class _MockCandidate:
    def __init__(self, d: dict):
        self.nom         = d["nom"]
        self.email       = d["nom"].lower().replace(" ", "_") + "@test.com"
        self.raw_text    = d["cv_text"]
        self.cv_id       = None
        self.parsed_data = {
            "competences": d["skills"],
            "experiences": [{"poste": d["nom"], "description": d["cv_text"]}],
            "formations":  [],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# OFFRES — 30 profils couvrant tous les domaines
# ═══════════════════════════════════════════════════════════════════════════════
OFFRES = [
    # ── Backend ─────────────────────────────────────────────────────────────
    {
        "titre": "Ingénieur Backend Python FastAPI",
        "description": "CDI ingénieur backend Python FastAPI PostgreSQL Docker Redis SQLAlchemy API REST microservices 3 ans Bac+5",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "SQLAlchemy", "Git", "REST API"],
        "exp_requise": 3, "edu_requise": 5,
    },
    {
        "titre": "Développeur Backend Python Django",
        "description": "CDI Python Django REST Framework PostgreSQL Celery Redis Docker Git pytest 2 ans Bac+5",
        "skills": ["Python", "Django", "PostgreSQL", "Docker", "Redis", "Git", "REST API", "Celery"],
        "exp_requise": 2, "edu_requise": 5,
    },
    {
        "titre": "Développeur Backend Java Spring Boot",
        "description": "CDI Java Spring Boot JPA Hibernate MySQL Docker Kubernetes Maven microservices 4 ans Bac+5",
        "skills": ["Java", "Spring Boot", "MySQL", "Docker", "Kubernetes", "Git", "REST API", "Maven"],
        "exp_requise": 4, "edu_requise": 5,
    },
    {
        "titre": "Développeur Backend Node.js",
        "description": "CDI Node.js Express TypeScript MongoDB Docker Redis JWT REST API 3 ans Bac+3",
        "skills": ["Node.js", "Express", "TypeScript", "MongoDB", "Docker", "Redis", "Git", "REST API"],
        "exp_requise": 3, "edu_requise": 3,
    },
    {
        "titre": "Développeur PHP Laravel",
        "description": "CDI PHP Laravel MySQL Docker Git API REST JavaScript Vue.js 2 ans Bac+3",
        "skills": ["PHP", "Laravel", "MySQL", "Docker", "Git", "REST API", "JavaScript"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Développeur .NET C# Backend",
        "description": "CDI C# ASP.NET Core Entity Framework SQL Server Docker Azure REST API 3 ans Bac+5",
        "skills": ["C#", ".NET", "ASP.NET", "SQL Server", "Docker", "Azure", "Git", "REST API"],
        "exp_requise": 3, "edu_requise": 5,
    },

    # ── Frontend ─────────────────────────────────────────────────────────────
    {
        "titre": "Développeur Frontend React TypeScript",
        "description": "CDI React TypeScript JavaScript HTML CSS Tailwind Next.js Redux Git REST API 2 ans Bac+3",
        "skills": ["React", "TypeScript", "JavaScript", "HTML", "CSS", "Tailwind", "Git", "REST API"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Développeur Frontend Angular",
        "description": "CDI Angular TypeScript RxJS NgRx HTML CSS SCSS REST API Docker 3 ans Bac+5",
        "skills": ["Angular", "TypeScript", "JavaScript", "HTML", "CSS", "RxJS", "Git", "REST API"],
        "exp_requise": 3, "edu_requise": 5,
    },
    {
        "titre": "Développeur Frontend Vue.js",
        "description": "CDI Vue.js JavaScript Nuxt.js Pinia HTML CSS Tailwind Git REST API 2 ans Bac+3",
        "skills": ["Vue.js", "JavaScript", "HTML", "CSS", "Tailwind", "Git", "REST API"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Développeur Full Stack React Node.js",
        "description": "CDI React Node.js Express TypeScript MongoDB PostgreSQL Docker Git REST API 3 ans Bac+5",
        "skills": ["React", "Node.js", "TypeScript", "MongoDB", "PostgreSQL", "Docker", "Git", "REST API"],
        "exp_requise": 3, "edu_requise": 5,
    },

    # ── Mobile ───────────────────────────────────────────────────────────────
    {
        "titre": "Développeur Mobile Flutter",
        "description": "CDI Flutter Dart Firebase REST API Git Android iOS state management 2 ans Bac+3",
        "skills": ["Flutter", "Dart", "Firebase", "REST API", "Git", "Android", "iOS"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Développeur Mobile Android Kotlin",
        "description": "CDI Android Kotlin Jetpack Compose Retrofit Room Firebase MVVM Git 3 ans Bac+5",
        "skills": ["Android", "Kotlin", "Jetpack Compose", "Retrofit", "Firebase", "Git", "REST API"],
        "exp_requise": 3, "edu_requise": 5,
    },

    # ── Data / IA ────────────────────────────────────────────────────────────
    {
        "titre": "Data Scientist Machine Learning",
        "description": "CDI Python TensorFlow scikit-learn Pandas NumPy SQL Docker MLflow machine learning NLP 2 ans Bac+5",
        "skills": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Git"],
        "exp_requise": 2, "edu_requise": 5,
    },
    {
        "titre": "Ingénieur Machine Learning MLOps",
        "description": "CDI Python PyTorch MLflow Kubernetes Docker CI/CD AWS SageMaker déploiement modèles 3 ans Bac+5",
        "skills": ["Python", "PyTorch", "MLflow", "Docker", "Kubernetes", "AWS", "CI/CD", "Git"],
        "exp_requise": 3, "edu_requise": 5,
    },
    {
        "titre": "Data Analyst BI",
        "description": "CDI Python SQL Power BI Tableau Excel Pandas statistiques dashboards 2 ans Bac+3",
        "skills": ["Python", "SQL", "Power BI", "Tableau", "Excel", "Pandas", "Git"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Data Engineer Big Data",
        "description": "CDI Python Spark Kafka Airflow Hadoop PostgreSQL Docker AWS S3 ETL pipelines 4 ans Bac+5",
        "skills": ["Python", "Apache Spark", "Kafka", "Airflow", "Docker", "AWS", "SQL", "Git"],
        "exp_requise": 4, "edu_requise": 5,
    },

    # ── DevOps / Cloud ───────────────────────────────────────────────────────
    {
        "titre": "Ingénieur DevOps AWS",
        "description": "CDI AWS Docker Kubernetes Terraform Ansible CI/CD Jenkins Linux Prometheus Grafana 4 ans Bac+5",
        "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "Ansible", "CI/CD", "Linux", "Git"],
        "exp_requise": 4, "edu_requise": 5,
    },
    {
        "titre": "Ingénieur Cloud Azure",
        "description": "CDI Azure AKS Terraform Docker CI/CD Azure DevOps Linux PowerShell 3 ans Bac+5",
        "skills": ["Azure", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux", "Git", "PowerShell"],
        "exp_requise": 3, "edu_requise": 5,
    },
    {
        "titre": "Ingénieur SRE Site Reliability",
        "description": "CDI Kubernetes Prometheus Grafana Linux Python Bash Docker CI/CD incident management 4 ans Bac+5",
        "skills": ["Kubernetes", "Prometheus", "Grafana", "Linux", "Python", "Docker", "CI/CD", "Git"],
        "exp_requise": 4, "edu_requise": 5,
    },

    # ── Cybersécurité ────────────────────────────────────────────────────────
    {
        "titre": "Analyste Cybersécurité Pentester",
        "description": "CDI Kali Linux Burp Suite Metasploit Python réseaux OWASP ISO 27001 pentest 2 ans Bac+5",
        "skills": ["Cybersécurité", "Pentest", "Kali Linux", "Python", "Linux", "Réseaux", "Burp Suite"],
        "exp_requise": 2, "edu_requise": 5,
    },
    {
        "titre": "Analyste SOC Cybersécurité",
        "description": "CDI SIEM Splunk QRadar réseaux firewall IDS/IPS Linux incident response 2 ans Bac+5",
        "skills": ["SIEM", "Splunk", "Réseaux", "Linux", "Cybersécurité", "Firewall", "Git"],
        "exp_requise": 2, "edu_requise": 5,
    },

    # ── QA / Test ────────────────────────────────────────────────────────────
    {
        "titre": "Ingénieur QA Automation",
        "description": "CDI Selenium Cypress Python pytest Java JUnit REST API Git CI/CD automatisation tests 2 ans Bac+5",
        "skills": ["Selenium", "Python", "pytest", "REST API", "Git", "CI/CD", "Java"],
        "exp_requise": 2, "edu_requise": 5,
    },

    # ── Stage / Junior ───────────────────────────────────────────────────────
    {
        "titre": "Développeur Full Stack Java Angular Stage",
        "description": "Stage 6 mois Java Spring Boot Angular SQL Git REST API débutant accepté Bac+5",
        "skills": ["Java", "Spring Boot", "Angular", "SQL", "Git", "REST API"],
        "exp_requise": 0, "edu_requise": 5,
    },
    {
        "titre": "Stage Développeur Data Science Python",
        "description": "Stage 6 mois Python machine learning Pandas scikit-learn SQL Jupyter Bac+5 en cours",
        "skills": ["Python", "Machine Learning", "Pandas", "scikit-learn", "SQL", "Git"],
        "exp_requise": 0, "edu_requise": 4,
    },

    # ── UX/UI Design ─────────────────────────────────────────────────────────
    {
        "titre": "Designer UX/UI",
        "description": "CDI Figma Adobe XD Sketch prototypage wireframes design system HTML CSS 2 ans Bac+3",
        "skills": ["Figma", "Adobe XD", "UX Design", "UI Design", "HTML", "CSS", "Sketch"],
        "exp_requise": 2, "edu_requise": 3,
    },

    # ── Chef de projet / Management ──────────────────────────────────────────
    {
        "titre": "Chef de Projet IT Agile",
        "description": "CDI gestion de projet Agile Scrum Jira management équipe technique planning budget 4 ans Bac+5",
        "skills": ["Gestion de projet", "Scrum", "Agile", "Jira", "Management", "Planning"],
        "exp_requise": 4, "edu_requise": 5,
    },

    # ── Marketing / Commercial ───────────────────────────────────────────────
    {
        "titre": "Responsable Marketing Digital",
        "description": "CDI Google Ads SEO Facebook Ads Google Analytics community management email marketing 2 ans Bac+3",
        "skills": ["Google Ads", "SEO", "Facebook Ads", "Google Analytics", "Community Management"],
        "exp_requise": 2, "edu_requise": 3,
    },
    {
        "titre": "Commercial B2B Tech",
        "description": "CDI vente B2B prospection négociation CRM Salesforce présentation PowerPoint relation client IT 3 ans Bac+3",
        "skills": ["Vente B2B", "CRM", "Salesforce", "Négociation", "PowerPoint", "Excel"],
        "exp_requise": 3, "edu_requise": 3,
    },

    # ── Finance / RH ─────────────────────────────────────────────────────────
    {
        "titre": "Comptable Contrôleur de Gestion",
        "description": "CDI comptabilité contrôle de gestion Excel SAP Power BI reporting bilan budget 3 ans Bac+5",
        "skills": ["Comptabilité", "Excel", "SAP", "Power BI", "Contrôle de gestion", "Budget"],
        "exp_requise": 3, "edu_requise": 5,
    },
    {
        "titre": "Chargé RH Recrutement",
        "description": "CDI recrutement sourcing LinkedIn ATS entretiens gestion administrative RH paie 2 ans Bac+3",
        "skills": ["Recrutement", "Sourcing", "LinkedIn", "RH", "Entretiens", "Excel", "Communication"],
        "exp_requise": 2, "edu_requise": 3,
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATS — 50 profils couvrant tous les niveaux et domaines
# ═══════════════════════════════════════════════════════════════════════════════
CANDIDATS = [
    # ── Backend Python ────────────────────────────────────────────────────────
    {
        "nom": "Senior Backend Python FastAPI",
        "cv_text": "Ingénieur backend Python FastAPI PostgreSQL Docker Redis SQLAlchemy Git REST API pytest CI/CD microservices 6 ans Bac+5 ingénieur informatique",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "SQLAlchemy", "Git", "REST API", "pytest"],
        "exp_years": 6, "edu_level": 5,
    },
    {
        "nom": "Mid Backend Python Django",
        "cv_text": "Développeur Python Django REST Framework PostgreSQL Celery Docker Redis Git REST API pytest 2 ans Bac+5 master génie logiciel",
        "skills": ["Python", "Django", "PostgreSQL", "Docker", "Redis", "Git", "REST API", "Celery"],
        "exp_years": 2, "edu_level": 5,
    },
    {
        "nom": "Junior Python Flask",
        "cv_text": "Développeur junior Python Flask MySQL Git HTML CSS REST API SQL 1 an Bac+3 licence informatique",
        "skills": ["Python", "Flask", "MySQL", "Git", "HTML", "CSS", "SQL"],
        "exp_years": 1, "edu_level": 3,
    },
    {
        "nom": "Python Data + Backend",
        "cv_text": "Ingénieur Python FastAPI Pandas NumPy PostgreSQL Docker ML scikit-learn Git REST API 3 ans Bac+5",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Pandas", "NumPy", "scikit-learn", "Git"],
        "exp_years": 3, "edu_level": 5,
    },

    # ── Backend Java ─────────────────────────────────────────────────────────
    {
        "nom": "Senior Java Spring Boot",
        "cv_text": "Ingénieur Java Spring Boot JPA Hibernate MySQL Docker Kubernetes Git CI/CD Angular TypeScript REST API microservices 5 ans Bac+5",
        "skills": ["Java", "Spring Boot", "MySQL", "Docker", "Kubernetes", "Git", "Angular", "TypeScript", "REST API"],
        "exp_years": 5, "edu_level": 5,
    },
    {
        "nom": "Mid Java Spring",
        "cv_text": "Développeur Java Spring Boot REST API Maven Docker PostgreSQL Git SQL JUnit 3 ans Bac+5",
        "skills": ["Java", "Spring Boot", "PostgreSQL", "Maven", "Docker", "Git", "REST API"],
        "exp_years": 3, "edu_level": 5,
    },
    {
        "nom": "Junior Java Angular Stage",
        "cv_text": "Étudiant ingénieur Java Spring Boot Angular SQL Git REST API stage fin études Bac+5 en cours",
        "skills": ["Java", "Spring Boot", "Angular", "SQL", "Git", "REST API"],
        "exp_years": 0, "edu_level": 4,
    },

    # ── Backend Node.js ───────────────────────────────────────────────────────
    {
        "nom": "Senior Node.js Express",
        "cv_text": "Développeur Node.js Express TypeScript MongoDB PostgreSQL Docker Redis JWT REST API Git 4 ans Bac+3",
        "skills": ["Node.js", "Express", "TypeScript", "MongoDB", "Docker", "Redis", "Git", "REST API"],
        "exp_years": 4, "edu_level": 3,
    },
    {
        "nom": "Full Stack Node React",
        "cv_text": "Développeur full stack React Node.js Express MongoDB PostgreSQL Docker TypeScript Git REST API 3 ans Bac+5",
        "skills": ["React", "Node.js", "TypeScript", "MongoDB", "PostgreSQL", "Docker", "Git", "REST API"],
        "exp_years": 3, "edu_level": 5,
    },

    # ── Backend PHP ───────────────────────────────────────────────────────────
    {
        "nom": "Développeur PHP Laravel Senior",
        "cv_text": "Développeur PHP Laravel MySQL Docker Git JavaScript REST API Vue.js Composer 3 ans Bac+3",
        "skills": ["PHP", "Laravel", "MySQL", "Docker", "Git", "JavaScript", "REST API"],
        "exp_years": 3, "edu_level": 3,
    },
    {
        "nom": "Junior PHP Symfony",
        "cv_text": "Développeur PHP Symfony MySQL Git JavaScript HTML CSS Twig 1 an Bac+3",
        "skills": ["PHP", "Symfony", "MySQL", "Git", "JavaScript", "HTML", "CSS"],
        "exp_years": 1, "edu_level": 3,
    },

    # ── Backend .NET ──────────────────────────────────────────────────────────
    {
        "nom": "Développeur .NET C# Senior",
        "cv_text": "Développeur C# ASP.NET Core Entity Framework SQL Server Docker Azure REST API Git 4 ans Bac+5",
        "skills": ["C#", ".NET", "ASP.NET", "SQL Server", "Docker", "Azure", "Git", "REST API"],
        "exp_years": 4, "edu_level": 5,
    },

    # ── Frontend React ────────────────────────────────────────────────────────
    {
        "nom": "Senior Frontend React",
        "cv_text": "Développeur frontend React TypeScript JavaScript HTML CSS Tailwind Next.js Redux Git REST API Figma 3 ans Bac+3",
        "skills": ["React", "TypeScript", "JavaScript", "HTML", "CSS", "Tailwind", "Next.js", "Git", "REST API"],
        "exp_years": 3, "edu_level": 3,
    },
    {
        "nom": "Mid Frontend React Redux",
        "cv_text": "Développeur React Redux TypeScript JavaScript CSS Tailwind Git REST API 2 ans Bac+5",
        "skills": ["React", "TypeScript", "JavaScript", "CSS", "Tailwind", "Git", "REST API"],
        "exp_years": 2, "edu_level": 5,
    },
    {
        "nom": "Junior Frontend JavaScript",
        "cv_text": "Développeur web JavaScript HTML CSS Vue.js Bootstrap Git 1 an Bac+2",
        "skills": ["JavaScript", "HTML", "CSS", "Vue.js", "Bootstrap", "Git"],
        "exp_years": 1, "edu_level": 2,
    },

    # ── Frontend Angular ──────────────────────────────────────────────────────
    {
        "nom": "Senior Angular TypeScript",
        "cv_text": "Développeur Angular TypeScript RxJS NgRx HTML CSS SCSS REST API Docker Git 4 ans Bac+5",
        "skills": ["Angular", "TypeScript", "JavaScript", "HTML", "CSS", "RxJS", "Git", "REST API"],
        "exp_years": 4, "edu_level": 5,
    },

    # ── Mobile ────────────────────────────────────────────────────────────────
    {
        "nom": "Développeur Flutter Senior",
        "cv_text": "Développeur mobile Flutter Dart Firebase REST API Git Android iOS GetX Bloc state management 3 ans Bac+3",
        "skills": ["Flutter", "Dart", "Firebase", "REST API", "Git", "Android", "iOS"],
        "exp_years": 3, "edu_level": 3,
    },
    {
        "nom": "Développeur Android Kotlin",
        "cv_text": "Développeur Android Kotlin Jetpack Compose Retrofit Room Firebase MVVM Git REST API 3 ans Bac+5",
        "skills": ["Android", "Kotlin", "Jetpack Compose", "Retrofit", "Firebase", "Git", "REST API"],
        "exp_years": 3, "edu_level": 5,
    },
    {
        "nom": "Junior Mobile React Native",
        "cv_text": "Développeur mobile React Native JavaScript Firebase REST API Git Expo 1 an Bac+3",
        "skills": ["React Native", "JavaScript", "Firebase", "REST API", "Git"],
        "exp_years": 1, "edu_level": 3,
    },

    # ── Data Science / ML ─────────────────────────────────────────────────────
    {
        "nom": "Senior Data Scientist",
        "cv_text": "Data scientist Python TensorFlow PyTorch scikit-learn Pandas NumPy SQL Docker MLflow Git machine learning NLP 4 ans Bac+5",
        "skills": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "MLflow", "Git"],
        "exp_years": 4, "edu_level": 5,
    },
    {
        "nom": "ML Engineer MLOps",
        "cv_text": "Ingénieur ML Python PyTorch MLflow Kubernetes Docker CI/CD AWS SageMaker déploiement modèles 3 ans Bac+5",
        "skills": ["Python", "PyTorch", "MLflow", "Docker", "Kubernetes", "AWS", "CI/CD", "Git"],
        "exp_years": 3, "edu_level": 5,
    },
    {
        "nom": "Data Analyst Junior",
        "cv_text": "Data analyst Python Pandas NumPy SQL scikit-learn Excel Power BI Tableau Git statistiques 1 an Bac+3",
        "skills": ["Python", "Pandas", "NumPy", "SQL", "scikit-learn", "Excel", "Power BI", "Git"],
        "exp_years": 1, "edu_level": 3,
    },
    {
        "nom": "Data Analyst Senior BI",
        "cv_text": "Data analyst SQL Power BI Tableau Excel Python Pandas ETL dashboards KPI reporting 4 ans Bac+5",
        "skills": ["SQL", "Power BI", "Tableau", "Excel", "Python", "Pandas", "Git"],
        "exp_years": 4, "edu_level": 5,
    },
    {
        "nom": "Data Engineer Spark",
        "cv_text": "Data engineer Python Apache Spark Kafka Airflow Docker AWS S3 PostgreSQL ETL pipelines Hadoop 5 ans Bac+5",
        "skills": ["Python", "Apache Spark", "Kafka", "Airflow", "Docker", "AWS", "SQL", "Git"],
        "exp_years": 5, "edu_level": 5,
    },
    {
        "nom": "Stage Data Science",
        "cv_text": "Étudiant data science Python machine learning Pandas scikit-learn SQL Jupyter TensorFlow stage fin études",
        "skills": ["Python", "Machine Learning", "Pandas", "scikit-learn", "SQL", "Git"],
        "exp_years": 0, "edu_level": 4,
    },

    # ── DevOps / Cloud ────────────────────────────────────────────────────────
    {
        "nom": "Senior DevOps AWS",
        "cv_text": "Ingénieur DevOps AWS Docker Kubernetes Terraform Ansible CI/CD Jenkins GitLab Linux Prometheus Grafana 6 ans Bac+5",
        "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "Ansible", "CI/CD", "Linux", "Git"],
        "exp_years": 6, "edu_level": 5,
    },
    {
        "nom": "Ingénieur Cloud Azure",
        "cv_text": "Ingénieur cloud Azure AKS Terraform Docker CI/CD Azure DevOps Linux PowerShell 4 ans Bac+5",
        "skills": ["Azure", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux", "Git", "PowerShell"],
        "exp_years": 4, "edu_level": 5,
    },
    {
        "nom": "SRE Kubernetes Linux",
        "cv_text": "Site reliability engineer Kubernetes Prometheus Grafana Linux Python Bash Docker CI/CD incident management monitoring 5 ans Bac+5",
        "skills": ["Kubernetes", "Prometheus", "Grafana", "Linux", "Python", "Docker", "CI/CD", "Git"],
        "exp_years": 5, "edu_level": 5,
    },
    {
        "nom": "Junior DevOps CI/CD",
        "cv_text": "Ingénieur DevOps junior Docker Linux Git CI/CD GitLab Jenkins Ansible 1 an Bac+5",
        "skills": ["Docker", "Linux", "CI/CD", "Git", "Ansible", "Kubernetes"],
        "exp_years": 1, "edu_level": 5,
    },

    # ── Cybersécurité ─────────────────────────────────────────────────────────
    {
        "nom": "Analyste Sécurité Pentester",
        "cv_text": "Analyste cybersécurité Kali Linux Burp Suite Metasploit Python Linux réseaux OWASP ISO 27001 pentest 3 ans Bac+5",
        "skills": ["Cybersécurité", "Pentest", "Kali Linux", "Python", "Linux", "Réseaux", "Burp Suite"],
        "exp_years": 3, "edu_level": 5,
    },
    {
        "nom": "Analyste SOC SIEM",
        "cv_text": "Analyste SOC SIEM Splunk QRadar réseaux firewall IDS IPS Linux incident response cybersécurité 2 ans Bac+5",
        "skills": ["SIEM", "Splunk", "Réseaux", "Linux", "Cybersécurité", "Firewall", "QRadar"],
        "exp_years": 2, "edu_level": 5,
    },

    # ── QA / Test ─────────────────────────────────────────────────────────────
    {
        "nom": "Ingénieur QA Automation",
        "cv_text": "Ingénieur QA Selenium Python pytest Cypress Java JUnit REST API Git CI/CD test automatisé 3 ans Bac+5",
        "skills": ["Selenium", "Python", "pytest", "REST API", "Git", "CI/CD", "Java"],
        "exp_years": 3, "edu_level": 5,
    },

    # ── UX/UI Design ─────────────────────────────────────────────────────────
    {
        "nom": "Designer UX/UI Figma",
        "cv_text": "Designer UX/UI Figma Adobe XD Sketch prototypage wireframes design system HTML CSS user research 3 ans Bac+3",
        "skills": ["Figma", "Adobe XD", "UX Design", "UI Design", "HTML", "CSS", "Sketch"],
        "exp_years": 3, "edu_level": 3,
    },

    # ── Gestion de projet ─────────────────────────────────────────────────────
    {
        "nom": "Chef de Projet IT Scrum",
        "cv_text": "Chef de projet IT Agile Scrum Jira management équipe technique planning budget delivery 5 ans Bac+5",
        "skills": ["Gestion de projet", "Scrum", "Agile", "Jira", "Management", "Planning"],
        "exp_years": 5, "edu_level": 5,
    },

    # ── Marketing / Commercial ────────────────────────────────────────────────
    {
        "nom": "Marketing Digital Expert",
        "cv_text": "Responsable marketing digital Google Ads SEO Facebook Ads Google Analytics community management email marketing Excel 3 ans Bac+3",
        "skills": ["Google Ads", "SEO", "Facebook Ads", "Google Analytics", "Community Management", "Excel"],
        "exp_years": 3, "edu_level": 3,
    },
    {
        "nom": "Commercial B2B Salesforce",
        "cv_text": "Commercial B2B prospection négociation CRM Salesforce présentation PowerPoint relation client IT SaaS 4 ans Bac+3",
        "skills": ["Vente B2B", "CRM", "Salesforce", "Négociation", "PowerPoint", "Excel"],
        "exp_years": 4, "edu_level": 3,
    },
    {
        "nom": "Junior Marketing Digital",
        "cv_text": "Assistant marketing digital SEO réseaux sociaux content création Adobe Photoshop Canva Google Analytics 1 an Bac+3",
        "skills": ["SEO", "Community Management", "Google Analytics", "Canva", "Excel"],
        "exp_years": 1, "edu_level": 3,
    },

    # ── Finance / Comptabilité ────────────────────────────────────────────────
    {
        "nom": "Comptable Confirmé SAP",
        "cv_text": "Comptable Excel SAP comptabilité générale bilan TVA audit fiscalité budget contrôle gestion 5 ans Bac+5",
        "skills": ["Comptabilité", "Excel", "SAP", "Contrôle de gestion", "Budget", "Fiscalité"],
        "exp_years": 5, "edu_level": 5,
    },
    {
        "nom": "Contrôleur de Gestion",
        "cv_text": "Contrôleur de gestion Excel Power BI SAP reporting analyse financière budget prévisionnel KPI 4 ans Bac+5",
        "skills": ["Comptabilité", "Excel", "Power BI", "SAP", "Budget", "Contrôle de gestion"],
        "exp_years": 4, "edu_level": 5,
    },

    # ── RH ────────────────────────────────────────────────────────────────────
    {
        "nom": "Chargé RH Recrutement IT",
        "cv_text": "Chargé RH recrutement IT sourcing LinkedIn ATS entretiens gestion administrative paie GPEC 3 ans Bac+3",
        "skills": ["Recrutement", "Sourcing", "LinkedIn", "RH", "Entretiens", "Excel", "Communication"],
        "exp_years": 3, "edu_level": 3,
    },

    # ── Hors domaine (pour apprendre le "pas de match") ──────────────────────
    {
        "nom": "Médecin Généraliste",
        "cv_text": "Médecin généraliste consultation diagnostic traitement patients santé hôpital clinique 8 ans Bac+8",
        "skills": ["Médecine", "Diagnostic", "Santé", "Consultation"],
        "exp_years": 8, "edu_level": 8,
    },
    {
        "nom": "Enseignant Mathématiques",
        "cv_text": "Professeur mathématiques lycée collège pédagogie cours préparation baccalauréat 5 ans Bac+5",
        "skills": ["Mathématiques", "Pédagogie", "Enseignement", "Excel"],
        "exp_years": 5, "edu_level": 5,
    },
    {
        "nom": "Juriste Droit des Affaires",
        "cv_text": "Juriste droit des affaires contrats propriété intellectuelle conformité RGPD audit juridique 4 ans Bac+5",
        "skills": ["Droit", "Contrats", "RGPD", "Conformité", "Audit juridique"],
        "exp_years": 4, "edu_level": 5,
    },
    {
        "nom": "Ingénieur Civil BTP",
        "cv_text": "Ingénieur génie civil BTP chantier construction béton armé AutoCAD Revit gestion travaux 5 ans Bac+5",
        "skills": ["Génie civil", "BTP", "AutoCAD", "Revit", "Gestion de chantier"],
        "exp_years": 5, "edu_level": 5,
    },
    {
        "nom": "Commercial Vente Retail",
        "cv_text": "Commercial vente retail prospection CRM PowerPoint Excel relation client négociation 4 ans Bac+3",
        "skills": ["CRM", "Négociation", "Excel", "PowerPoint", "Vente"],
        "exp_years": 4, "edu_level": 3,
    },
    {
        "nom": "Étudiant Première Année",
        "cv_text": "Étudiant première année informatique Python bases algorithmique HTML CSS débutant",
        "skills": ["Python", "HTML", "CSS"],
        "exp_years": 0, "edu_level": 1,
    },
]


# ── Fonctions label ──────────────────────────────────────────────────────────
def skill_overlap(offer_skills: list, cv_skills: list) -> float:
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
    """Label objectif intelligent — pénalités multiplicatives pour hors-domaine et formation."""
    s_skills  = skill_overlap(offre["skills"], candidat["skills"])

    req_exp   = offre["exp_requise"]
    s_exp     = 1.0 if req_exp <= 0 else min(1.0, candidat["exp_years"] / max(req_exp, 1))

    req_edu   = offre.get("edu_requise", 0)
    cand_edu  = candidat.get("edu_level", 0)
    s_edu     = 1.0 if req_edu <= 0 else min(1.0, cand_edu / max(req_edu, 1))

    # Score de base
    base = s_skills * 0.55 + s_exp * 0.25 + s_edu * 0.20

    # ── Pénalité multiplicative domaine ──────────────────────────────────────
    # Médecin → IT, financier → frontend, juriste → DevOps : quasi 0
    # Le modèle APPREND que skills_raw très faible = hors-domaine
    if s_skills < 0.10:
        base *= 0.12    # < 10% skills : complètement hors-domaine
    elif s_skills < 0.20:
        base *= 0.30    # 10-20% skills : domaine très éloigné
    elif s_skills < 0.35:
        base *= 0.60    # 20-35% skills : mismatch significatif

    # ── Pénalité formation manquante (uniquement si sous-qualifié) ───────────
    edu_gap = req_edu - cand_edu
    if edu_gap >= 3:
        base *= 0.55    # Bac+2 pour poste Bac+5 : pénalité forte
    elif edu_gap >= 2:
        base *= 0.72    # Bac+3 pour poste Bac+5
    elif edu_gap >= 1:
        base *= 0.88    # léger écart

    return round(max(0.02, min(0.95, base)), 4)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  Generation dataset MLP Fusion v3.0  [7 features + labels intelligents]")
    print(f"  {len(OFFRES)} offres x {len(CANDIDATS)} candidats = {len(OFFRES)*len(CANDIDATS)} paires")
    print("=" * 65)

    print("\n[1/2] Chargement BGE-M3...")
    scorer_bge = BERTMatchingScorer()
    scorer_bge._ensure_loaded()
    scorer_bge._ensure_reranker_loaded()
    if not scorer_bge.ready:
        print("[ERREUR] BGE-M3 non disponible.")
        sys.exit(1)
    print(f"[OK] BGE-M3 charge")

    print("\n[2/2] Chargement BERT v2...")
    scorer_v2 = BERTMatchingScorer(model_name=BERT_V2_PATH)
    scorer_v2._ensure_loaded()
    scorer_v2._disable_mlp = True
    if not scorer_v2.ready:
        print(f"[ERREUR] BERT v2 non disponible : {BERT_V2_PATH}")
        sys.exit(1)
    print(f"[OK] BERT v2 charge")

    total = len(OFFRES) * len(CANDIDATS)
    print(f"\n[INFO] Generation de {total} paires...\n")

    rows = []
    done = 0

    for offre in OFFRES:
        offer_mock = _MockOffer(offre)
        for cand in CANDIDATS:
            cand_mock = _MockCandidate(cand)

            _, details_bge = scorer_bge.score(offer_mock, cand_mock)
            _, details_v2  = scorer_v2.score(offer_mock, cand_mock)

            sem_bge  = details_bge.get("semantique",  50) / 100
            comp_bge = details_bge.get("competences", 50) / 100
            exp_bge  = details_bge.get("experience",  50) / 100
            form_bge = details_bge.get("formation",   50) / 100
            sem_v2   = details_v2.get("semantique",   50) / 100

            # Nouvelles features discriminantes
            skills_raw   = skill_overlap(offre["skills"], cand["skills"])
            req_edu      = offre.get("edu_requise", 0)
            cand_edu     = cand.get("edu_level", 0)
            edu_gap_norm = round(max(-1.0, min(1.0, (req_edu - cand_edu) / 5.0)), 4)

            label = compute_label(offre, cand)

            rows.append({
                "offre":      offre["titre"],
                "candidat":   cand["nom"],
                "sem_bge":    round(sem_bge,    6),
                "comp_bge":   round(comp_bge,   6),
                "exp_bge":    round(exp_bge,    6),
                "form_bge":   round(form_bge,   6),
                "sem_v2":     round(sem_v2,     6),
                "skills_raw": round(skills_raw, 4),
                "edu_gap":    edu_gap_norm,
                "label":      label,
            })

            done += 1
            if done % 50 == 0 or done <= 5:
                print(
                    f"  [{done:4d}/{total}] {offre['titre'][:25]:<25}"
                    f" + {cand['nom']:<30}"
                    f"  sk_raw={skills_raw:.2f} sem_v2={sem_v2:.2f} label={label:.2f}"
                )

    fieldnames = ["offre", "candidat", "sem_bge", "comp_bge", "exp_bge", "form_bge", "sem_v2", "skills_raw", "edu_gap", "label"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[OK] {len(rows)} paires sauvegardees -> {OUT_CSV}")
    print("Lancez maintenant : .venv-10\\Scripts\\python backend/scripts/train_mlp_fusion.py")


if __name__ == "__main__":
    main()
