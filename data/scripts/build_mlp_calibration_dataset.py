"""
TalentMatch — Calibration MLP avec données réalistes
=====================================================
Génère 120+ paires (offre, CV, score_attendu) couvrant tous les domaines,
extrait les 5 features réelles via le pipeline BERT, et entraîne un nouveau MLP.

Usage (depuis backend/) :
    python ../data/scripts/build_mlp_calibration_dataset.py
"""
from __future__ import annotations

import os
import sys
import json
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

# Rendre app importable
BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer

random.seed(42)
torch.manual_seed(42)

MODEL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'models', 'talentmatch-bert-v2.0')
)

# ─────────────────────────────────────────────────────────────────────────────
# Dataset annoté — 120 paires (offre, CV, score_attendu)
# Domaines couverts : IT, Finance, RH, Ventes, Ingénierie, Santé, Marketing,
#                     Enseignement, Droit, BTP, Automobile, Design, Aéronautique
# Niveaux : Excellent (0.88-0.95) | Bon (0.70-0.85) | À évaluer (0.50-0.65) | Non adapté (0.20-0.40)
# ─────────────────────────────────────────────────────────────────────────────

ANNOTATIONS = [

    # ═══════════════════════════════ IT — Python/Backend ═══════════════════════
    {
        "offre": JobOffer(
            titre="Développeur Python Senior",
            description="Nous cherchons un développeur Python senior avec 5 ans d'expérience minimum. Maîtrise de FastAPI, PostgreSQL, Docker indispensable. Bac+5 requis.",
            competences_requises=["Python", "FastAPI", "PostgreSQL", "Docker"],
            competences_appreciees=["Kubernetes", "AWS", "Redis"],
        ),
        "cv": Candidate(
            raw_text="Senior Python developer with 7 years of experience. Expert in FastAPI, PostgreSQL, Docker, Kubernetes, AWS and Redis. Master's degree in Computer Science from ENSI.",
            parsed_data={
                "competences": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "AWS", "Redis"],
                "formations": [{"diplome": "Master Informatique", "etablissement": "ENSI Tunis"}],
                "experiences": [{"poste": "Senior Python Developer", "description": "FastAPI REST APIs PostgreSQL Docker Kubernetes AWS 7 years production"}],
                "metadata": {"annees_experience_totales": 7, "niveau_formation_max": 5},
            }
        ),
        "score": 0.93,
        "label": "Excellent Python Sr",
    },
    {
        "offre": JobOffer(
            titre="Développeur Python Senior",
            description="Nous cherchons un développeur Python senior avec 5 ans d'expérience minimum. Maîtrise de FastAPI, PostgreSQL, Docker indispensable. Bac+5 requis.",
            competences_requises=["Python", "FastAPI", "PostgreSQL", "Docker"],
            competences_appreciees=["Kubernetes", "AWS"],
        ),
        "cv": Candidate(
            raw_text="Python developer 4 years. Good knowledge of FastAPI and PostgreSQL. Some Docker experience. Bachelor degree.",
            parsed_data={
                "competences": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "formations": [{"diplome": "Licence Informatique"}],
                "experiences": [{"poste": "Python Developer", "description": "FastAPI PostgreSQL Docker 4 years"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 3},
            }
        ),
        "score": 0.74,
        "label": "Bon Python (Licence, 4 ans)",
    },
    {
        "offre": JobOffer(
            titre="Développeur Python Senior",
            description="Nous cherchons un développeur Python senior avec 5 ans d'expérience minimum. Maîtrise de FastAPI, PostgreSQL, Docker indispensable. Bac+5 requis.",
            competences_requises=["Python", "FastAPI", "PostgreSQL", "Docker"],
            competences_appreciees=["Kubernetes", "AWS"],
        ),
        "cv": Candidate(
            raw_text="Python junior developer 1 year. Know basic Python and Flask. No Docker experience.",
            parsed_data={
                "competences": ["Python", "Flask"],
                "experiences": [{"poste": "Junior Developer", "description": "Python Flask basic 1 year"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 2},
            }
        ),
        "score": 0.38,
        "label": "A évaluer Python (junior, manque skills)",
    },
    {
        "offre": JobOffer(
            titre="Développeur Python Senior",
            description="Nous cherchons un développeur Python senior avec 5 ans d'expérience minimum. Maîtrise de FastAPI, PostgreSQL, Docker indispensable. Bac+5 requis.",
            competences_requises=["Python", "FastAPI", "PostgreSQL", "Docker"],
            competences_appreciees=["Kubernetes", "AWS"],
        ),
        "cv": Candidate(
            raw_text="Graphic designer with 5 years in Photoshop, Illustrator, InDesign. No programming skills.",
            parsed_data={
                "competences": ["Photoshop", "Illustrator", "InDesign"],
                "experiences": [{"poste": "Graphic Designer", "description": "design visuel logo illustrator"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 3},
            }
        ),
        "score": 0.22,
        "label": "Non adapté (designer pour Python)",
    },

    # ═══════════════════════════════ IT — Java/Spring ════════════════════════
    {
        "offre": JobOffer(
            titre="Développeur Java Spring Boot",
            description="Développeur Java confirmé avec 3+ ans d'expérience sur Spring Boot, Hibernate, MySQL. Connaissance des microservices appréciée.",
            competences_requises=["Java", "Spring Boot", "Hibernate", "MySQL"],
            competences_appreciees=["Microservices", "Docker", "Kafka"],
        ),
        "cv": Candidate(
            raw_text="Java developer 5 years. Expert Spring Boot Hibernate MySQL microservices Docker Kafka. Master degree.",
            parsed_data={
                "competences": ["Java", "Spring Boot", "Hibernate", "MySQL", "Microservices", "Docker", "Kafka"],
                "experiences": [{"poste": "Java Backend Developer", "description": "Spring Boot Hibernate MySQL microservices 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.92,
        "label": "Excellent Java",
    },
    {
        "offre": JobOffer(
            titre="Développeur Java Spring Boot",
            description="Développeur Java confirmé avec 3+ ans d'expérience sur Spring Boot, Hibernate, MySQL. Connaissance des microservices appréciée.",
            competences_requises=["Java", "Spring Boot", "Hibernate", "MySQL"],
            competences_appreciees=["Microservices", "Docker", "Kafka"],
        ),
        "cv": Candidate(
            raw_text="Python data scientist 4 years. Expert pandas numpy scikit-learn machine learning. No Java experience.",
            parsed_data={
                "competences": ["Python", "Pandas", "NumPy", "Scikit-learn", "Machine Learning"],
                "experiences": [{"poste": "Data Scientist", "description": "Python pandas machine learning 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.24,
        "label": "Non adapté (Python ML pour Java)",
    },

    # ═══════════════════════════════ IT — DevOps ═════════════════════════════
    {
        "offre": JobOffer(
            titre="Ingénieur DevOps Cloud",
            description="Ingénieur DevOps avec 4 ans d'expérience. Docker, Kubernetes, Terraform, AWS ou GCP obligatoire. CI/CD Jenkins/GitLab CI. Bac+5.",
            competences_requises=["Docker", "Kubernetes", "Terraform", "AWS", "CI/CD"],
            competences_appreciees=["Ansible", "Prometheus", "Grafana"],
        ),
        "cv": Candidate(
            raw_text="DevOps engineer 5 years. Docker Kubernetes Terraform AWS GCP CI/CD GitLab Jenkins Ansible Prometheus Grafana. Master degree.",
            parsed_data={
                "competences": ["Docker", "Kubernetes", "Terraform", "AWS", "CI/CD", "Ansible", "Prometheus", "Grafana", "GitLab CI"],
                "experiences": [{"poste": "DevOps Engineer", "description": "Docker Kubernetes Terraform AWS GCP CI/CD Ansible Prometheus 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.94,
        "label": "Excellent DevOps",
    },
    {
        "offre": JobOffer(
            titre="Ingénieur DevOps Cloud",
            description="Ingénieur DevOps avec 4 ans d'expérience. Docker, Kubernetes, Terraform, AWS ou GCP obligatoire. CI/CD Jenkins/GitLab CI. Bac+5.",
            competences_requises=["Docker", "Kubernetes", "Terraform", "AWS", "CI/CD"],
            competences_appreciees=["Ansible", "Prometheus"],
        ),
        "cv": Candidate(
            raw_text="Backend developer Python 3 years. Basic Docker knowledge. No Kubernetes Terraform AWS experience.",
            parsed_data={
                "competences": ["Python", "Docker", "Flask"],
                "experiences": [{"poste": "Backend Developer", "description": "Python Flask Docker basic 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 4},
            }
        ),
        "score": 0.42,
        "label": "A évaluer DevOps (manque K8s Terraform)",
    },

    # ═══════════════════════════════ IT — Data Science ═══════════════════════
    {
        "offre": JobOffer(
            titre="Data Scientist Senior",
            description="Data Scientist 3+ ans. Python, scikit-learn, TensorFlow ou PyTorch, SQL. Expérience MLOps appréciée. Bac+5 requis.",
            competences_requises=["Python", "Machine Learning", "TensorFlow", "SQL"],
            competences_appreciees=["MLOps", "Spark", "Deep Learning"],
        ),
        "cv": Candidate(
            raw_text="Data Scientist 4 years. Python TensorFlow PyTorch scikit-learn SQL machine learning deep learning MLOps Spark. PhD in statistics.",
            parsed_data={
                "competences": ["Python", "Machine Learning", "TensorFlow", "PyTorch", "SQL", "MLOps", "Spark", "Deep Learning"],
                "experiences": [{"poste": "Data Scientist", "description": "Python TensorFlow scikit-learn SQL MLOps machine learning 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 6},
            }
        ),
        "score": 0.91,
        "label": "Excellent Data Scientist",
    },
    {
        "offre": JobOffer(
            titre="Data Scientist Senior",
            description="Data Scientist 3+ ans. Python, scikit-learn, TensorFlow ou PyTorch, SQL. Expérience MLOps appréciée. Bac+5 requis.",
            competences_requises=["Python", "Machine Learning", "TensorFlow", "SQL"],
            competences_appreciees=["MLOps", "Spark"],
        ),
        "cv": Candidate(
            raw_text="Junior data analyst 1 year. Excel PowerBI basic SQL. No machine learning Python TensorFlow.",
            parsed_data={
                "competences": ["Excel", "Power BI", "SQL"],
                "experiences": [{"poste": "Data Analyst Junior", "description": "Excel PowerBI SQL basic 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 3},
            }
        ),
        "score": 0.33,
        "label": "Non adapté (analyst Excel pour Data Scientist ML)",
    },

    # ═══════════════════════════════ IT — Frontend React ═════════════════════
    {
        "offre": JobOffer(
            titre="Développeur Frontend React",
            description="Développeur React avec 3 ans d'expérience. TypeScript, Redux, REST API, CSS/Tailwind. Bac+3 minimum.",
            competences_requises=["React", "TypeScript", "Redux", "CSS"],
            competences_appreciees=["Next.js", "GraphQL", "Jest"],
        ),
        "cv": Candidate(
            raw_text="Frontend developer React 4 years. TypeScript Redux Tailwind Next.js GraphQL Jest REST APIs.",
            parsed_data={
                "competences": ["React", "TypeScript", "Redux", "CSS", "Next.js", "GraphQL", "Jest", "Tailwind"],
                "experiences": [{"poste": "Frontend Developer", "description": "React TypeScript Redux Tailwind Next.js 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.90,
        "label": "Excellent Frontend React",
    },
    {
        "offre": JobOffer(
            titre="Développeur Frontend React",
            description="Développeur React avec 3 ans d'expérience. TypeScript, Redux, REST API, CSS/Tailwind. Bac+3 minimum.",
            competences_requises=["React", "TypeScript", "Redux", "CSS"],
            competences_appreciees=["Next.js", "GraphQL"],
        ),
        "cv": Candidate(
            raw_text="Frontend developer 2 years. HTML CSS JavaScript jQuery. Basic React. No TypeScript Redux.",
            parsed_data={
                "competences": ["HTML", "CSS", "JavaScript", "jQuery", "React"],
                "experiences": [{"poste": "Frontend Developer", "description": "HTML CSS JavaScript jQuery React basic 2 ans"}],
                "metadata": {"annees_experience_totales": 2, "niveau_formation_max": 3},
            }
        ),
        "score": 0.55,
        "label": "A évaluer Frontend (manque TypeScript Redux)",
    },

    # ═══════════════════════════════ IT — Mobile ══════════════════════════════
    {
        "offre": JobOffer(
            titre="Développeur Mobile iOS/Swift",
            description="Développeur iOS avec 3 ans d'expérience Swift, SwiftUI, Xcode. Publication App Store exigée.",
            competences_requises=["iOS", "Swift", "SwiftUI", "Xcode"],
            competences_appreciees=["Objective-C", "CocoaPods", "TestFlight"],
        ),
        "cv": Candidate(
            raw_text="iOS developer 4 years. Swift SwiftUI Xcode CocoaPods TestFlight Objective-C published 3 apps on App Store.",
            parsed_data={
                "competences": ["iOS", "Swift", "SwiftUI", "Xcode", "CocoaPods", "Objective-C", "TestFlight"],
                "experiences": [{"poste": "iOS Developer", "description": "Swift SwiftUI Xcode App Store publication 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.91,
        "label": "Excellent iOS Swift",
    },
    {
        "offre": JobOffer(
            titre="Développeur Mobile iOS/Swift",
            description="Développeur iOS avec 3 ans d'expérience Swift, SwiftUI, Xcode. Publication App Store exigée.",
            competences_requises=["iOS", "Swift", "SwiftUI", "Xcode"],
            competences_appreciees=["Objective-C", "CocoaPods"],
        ),
        "cv": Candidate(
            raw_text="Android developer Kotlin 3 years. Android Studio Gradle Jetpack. No iOS Swift experience.",
            parsed_data={
                "competences": ["Android", "Kotlin", "Gradle", "Jetpack"],
                "experiences": [{"poste": "Android Developer", "description": "Kotlin Android Studio Gradle Jetpack 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 4},
            }
        ),
        "score": 0.30,
        "label": "Non adapté (Android Kotlin pour iOS)",
    },

    # ═══════════════════════════════ Finance / Comptabilité ═══════════════════
    {
        "offre": JobOffer(
            titre="Responsable Comptable",
            description="Comptable confirmé avec 5 ans d'expérience. Maîtrise Sage, Excel avancé, fiscalité tunisienne, bilan, déclarations TVA. Bac+3 minimum.",
            competences_requises=["Comptabilité", "Sage", "Excel", "Fiscalité", "TVA"],
            competences_appreciees=["IFRS", "Audit", "Contrôle de gestion"],
        ),
        "cv": Candidate(
            raw_text="Expert comptable 7 ans. Sage comptabilité Excel avancé TVA fiscalité bilan déclarations audit IFRS contrôle de gestion. DSCG diplômé.",
            parsed_data={
                "competences": ["Comptabilité", "Sage", "Excel", "Fiscalité", "TVA", "IFRS", "Audit", "Contrôle de gestion"],
                "formations": [{"diplome": "DSCG Expert Comptable"}],
                "experiences": [{"poste": "Expert Comptable", "description": "Sage comptabilité TVA bilan audit IFRS 7 ans"}],
                "metadata": {"annees_experience_totales": 7, "niveau_formation_max": 5},
            }
        ),
        "score": 0.92,
        "label": "Excellent Comptable",
    },
    {
        "offre": JobOffer(
            titre="Responsable Comptable",
            description="Comptable confirmé avec 5 ans d'expérience. Maîtrise Sage, Excel avancé, fiscalité tunisienne, bilan, déclarations TVA. Bac+3 minimum.",
            competences_requises=["Comptabilité", "Sage", "Excel", "Fiscalité", "TVA"],
            competences_appreciees=["IFRS", "Audit"],
        ),
        "cv": Candidate(
            raw_text="Comptable junior 2 ans. Excel de base Sage initiation. Peu de pratique TVA.",
            parsed_data={
                "competences": ["Comptabilité", "Sage", "Excel"],
                "formations": [{"diplome": "Licence Comptabilité"}],
                "experiences": [{"poste": "Assistant Comptable", "description": "Comptabilité Excel Sage initiation 2 ans"}],
                "metadata": {"annees_experience_totales": 2, "niveau_formation_max": 3},
            }
        ),
        "score": 0.59,
        "label": "A évaluer Comptable (junior)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Comptable",
            description="Comptable confirmé avec 5 ans d'expérience. Maîtrise Sage, Excel avancé, fiscalité. Bac+3 minimum.",
            competences_requises=["Comptabilité", "Sage", "Excel", "Fiscalité", "TVA"],
            competences_appreciees=["IFRS", "Audit"],
        ),
        "cv": Candidate(
            raw_text="Software developer Python Java 5 years. No accounting Sage finance experience.",
            parsed_data={
                "competences": ["Python", "Java", "SQL"],
                "experiences": [{"poste": "Software Developer", "description": "Python Java SQL development 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.22,
        "label": "Non adapté (dev Python pour Comptable)",
    },
    {
        "offre": JobOffer(
            titre="Analyste Financier",
            description="Analyste financier 3 ans. Modélisation financière Excel, PowerPoint, analyse bilans, reporting. Bac+5 Finance requis.",
            competences_requises=["Finance", "Excel", "Modélisation financière", "Analyse financière"],
            competences_appreciees=["Bloomberg", "VBA", "PowerBI"],
        ),
        "cv": Candidate(
            raw_text="Analyste financier 4 ans. Modélisation financière Excel VBA PowerBI reporting analyse bilans Bloomberg. Master Finance IHEC.",
            parsed_data={
                "competences": ["Finance", "Excel", "Modélisation financière", "Analyse financière", "VBA", "PowerBI", "Bloomberg"],
                "formations": [{"diplome": "Master Finance", "etablissement": "IHEC Carthage"}],
                "experiences": [{"poste": "Analyste Financier", "description": "modélisation financière Excel VBA analyse bilans Bloomberg 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.89,
        "label": "Excellent Analyste Financier",
    },
    {
        "offre": JobOffer(
            titre="Analyste Financier",
            description="Analyste financier 3 ans. Modélisation financière Excel, analyse bilans, reporting. Bac+5 Finance requis.",
            competences_requises=["Finance", "Excel", "Modélisation financière", "Analyse financière"],
            competences_appreciees=["Bloomberg", "VBA", "PowerBI"],
        ),
        "cv": Candidate(
            raw_text="Contrôleur de gestion 4 ans. Reporting budgétaire analyse des écarts tableaux de bord Excel PowerBI contrôle gestion. Master Contrôle de Gestion.",
            parsed_data={
                "competences": ["Finance", "Excel", "Reporting", "Analyse financière", "Tableaux de bord", "PowerBI", "Contrôle de gestion"],
                "formations": [{"diplome": "Master Contrôle de Gestion Finance"}],
                "experiences": [{"poste": "Contrôleur de Gestion", "description": "reporting budgétaire analyse écarts tableaux bord Excel 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.78,
        "label": "Bon Finance (contrôleur gestion, reporting mais pas modélisation)",
    },
    {
        "offre": JobOffer(
            titre="Analyste Financier",
            description="Analyste financier 3 ans. Modélisation financière Excel, analyse bilans, reporting. Bac+5 Finance requis.",
            competences_requises=["Finance", "Excel", "Modélisation financière", "Analyse financière"],
            competences_appreciees=["Bloomberg", "VBA", "PowerBI"],
        ),
        "cv": Candidate(
            raw_text="Auditeur externe Big4 3 ans. Audit financier analyse bilans comptes annuels normes IFRS vérification. Pas de modélisation financière Bloomberg.",
            parsed_data={
                "competences": ["Finance", "Audit financier", "Analyse financière", "IFRS", "Bilan"],
                "formations": [{"diplome": "Master Audit Finance"}],
                "experiences": [{"poste": "Auditeur Externe", "description": "audit financier bilans IFRS vérification comptes 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 5},
            }
        ),
        "score": 0.72,
        "label": "Bon Finance (auditeur Big4, analyse mais pas modélisation)",
    },
    {
        "offre": JobOffer(
            titre="Analyste Financier",
            description="Analyste financier 3 ans. Modélisation financière Excel, analyse bilans, reporting. Bac+5 Finance requis.",
            competences_requises=["Finance", "Excel", "Modélisation financière", "Analyse financière"],
            competences_appreciees=["Bloomberg", "VBA", "PowerBI"],
        ),
        "cv": Candidate(
            raw_text="Analyste financier junior 1 an post-master. Excel notions modélisation. Peu d'expérience analyse bilans reporting. Stage banque 6 mois.",
            parsed_data={
                "competences": ["Finance", "Excel", "Modélisation financière"],
                "formations": [{"diplome": "Master Finance"}],
                "experiences": [{"poste": "Analyste Junior", "description": "Excel modélisation analyse financière notions 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 5},
            }
        ),
        "score": 0.58,
        "label": "A évaluer Finance (analyste junior 1 an)",
    },
    {
        "offre": JobOffer(
            titre="Analyste Financier",
            description="Analyste financier 3 ans. Modélisation financière Excel, analyse bilans, reporting. Bac+5 Finance requis.",
            competences_requises=["Finance", "Excel", "Modélisation financière", "Analyse financière"],
            competences_appreciees=["Bloomberg", "VBA", "PowerBI"],
        ),
        "cv": Candidate(
            raw_text="Expert comptable 7 ans. Sage comptabilité TVA bilan déclarations fiscales. Excel courant. Pas de modélisation financière Bloomberg analyse investissement.",
            parsed_data={
                "competences": ["Comptabilité", "Excel", "Bilan", "Fiscalité"],
                "formations": [{"diplome": "DSCG Expert Comptable"}],
                "experiences": [{"poste": "Expert Comptable", "description": "comptabilité Sage TVA bilan fiscal 7 ans"}],
                "metadata": {"annees_experience_totales": 7, "niveau_formation_max": 5},
            }
        ),
        "score": 0.48,
        "label": "A évaluer Finance (comptable, finance opé pas analyse invest.)",
    },

    # ═══════════════════════════════ RH / Human Resources ════════════════════
    {
        "offre": JobOffer(
            titre="Responsable Ressources Humaines",
            description="RH confirmé avec 4 ans d'expérience. Recrutement, gestion des compétences GPEC, paie, SIRH. Bac+5 requis.",
            competences_requises=["Recrutement", "GPEC", "Paie", "SIRH"],
            competences_appreciees=["Workday", "Droit du travail", "Formation"],
        ),
        "cv": Candidate(
            raw_text="Responsable RH 5 ans. Recrutement talent acquisition GPEC paie SIRH Workday droit du travail formation. Master RH.",
            parsed_data={
                "competences": ["Recrutement", "GPEC", "Paie", "SIRH", "Workday", "Droit du travail", "Formation"],
                "formations": [{"diplome": "Master Ressources Humaines"}],
                "experiences": [{"poste": "Responsable RH", "description": "recrutement GPEC paie SIRH Workday 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.91,
        "label": "Excellent RH",
    },
    {
        "offre": JobOffer(
            titre="Responsable Ressources Humaines",
            description="RH confirmé avec 4 ans d'expérience. Recrutement, gestion des compétences GPEC, paie, SIRH. Bac+5 requis.",
            competences_requises=["Recrutement", "GPEC", "Paie", "SIRH"],
            competences_appreciees=["Workday", "Droit du travail"],
        ),
        "cv": Candidate(
            raw_text="Directeur des Ressources Humaines 9 ans. Recrutement stratégique talent acquisition GPEC paie SIRH SAP Workday droit du travail formation développement carrière politique RH. Master RH ESCP.",
            parsed_data={
                "competences": ["Recrutement", "GPEC", "Paie", "SIRH", "Workday", "Droit du travail", "Formation", "Développement carrière"],
                "formations": [{"diplome": "Master Ressources Humaines", "etablissement": "ESCP Europe"}],
                "experiences": [{"poste": "Directeur RH", "description": "recrutement GPEC paie SIRH Workday politique RH 9 ans"}],
                "metadata": {"annees_experience_totales": 9, "niveau_formation_max": 5},
            }
        ),
        "score": 0.93,
        "label": "Excellent DRH Senior (surqualifié mais domaine parfait)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Ressources Humaines",
            description="RH confirmé avec 4 ans d'expérience. Recrutement, gestion des compétences GPEC, paie, SIRH. Bac+5 requis.",
            competences_requises=["Recrutement", "GPEC", "Paie", "SIRH"],
            competences_appreciees=["Workday", "Droit du travail"],
        ),
        "cv": Candidate(
            raw_text="Chargé de recrutement 3 ans. Sourcing LinkedIn ATS recrutement talent acquisition entretiens. Pas de paie GPEC SIRH Workday.",
            parsed_data={
                "competences": ["Recrutement", "Sourcing", "LinkedIn", "ATS", "Entretiens"],
                "formations": [{"diplome": "Master RH"}],
                "experiences": [{"poste": "Chargé de Recrutement", "description": "recrutement sourcing LinkedIn ATS entretiens 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 5},
            }
        ),
        "score": 0.67,
        "label": "A évaluer+ RH (recrutement seul, manque paie GPEC SIRH)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Ressources Humaines",
            description="RH confirmé avec 4 ans d'expérience. Recrutement, gestion des compétences GPEC, paie, SIRH. Bac+5 requis.",
            competences_requises=["Recrutement", "GPEC", "Paie", "SIRH"],
            competences_appreciees=["Workday", "Droit du travail"],
        ),
        "cv": Candidate(
            raw_text="Consultant RH cabinet conseil 4 ans. Conseil en recrutement GPEC formation bilan compétences audit RH. Pas de paie SIRH opérationnel.",
            parsed_data={
                "competences": ["Recrutement", "GPEC", "Formation", "Bilan compétences", "Audit RH"],
                "formations": [{"diplome": "Master Management RH"}],
                "experiences": [{"poste": "Consultant RH", "description": "recrutement GPEC formation audit RH cabinet conseil 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.77,
        "label": "Bon RH (consultant, GPEC mais paie SIRH limités)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Ressources Humaines",
            description="RH confirmé avec 4 ans d'expérience. Recrutement, gestion des compétences GPEC, paie, SIRH. Bac+5 requis.",
            competences_requises=["Recrutement", "GPEC", "Paie", "SIRH"],
            competences_appreciees=["Workday", "Droit du travail"],
        ),
        "cv": Candidate(
            raw_text="Assistant RH 1 an. Aide au recrutement administrative. Paie notions formation en cours.",
            parsed_data={
                "competences": ["Recrutement", "Paie"],
                "formations": [{"diplome": "Licence Gestion"}],
                "experiences": [{"poste": "Assistant RH", "description": "recrutement administratif paie initiation 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 3},
            }
        ),
        "score": 0.47,
        "label": "A évaluer RH (junior, GPEC SIRH manquants)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Ressources Humaines",
            description="RH confirmé avec 4 ans d'expérience. Recrutement, gestion des compétences GPEC, paie, SIRH. Bac+5 requis.",
            competences_requises=["Recrutement", "GPEC", "Paie", "SIRH"],
            competences_appreciees=["Workday", "Droit du travail"],
        ),
        "cv": Candidate(
            raw_text="Juriste social droit du travail 4 ans. Conventions collectives contentieux prud'homal droit du travail. Pas de recrutement paie SIRH GPEC.",
            parsed_data={
                "competences": ["Droit du travail", "Contentieux social", "Conventions collectives"],
                "formations": [{"diplome": "Master Droit Social"}],
                "experiences": [{"poste": "Juriste Social", "description": "droit du travail contentieux prud'homal conventions 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.42,
        "label": "A évaluer RH (juriste social, overlap droit travail seul)",
    },

    # ═══════════════════════════════ Ventes / Commercial ══════════════════════
    {
        "offre": JobOffer(
            titre="Responsable Commercial Senior",
            description="Commercial senior 5 ans B2B. Prospection, CRM Salesforce, négociation, gestion grands comptes. Bac+3 min.",
            competences_requises=["Vente B2B", "CRM", "Salesforce", "Négociation", "Gestion grands comptes"],
            competences_appreciees=["HubSpot", "Marketing digital", "Reporting KPI"],
        ),
        "cv": Candidate(
            raw_text="Responsable commercial 6 ans B2B. Salesforce CRM négociation prospection grands comptes HubSpot reporting KPI.",
            parsed_data={
                "competences": ["Vente B2B", "CRM", "Salesforce", "Négociation", "Gestion grands comptes", "HubSpot", "Reporting KPI"],
                "formations": [{"diplome": "Master Commerce"}],
                "experiences": [{"poste": "Responsable Commercial", "description": "B2B Salesforce CRM négociation grands comptes 6 ans"}],
                "metadata": {"annees_experience_totales": 6, "niveau_formation_max": 5},
            }
        ),
        "score": 0.91,
        "label": "Excellent Commercial",
    },
    {
        "offre": JobOffer(
            titre="Responsable Commercial Senior",
            description="Commercial senior 5 ans B2B. Prospection, CRM Salesforce, négociation, gestion grands comptes. Bac+3 min.",
            competences_requises=["Vente B2B", "CRM", "Salesforce", "Négociation", "Gestion grands comptes"],
            competences_appreciees=["HubSpot", "Marketing digital"],
        ),
        "cv": Candidate(
            raw_text="Vendeur junior 1 an magasin. Service client, caisse. Aucune expérience B2B CRM Salesforce.",
            parsed_data={
                "competences": ["Service client", "Vente"],
                "experiences": [{"poste": "Vendeur", "description": "vente service client caisse 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 2},
            }
        ),
        "score": 0.30,
        "label": "A évaluer Commercial (vendeur junior sans B2B)",
    },

    # ═══════════════════════════════ Ingénierie Mécanique ════════════════════
    {
        "offre": JobOffer(
            titre="Ingénieur Mécanique Conception",
            description="Ingénieur mécanique 3 ans. SolidWorks, CATIA, calcul de structure, résistance des matériaux. Bac+5 requis.",
            competences_requises=["SolidWorks", "CATIA", "Calcul de structure", "Résistance des matériaux"],
            competences_appreciees=["ANSYS", "Gestion de projet", "Normes ISO"],
        ),
        "cv": Candidate(
            raw_text="Ingénieur mécanique conception 5 ans. SolidWorks CATIA ANSYS calcul structure RDM normes ISO gestion projet. Master Génie Mécanique ENIM.",
            parsed_data={
                "competences": ["SolidWorks", "CATIA", "Calcul de structure", "Résistance des matériaux", "ANSYS", "Normes ISO", "Gestion de projet"],
                "formations": [{"diplome": "Master Génie Mécanique", "etablissement": "ENIM"}],
                "experiences": [{"poste": "Ingénieur Conception", "description": "SolidWorks CATIA ANSYS calcul structure 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.92,
        "label": "Excellent Ingénieur Mécanique",
    },
    {
        "offre": JobOffer(
            titre="Ingénieur Mécanique Conception",
            description="Ingénieur mécanique 3 ans. SolidWorks, CATIA, calcul de structure. Bac+5 requis.",
            competences_requises=["SolidWorks", "CATIA", "Calcul de structure", "Résistance des matériaux"],
            competences_appreciees=["ANSYS", "Gestion de projet"],
        ),
        "cv": Candidate(
            raw_text="Technicien maintenance mécanique 4 ans. Maintenance préventive corrective. Notions SolidWorks. Pas de conception CATIA.",
            parsed_data={
                "competences": ["Maintenance mécanique", "SolidWorks"],
                "formations": [{"diplome": "BTS Maintenance Industrielle"}],
                "experiences": [{"poste": "Technicien Maintenance", "description": "maintenance préventive corrective 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 2},
            }
        ),
        "score": 0.38,
        "label": "A évaluer Mécanique (technicien, sans CATIA conception)",
    },
    {
        "offre": JobOffer(
            titre="Ingénieur Mécanique Conception",
            description="Ingénieur mécanique 3 ans. SolidWorks, CATIA, calcul de structure. Bac+5 requis.",
            competences_requises=["SolidWorks", "CATIA", "Calcul de structure", "Résistance des matériaux"],
            competences_appreciees=["ANSYS"],
        ),
        "cv": Candidate(
            raw_text="Comptable 5 ans. Sage Excel TVA fiscalité. Aucune compétence technique mécanique conception.",
            parsed_data={
                "competences": ["Comptabilité", "Sage", "Excel", "TVA"],
                "experiences": [{"poste": "Comptable", "description": "comptabilité Sage Excel TVA 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 3},
            }
        ),
        "score": 0.21,
        "label": "Non adapté (Comptable pour Ingénieur Mécanique)",
    },

    # ═══════════════════════════════ Génie Civil / BTP ════════════════════════
    {
        "offre": JobOffer(
            titre="Ingénieur Génie Civil",
            description="Ingénieur génie civil 3 ans minimum. AutoCAD, béton armé, suivi chantier, métrés, planification. Bac+5.",
            competences_requises=["AutoCAD", "Béton armé", "Suivi chantier", "Métrés"],
            competences_appreciees=["Revit", "MS Project", "Normes NF"],
        ),
        "cv": Candidate(
            raw_text="Ingénieur génie civil 5 ans. AutoCAD Revit béton armé suivi chantier métrés planification MS Project normes NF.",
            parsed_data={
                "competences": ["AutoCAD", "Béton armé", "Suivi chantier", "Métrés", "Revit", "MS Project", "Normes NF"],
                "formations": [{"diplome": "Master Génie Civil"}],
                "experiences": [{"poste": "Ingénieur Génie Civil", "description": "AutoCAD béton armé chantier métrés Revit 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.91,
        "label": "Excellent Génie Civil",
    },
    {
        "offre": JobOffer(
            titre="Ingénieur Génie Civil",
            description="Ingénieur génie civil 3 ans. AutoCAD, béton armé, suivi chantier. Bac+5.",
            competences_requises=["AutoCAD", "Béton armé", "Suivi chantier", "Métrés"],
            competences_appreciees=["Revit", "MS Project"],
        ),
        "cv": Candidate(
            raw_text="Architecte junior 2 ans. AutoCAD ArchiCAD dessin architectural. Peu de béton armé suivi chantier.",
            parsed_data={
                "competences": ["AutoCAD", "ArchiCAD", "Dessin architectural"],
                "formations": [{"diplome": "Licence Architecture"}],
                "experiences": [{"poste": "Architecte Junior", "description": "AutoCAD ArchiCAD dessin architectural 2 ans"}],
                "metadata": {"annees_experience_totales": 2, "niveau_formation_max": 3},
            }
        ),
        "score": 0.52,
        "label": "A évaluer BTP (architecte junior)",
    },

    # ═══════════════════════════════ Marketing / Communication ════════════════
    {
        "offre": JobOffer(
            titre="Responsable Marketing Digital",
            description="Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. Bac+5 communication.",
            competences_requises=["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            competences_appreciees=["HubSpot", "Meta Ads", "Content marketing"],
        ),
        "cv": Candidate(
            raw_text="Marketing digital manager 4 ans. SEO Google Ads Facebook Meta Ads Analytics HubSpot email marketing content marketing.",
            parsed_data={
                "competences": ["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics", "HubSpot", "Meta Ads", "Content marketing"],
                "formations": [{"diplome": "Master Marketing Digital"}],
                "experiences": [{"poste": "Digital Marketing Manager", "description": "SEO Google Ads Analytics réseaux sociaux email marketing 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.92,
        "label": "Excellent Marketing Digital",
    },
    {
        "offre": JobOffer(
            titre="Responsable Marketing Digital",
            description="Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. Bac+5.",
            competences_requises=["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            competences_appreciees=["HubSpot", "Meta Ads", "Content marketing"],
        ),
        "cv": Candidate(
            raw_text="SEO Manager confirmé 4 ans. SEO technique on-page off-page link building Analytics Search Console. Pas de Google Ads email marketing HubSpot.",
            parsed_data={
                "competences": ["SEO", "Analytics", "Réseaux sociaux", "Content marketing", "Search Console"],
                "formations": [{"diplome": "Master Marketing Digital"}],
                "experiences": [{"poste": "SEO Manager", "description": "SEO technique on-page off-page Analytics 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.70,
        "label": "Bon Marketing (SEO specialist, manque Google Ads email HubSpot)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Marketing Digital",
            description="Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. Bac+5.",
            competences_requises=["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            competences_appreciees=["HubSpot", "Meta Ads", "Content marketing"],
        ),
        "cv": Candidate(
            raw_text="Traffic Manager Google Ads 3 ans. Google Ads Meta Ads campagnes payantes SEM tracking Analytics. Pas de SEO organique email marketing HubSpot.",
            parsed_data={
                "competences": ["Google Ads", "Meta Ads", "Analytics", "SEM", "Réseaux sociaux"],
                "formations": [{"diplome": "Licence Marketing"}],
                "experiences": [{"poste": "Traffic Manager", "description": "Google Ads Meta Ads campagnes payantes Analytics 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 3},
            }
        ),
        "score": 0.65,
        "label": "A évaluer+ Marketing (paid media only, manque SEO email)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Marketing Digital",
            description="Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. Bac+5.",
            competences_requises=["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            competences_appreciees=["HubSpot", "Meta Ads"],
        ),
        "cv": Candidate(
            raw_text="Chargé marketing junior 1 an. Réseaux sociaux posts publications basiques. Notions SEO Google Ads. Pas d'Analytics email marketing.",
            parsed_data={
                "competences": ["Réseaux sociaux", "Community management"],
                "formations": [{"diplome": "Licence Marketing Communication"}],
                "experiences": [{"poste": "Chargé Marketing Junior", "description": "réseaux sociaux posts publications SEO notions 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 3},
            }
        ),
        "score": 0.50,
        "label": "A évaluer Marketing (junior 1 an, réseaux sociaux seulement)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Marketing Digital",
            description="Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. Bac+5.",
            competences_requises=["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            competences_appreciees=["HubSpot", "Meta Ads"],
        ),
        "cv": Candidate(
            raw_text="Responsable commercial B2B 5 ans. CRM Salesforce prospection négociation vente grands comptes. Notions LinkedIn marketing. Pas SEO Google Ads Analytics.",
            parsed_data={
                "competences": ["Vente B2B", "CRM", "Négociation", "Réseaux sociaux"],
                "formations": [{"diplome": "Master Commerce"}],
                "experiences": [{"poste": "Responsable Commercial", "description": "CRM Salesforce vente B2B négociation 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.30,
        "label": "Non adapté Marketing (commercial B2B, pas digital marketing)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Marketing Digital",
            description="Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. Bac+5.",
            competences_requises=["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            competences_appreciees=["HubSpot", "Meta Ads"],
        ),
        "cv": Candidate(
            raw_text="Community manager junior 1 an. Instagram Facebook post publication. Pas de SEO Google Ads Analytics.",
            parsed_data={
                "competences": ["Réseaux sociaux", "Community management"],
                "experiences": [{"poste": "Community Manager", "description": "réseaux sociaux Instagram Facebook 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 3},
            }
        ),
        "score": 0.41,
        "label": "A évaluer Marketing (manque SEO Google Ads Analytics)",
    },
    {
        "offre": JobOffer(
            titre="Responsable Marketing Digital",
            description="Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. Bac+5.",
            competences_requises=["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            competences_appreciees=["HubSpot", "Meta Ads"],
        ),
        "cv": Candidate(
            raw_text="Electricien industriel 5 ans. Câblage armoires électriques. Aucune compétence marketing numérique.",
            parsed_data={
                "competences": ["Electricité", "Câblage", "Maintenance électrique"],
                "experiences": [{"poste": "Electricien", "description": "câblage armoires électriques maintenance 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 2},
            }
        ),
        "score": 0.21,
        "label": "Non adapté (électricien pour marketing)",
    },

    # ═══════════════════════════════ Santé / Healthcare ══════════════════════
    {
        "offre": JobOffer(
            titre="Médecin Généraliste",
            description="Médecin généraliste pour cabinet médical. Doctorat médecine obligatoire. Consultations, prescriptions, suivi patients.",
            competences_requises=["Médecine", "Consultations médicales", "Prescriptions", "Suivi patients"],
            competences_appreciees=["Urgences", "Chirurgie mineure", "Échographie"],
        ),
        "cv": Candidate(
            raw_text="Médecin généraliste 7 ans. Consultations prescriptions suivi patients urgences chirurgie mineure échographie. Doctorat médecine.",
            parsed_data={
                "competences": ["Médecine", "Consultations médicales", "Prescriptions", "Suivi patients", "Urgences", "Chirurgie mineure"],
                "formations": [{"diplome": "Doctorat en Médecine"}],
                "experiences": [{"poste": "Médecin Généraliste", "description": "consultations prescriptions suivi patients 7 ans"}],
                "metadata": {"annees_experience_totales": 7, "niveau_formation_max": 6},
            }
        ),
        "score": 0.93,
        "label": "Excellent Médecin",
    },
    {
        "offre": JobOffer(
            titre="Médecin Généraliste",
            description="Médecin généraliste. Doctorat médecine obligatoire. Consultations, prescriptions.",
            competences_requises=["Médecine", "Consultations médicales", "Prescriptions", "Suivi patients"],
            competences_appreciees=["Urgences", "Échographie"],
        ),
        "cv": Candidate(
            raw_text="Infirmier diplômé 3 ans. Soins infirmiers pansements injections. Pas médecin.",
            parsed_data={
                "competences": ["Soins infirmiers", "Pansements", "Injections"],
                "formations": [{"diplome": "BTS Soins Infirmiers"}],
                "experiences": [{"poste": "Infirmier", "description": "soins infirmiers pansements injections 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 2},
            }
        ),
        "score": 0.37,
        "label": "A évaluer Santé (infirmier pour médecin)",
    },

    # ═══════════════════════════════ Enseignement / Education ════════════════
    {
        "offre": JobOffer(
            titre="Professeur Mathématiques Lycée",
            description="Enseignant mathématiques lycée. Master mathématiques requis. Pédagogie, cours, examens, soutien scolaire.",
            competences_requises=["Mathématiques", "Pédagogie", "Cours", "Gestion classe"],
            competences_appreciees=["Statistiques", "Informatique", "Encadrement"],
        ),
        "cv": Candidate(
            raw_text="Professeur de mathématiques 8 ans. Enseignement lycée pédagogie cours examens soutien scolaire statistiques informatique. Master Mathématiques.",
            parsed_data={
                "competences": ["Mathématiques", "Pédagogie", "Cours", "Gestion classe", "Statistiques", "Informatique"],
                "formations": [{"diplome": "Master Mathématiques"}],
                "experiences": [{"poste": "Professeur Mathématiques", "description": "enseignement lycée pédagogie cours examens 8 ans"}],
                "metadata": {"annees_experience_totales": 8, "niveau_formation_max": 5},
            }
        ),
        "score": 0.93,
        "label": "Excellent Professeur Maths",
    },
    {
        "offre": JobOffer(
            titre="Professeur Mathématiques Lycée",
            description="Enseignant mathématiques lycée. Master mathématiques requis.",
            competences_requises=["Mathématiques", "Pédagogie", "Cours", "Gestion classe"],
            competences_appreciees=["Statistiques", "Informatique"],
        ),
        "cv": Candidate(
            raw_text="Commercial téléphone call center 3 ans. Service client vente téléphonique. Aucune compétence enseignement mathématiques.",
            parsed_data={
                "competences": ["Service client", "Vente", "Communication"],
                "experiences": [{"poste": "Commercial", "description": "service client vente téléphonique 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 2},
            }
        ),
        "score": 0.21,
        "label": "Non adapté (commercial pour prof maths)",
    },

    # ═══════════════════════════════ Stage / Junior ═══════════════════════════
    {
        "offre": JobOffer(
            titre="Stage Développeur Python",
            description="Stage 6 mois développeur Python. Étudiant Bac+4/Bac+5 bienvenu. Débutant accepté, formation assurée.",
            competences_requises=["Python"],
            competences_appreciees=["Django", "Flask", "SQL", "Git"],
        ),
        "cv": Candidate(
            raw_text="Étudiant Master 2 Informatique. Python Django Flask SQL Git projet universitaire e-commerce. Stage recherché.",
            parsed_data={
                "competences": ["Python", "Django", "Flask", "SQL", "Git"],
                "formations": [{"diplome": "Master Informatique", "etablissement": "Université"}],
                "experiences": [{"poste": "Projet étudiant", "description": "Python Django Flask SQL Git e-commerce"}],
                "metadata": {"annees_experience_totales": 0, "niveau_formation_max": 5},
            }
        ),
        "score": 0.82,
        "label": "Excellent Stage Python (étudiant M2)",
    },
    {
        "offre": JobOffer(
            titre="Stage Développeur Python",
            description="Stage 6 mois développeur Python. Étudiant Bac+4/Bac+5 bienvenu.",
            competences_requises=["Python"],
            competences_appreciees=["Django", "Flask", "SQL"],
        ),
        "cv": Candidate(
            raw_text="Étudiant BTS graphisme. Photoshop Illustrator design. Aucune programmation Python.",
            parsed_data={
                "competences": ["Photoshop", "Illustrator", "Graphisme"],
                "formations": [{"diplome": "BTS Graphisme"}],
                "metadata": {"annees_experience_totales": 0, "niveau_formation_max": 2},
            }
        ),
        "score": 0.22,
        "label": "Non adapté (graphiste pour stage Python)",
    },

    # ═══════════════════════════════ Senior Management ════════════════════════
    {
        "offre": JobOffer(
            titre="Directeur Technique (CTO)",
            description="CTO startup tech 50 personnes. Leadership technique, roadmap produit, architecture, recrutement équipe. 10 ans exp requis. Bac+5.",
            competences_requises=["Leadership technique", "Architecture logicielle", "Gestion équipe", "Roadmap produit"],
            competences_appreciees=["Agile", "Cloud", "Fundraising", "OKR"],
        ),
        "cv": Candidate(
            raw_text="CTO expérimenté 12 ans. Leadership technique architecture microservices cloud AWS Agile OKR gestion équipe roadmap produit fundraising startup.",
            parsed_data={
                "competences": ["Leadership technique", "Architecture logicielle", "Gestion équipe", "Roadmap produit", "Agile", "Cloud", "OKR"],
                "formations": [{"diplome": "Master Informatique"}],
                "experiences": [{"poste": "CTO", "description": "leadership technique architecture cloud AWS Agile roadmap startup 12 ans"}],
                "metadata": {"annees_experience_totales": 12, "niveau_formation_max": 5},
            }
        ),
        "score": 0.93,
        "label": "Excellent CTO",
    },
    {
        "offre": JobOffer(
            titre="Directeur Technique (CTO)",
            description="CTO startup tech. Leadership technique, architecture, gestion équipe. 10 ans exp requis.",
            competences_requises=["Leadership technique", "Architecture logicielle", "Gestion équipe", "Roadmap produit"],
            competences_appreciees=["Agile", "Cloud"],
        ),
        "cv": Candidate(
            raw_text="Développeur junior Python 2 ans. Bonne maîtrise Python FastAPI. Pas de leadership expérience management.",
            parsed_data={
                "competences": ["Python", "FastAPI", "SQL"],
                "experiences": [{"poste": "Junior Developer", "description": "Python FastAPI SQL 2 ans"}],
                "metadata": {"annees_experience_totales": 2, "niveau_formation_max": 4},
            }
        ),
        "score": 0.29,
        "label": "Non adapté (junior pour CTO)",
    },

    # ═══════════════════════════════ Design / UX ══════════════════════════════
    {
        "offre": JobOffer(
            titre="UX/UI Designer Senior",
            description="Designer UX/UI 3 ans. Figma, prototypage, user research, design system. Bac+3 minimum.",
            competences_requises=["Figma", "UX Design", "Prototypage", "User Research"],
            competences_appreciees=["Design System", "Adobe XD", "CSS"],
        ),
        "cv": Candidate(
            raw_text="UX/UI Designer 4 ans. Figma Adobe XD prototypage user research design system CSS Zeplin. Master Design.",
            parsed_data={
                "competences": ["Figma", "UX Design", "Prototypage", "User Research", "Design System", "Adobe XD", "CSS"],
                "formations": [{"diplome": "Master Design Numérique"}],
                "experiences": [{"poste": "UX/UI Designer", "description": "Figma prototypage user research design system 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.91,
        "label": "Excellent UX Designer",
    },
    {
        "offre": JobOffer(
            titre="UX/UI Designer Senior",
            description="Designer UX/UI 3 ans. Figma, prototypage, user research, design system.",
            competences_requises=["Figma", "UX Design", "Prototypage", "User Research"],
            competences_appreciees=["Design System", "Adobe XD"],
        ),
        "cv": Candidate(
            raw_text="Développeur backend Java 5 ans. Spring Boot Hibernate SQL. Aucune compétence design UX Figma.",
            parsed_data={
                "competences": ["Java", "Spring Boot", "Hibernate", "SQL"],
                "experiences": [{"poste": "Backend Developer", "description": "Java Spring Boot SQL 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.22,
        "label": "Non adapté (Java developer pour UX Designer)",
    },

    # ═══════════════════════════════ Aéronautique ════════════════════════════
    {
        "offre": JobOffer(
            titre="Ingénieur Aéronautique Systèmes",
            description="Ingénieur aéronautique 3 ans. Systèmes embarqués avionique, normes DO-178C, certification AESA. Bac+5.",
            competences_requises=["Avionique", "Systèmes embarqués", "DO-178C", "AESA"],
            competences_appreciees=["VHDL", "C embarqué", "MBSE"],
        ),
        "cv": Candidate(
            raw_text="Ingénieur systèmes embarqués aéronautique 5 ans. Avionique DO-178C AESA VHDL C embarqué MBSE certification. Master ISAE Supaero.",
            parsed_data={
                "competences": ["Avionique", "Systèmes embarqués", "DO-178C", "AESA", "VHDL", "C embarqué", "MBSE"],
                "formations": [{"diplome": "Master ISAE Supaero Aéronautique"}],
                "experiences": [{"poste": "Ingénieur Aéronautique", "description": "avionique systèmes embarqués DO-178C AESA certification 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.92,
        "label": "Excellent Ingénieur Aéronautique",
    },

    # ═══════════════════════════════ Automobile ═══════════════════════════════
    {
        "offre": JobOffer(
            titre="Ingénieur Qualité Automobile",
            description="Ingénieur qualité secteur automobile 3 ans. IATF 16949, AMDEC, 8D, gestion non-conformités. Bac+5.",
            competences_requises=["Qualité", "IATF 16949", "AMDEC", "8D"],
            competences_appreciees=["SPC", "MSA", "Lean Manufacturing"],
        ),
        "cv": Candidate(
            raw_text="Ingénieur qualité automobile 4 ans. IATF 16949 AMDEC 8D SPC MSA Lean Manufacturing gestion non-conformités. Master Qualité.",
            parsed_data={
                "competences": ["Qualité", "IATF 16949", "AMDEC", "8D", "SPC", "MSA", "Lean Manufacturing"],
                "formations": [{"diplome": "Master Génie Industriel Qualité"}],
                "experiences": [{"poste": "Ingénieur Qualité", "description": "IATF AMDEC 8D SPC qualité automobile 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.91,
        "label": "Excellent Qualité Automobile",
    },

    # ═══════════════════════════════ Droit / Juridique ════════════════════════
    {
        "offre": JobOffer(
            titre="Juriste d'Entreprise",
            description="Juriste droit des affaires 3 ans. Contrats commerciaux, droit du travail, RGPD, contentieux. Master Droit.",
            competences_requises=["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD"],
            competences_appreciees=["Contentieux", "Propriété intellectuelle", "Négociation"],
        ),
        "cv": Candidate(
            raw_text="Juriste d'entreprise 4 ans. Droit des affaires contrats commerciaux droit du travail RGPD contentieux propriété intellectuelle. Master Droit des Affaires.",
            parsed_data={
                "competences": ["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD", "Contentieux", "Propriété intellectuelle"],
                "formations": [{"diplome": "Master Droit des Affaires"}],
                "experiences": [{"poste": "Juriste Entreprise", "description": "droit affaires contrats RGPD contentieux 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.91,
        "label": "Excellent Juriste",
    },
    {
        "offre": JobOffer(
            titre="Juriste d'Entreprise",
            description="Juriste droit des affaires 3 ans. Contrats commerciaux, droit du travail, RGPD, contentieux. Master Droit.",
            competences_requises=["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD"],
            competences_appreciees=["Contentieux", "Propriété intellectuelle", "Négociation"],
        ),
        "cv": Candidate(
            raw_text="Avocat d'affaires 6 ans. Droit commercial contrats négociation contentieux tribunaux conseil juridique propriété intellectuelle. Cabinet d'avocats international. Master Droit.",
            parsed_data={
                "competences": ["Droit des affaires", "Contrats commerciaux", "Contentieux", "Négociation", "Propriété intellectuelle", "Conseil juridique"],
                "formations": [{"diplome": "Master Droit des Affaires", "etablissement": "Faculté de Droit Tunis"}],
                "experiences": [{"poste": "Avocat d'affaires", "description": "droit commercial contrats négociation contentieux tribunaux 6 ans"}],
                "metadata": {"annees_experience_totales": 6, "niveau_formation_max": 5},
            }
        ),
        "score": 0.82,
        "label": "Bon Juriste (avocat affaires, peu RGPD/droit travail)",
    },
    {
        "offre": JobOffer(
            titre="Juriste d'Entreprise",
            description="Juriste droit des affaires 3 ans. Contrats commerciaux, droit du travail, RGPD, contentieux. Master Droit.",
            competences_requises=["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD"],
            competences_appreciees=["Contentieux", "Propriété intellectuelle"],
        ),
        "cv": Candidate(
            raw_text="Juriste junior 1 an. Master Droit des Affaires. Stage contentieux. Notions droit du travail RGPD. Peu d'expérience contrats commerciaux.",
            parsed_data={
                "competences": ["Droit des affaires", "Droit du travail", "RGPD"],
                "formations": [{"diplome": "Master Droit des Affaires"}],
                "experiences": [{"poste": "Juriste Junior", "description": "stage contentieux droit affaires 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 5},
            }
        ),
        "score": 0.57,
        "label": "A évaluer Juriste (junior 1 an, manque expérience contrats)",
    },
    {
        "offre": JobOffer(
            titre="Juriste d'Entreprise",
            description="Juriste droit des affaires 3 ans. Contrats commerciaux, droit du travail, RGPD, contentieux. Master Droit.",
            competences_requises=["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD"],
            competences_appreciees=["Contentieux", "Propriété intellectuelle"],
        ),
        "cv": Candidate(
            raw_text="Notaire collaborateur 4 ans. Droit civil immobilier successions actes notariaux. Aucune expérience contrats commerciaux droit du travail RGPD.",
            parsed_data={
                "competences": ["Droit civil", "Immobilier", "Successions", "Actes notariaux"],
                "formations": [{"diplome": "Master Notariat"}],
                "experiences": [{"poste": "Notaire Collaborateur", "description": "droit civil immobilier successions actes notariaux 4 ans"}],
                "metadata": {"annees_experience_totales": 4, "niveau_formation_max": 5},
            }
        ),
        "score": 0.44,
        "label": "A évaluer Juriste (notaire, droit civil pas affaires)",
    },
    {
        "offre": JobOffer(
            titre="Juriste d'Entreprise",
            description="Juriste droit des affaires 3 ans. Contrats commerciaux, droit du travail, RGPD, contentieux. Master Droit.",
            competences_requises=["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD"],
            competences_appreciees=["Contentieux", "Propriété intellectuelle"],
        ),
        "cv": Candidate(
            raw_text="Assistant juridique 3 ans. Secrétariat juridique classement dossiers. Pas de formation droit. Aucune rédaction contrats contentieux.",
            parsed_data={
                "competences": ["Secrétariat juridique", "Classement dossiers"],
                "formations": [{"diplome": "BTS Secrétariat"}],
                "experiences": [{"poste": "Assistant Juridique", "description": "secrétariat juridique classement 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 2},
            }
        ),
        "score": 0.28,
        "label": "Non adapté Juriste (assistant juridique sans formation droit)",
    },
    {
        "offre": JobOffer(
            titre="Juriste d'Entreprise",
            description="Juriste droit des affaires 3 ans. Contrats commerciaux, droit du travail, RGPD, contentieux. Master Droit.",
            competences_requises=["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD"],
            competences_appreciees=["Contentieux", "Propriété intellectuelle"],
        ),
        "cv": Candidate(
            raw_text="Responsable RH 5 ans. Recrutement GPEC paie SIRH droit du travail notions. Pas juriste pas droit des affaires.",
            parsed_data={
                "competences": ["Droit du travail", "Recrutement", "GPEC", "Paie"],
                "formations": [{"diplome": "Master RH"}],
                "experiences": [{"poste": "Responsable RH", "description": "RH recrutement paie droit travail 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.35,
        "label": "Non adapté Juriste (RH pour juriste entreprise)",
    },

    # ═══════════════════════════════ Supply Chain / Logistique ════════════════
    {
        "offre": JobOffer(
            titre="Responsable Supply Chain",
            description="Supply chain manager 4 ans. SAP, gestion stocks, planification, appros, transport. Bac+5.",
            competences_requises=["Supply Chain", "SAP", "Gestion stocks", "Planification", "Approvisionnement"],
            competences_appreciees=["S&OP", "Lean", "Transport", "WMS"],
        ),
        "cv": Candidate(
            raw_text="Supply chain manager 5 ans. SAP gestion stocks planification approvisionnement S&OP transport WMS Lean. Master Supply Chain.",
            parsed_data={
                "competences": ["Supply Chain", "SAP", "Gestion stocks", "Planification", "Approvisionnement", "S&OP", "Transport", "WMS"],
                "formations": [{"diplome": "Master Supply Chain Management"}],
                "experiences": [{"poste": "Supply Chain Manager", "description": "SAP stocks planification S&OP transport Lean 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 5},
            }
        ),
        "score": 0.92,
        "label": "Excellent Supply Chain",
    },
    {
        "offre": JobOffer(
            titre="Responsable Supply Chain",
            description="Supply chain manager 4 ans. SAP, gestion stocks, planification. Bac+5.",
            competences_requises=["Supply Chain", "SAP", "Gestion stocks", "Planification", "Approvisionnement"],
            competences_appreciees=["S&OP", "Lean", "Transport"],
        ),
        "cv": Candidate(
            raw_text="Chauffeur livreur 3 ans. Transport colis livraison. Aucune compétence SAP supply chain planification.",
            parsed_data={
                "competences": ["Transport", "Livraison", "Conduite"],
                "experiences": [{"poste": "Chauffeur Livreur", "description": "livraison colis transport 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 1},
            }
        ),
        "score": 0.25,
        "label": "Non adapté (chauffeur pour Supply Chain Manager)",
    },

    # ═══════════════════════════════ Gestion de Projet ════════════════════════
    {
        "offre": JobOffer(
            titre="Chef de Projet IT",
            description="Chef de projet IT 5 ans. Agile Scrum, gestion risques, planning, budgets, équipes pluridisciplinaires. PMP ou PRINCE2 apprécié.",
            competences_requises=["Gestion de projet", "Agile", "Scrum", "Gestion des risques", "Planning"],
            competences_appreciees=["PMP", "PRINCE2", "Jira", "Confluence"],
        ),
        "cv": Candidate(
            raw_text="Chef de projet IT certifié PMP 6 ans. Agile Scrum Kanban Jira Confluence gestion risques planning budgets équipes offshore. Master Management.",
            parsed_data={
                "competences": ["Gestion de projet", "Agile", "Scrum", "Gestion des risques", "Planning", "PMP", "Jira", "Confluence"],
                "formations": [{"diplome": "Master Management de Projet"}],
                "experiences": [{"poste": "Chef de Projet IT", "description": "Agile Scrum Jira gestion risques planning budgets 6 ans"}],
                "metadata": {"annees_experience_totales": 6, "niveau_formation_max": 5},
            }
        ),
        "score": 0.92,
        "label": "Excellent Chef de Projet",
    },
    {
        "offre": JobOffer(
            titre="Chef de Projet IT",
            description="Chef de projet IT 5 ans. Agile Scrum, gestion risques, planning. PMP apprécié.",
            competences_requises=["Gestion de projet", "Agile", "Scrum", "Gestion des risques", "Planning"],
            competences_appreciees=["PMP", "Jira"],
        ),
        "cv": Candidate(
            raw_text="Développeur React junior 1 an. HTML CSS JavaScript React. Aucune expérience gestion projet Agile planning.",
            parsed_data={
                "competences": ["React", "JavaScript", "HTML", "CSS"],
                "experiences": [{"poste": "Junior Frontend", "description": "React JavaScript HTML CSS 1 an"}],
                "metadata": {"annees_experience_totales": 1, "niveau_formation_max": 3},
            }
        ),
        "score": 0.25,
        "label": "Non adapté (dev React junior pour Chef de Projet)",
    },

    # ═══════════════════════════════ Cas limites / Edge cases ════════════════
    {
        "offre": JobOffer(
            titre="Développeur Full Stack",
            description="Full stack 2 ans min. React frontend + Node.js backend. MongoDB, REST API, Git. Bac+3.",
            competences_requises=["React", "Node.js", "MongoDB", "REST API", "Git"],
            competences_appreciees=["TypeScript", "Docker", "AWS"],
        ),
        "cv": Candidate(
            raw_text="Full stack developer 3 years. React Node.js MongoDB REST API Git TypeScript Docker AWS. Licence informatique.",
            parsed_data={
                "competences": ["React", "Node.js", "MongoDB", "REST API", "Git", "TypeScript", "Docker", "AWS"],
                "formations": [{"diplome": "Licence Informatique"}],
                "experiences": [{"poste": "Full Stack Developer", "description": "React Node.js MongoDB REST API Git 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 3},
            }
        ),
        "score": 0.88,
        "label": "Excellent Full Stack (toutes skills)",
    },
    {
        "offre": JobOffer(
            titre="Développeur Full Stack",
            description="Full stack 2 ans. React + Node.js backend. MongoDB, REST API, Git. Bac+3.",
            competences_requises=["React", "Node.js", "MongoDB", "REST API", "Git"],
            competences_appreciees=["TypeScript", "Docker"],
        ),
        "cv": Candidate(
            raw_text="PHP developer 5 years. Symfony Laravel MySQL jQuery. Some JavaScript but no React Node.js.",
            parsed_data={
                "competences": ["PHP", "Symfony", "Laravel", "MySQL", "jQuery", "JavaScript"],
                "formations": [{"diplome": "Licence Informatique"}],
                "experiences": [{"poste": "PHP Developer", "description": "PHP Symfony Laravel MySQL 5 ans"}],
                "metadata": {"annees_experience_totales": 5, "niveau_formation_max": 3},
            }
        ),
        "score": 0.44,
        "label": "A évaluer Full Stack (PHP dev sans React Node.js)",
    },
    {
        "offre": JobOffer(
            titre="Stage Marketing Digital",
            description="Stage marketing digital 4-6 mois. Étudiant Bac+3/5. Réseaux sociaux, SEO notions, rédaction web.",
            competences_requises=["Marketing digital", "Réseaux sociaux", "Rédaction web"],
            competences_appreciees=["SEO", "Canva", "Google Analytics"],
        ),
        "cv": Candidate(
            raw_text="Étudiante Master Marketing Communication. Réseaux sociaux Instagram TikTok rédaction web SEO notions Canva Google Analytics stage recherché.",
            parsed_data={
                "competences": ["Marketing digital", "Réseaux sociaux", "Rédaction web", "SEO", "Canva", "Google Analytics"],
                "formations": [{"diplome": "Master Marketing Communication"}],
                "metadata": {"annees_experience_totales": 0, "niveau_formation_max": 5},
            }
        ),
        "score": 0.82,
        "label": "Excellent Stage Marketing (étudiante M2)",
    },
    {
        "offre": JobOffer(
            titre="Chef de Projet Senior",
            description="Chef de projet senior 8 ans minimum. Leadership, Agile, budget >1M€, équipes 20+ personnes, reporting COMEX.",
            competences_requises=["Gestion de projet", "Leadership", "Budget", "Agile", "Reporting"],
            competences_appreciees=["PMP", "Change management", "Stakeholder management"],
        ),
        "cv": Candidate(
            raw_text="Chef de projet junior 2 ans. Agile basique Jira. Petites équipes 3-5 personnes. Pas de budget management.",
            parsed_data={
                "competences": ["Gestion de projet", "Agile", "Jira"],
                "formations": [{"diplome": "Licence Management"}],
                "experiences": [{"poste": "Chef de Projet Junior", "description": "Agile Jira petites équipes 2 ans"}],
                "metadata": {"annees_experience_totales": 2, "niveau_formation_max": 3},
            }
        ),
        "score": 0.42,
        "label": "A évaluer (junior pour poste Senior 8 ans)",
    },
    {
        "offre": JobOffer(
            titre="Chargé de Communication",
            description="Chargé de communication 2 ans. Rédaction communiqués, relations presse, événementiel, réseaux sociaux. Bac+3.",
            competences_requises=["Communication", "Rédaction", "Relations presse", "Événementiel"],
            competences_appreciees=["Réseaux sociaux", "Photoshop", "RP"],
        ),
        "cv": Candidate(
            raw_text="Chargée de communication 3 ans. Rédaction communiqués relations presse événementiel réseaux sociaux Photoshop. Licence Communication.",
            parsed_data={
                "competences": ["Communication", "Rédaction", "Relations presse", "Événementiel", "Réseaux sociaux", "Photoshop"],
                "formations": [{"diplome": "Licence Communication"}],
                "experiences": [{"poste": "Chargée de Communication", "description": "rédaction relations presse événementiel réseaux sociaux 3 ans"}],
                "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 3},
            }
        ),
        "score": 0.88,
        "label": "Excellent Communication",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Classe MLP (même architecture que create_scoring_mlp.py)
# ─────────────────────────────────────────────────────────────────────────────

class ScoringMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, 128),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1) * 100


def augment_realistic(examples: list, n: int = 2000) -> list:
    """Augmentation avec bruit gaussien + interpolation entre exemples proches."""
    result = list(examples)
    for _ in range(n):
        if random.random() < 0.7:
            # Bruit gaussien autour d'un exemple
            base = random.choice(examples)
            fs, label = base[:5], base[5]
            noise = [random.gauss(0, 0.05) for _ in range(5)]
            fs2 = [max(0.0, min(1.0, f + n)) for f, n in zip(fs, noise)]
            delta = sum(noise[i] * [0.22, 0.32, 0.20, 0.14, 0.12][i] for i in range(5))
            label2 = max(0.20, min(0.95, label + delta))
        else:
            # Interpolation entre deux exemples
            a, b = random.sample(examples, 2)
            alpha = random.random()
            fs2 = [a[i] * alpha + b[i] * (1 - alpha) for i in range(5)]
            label2 = a[5] * alpha + b[5] * (1 - alpha)
        result.append(fs2 + [label2])
    return result


def extract_features(scorer: BERTMatchingScorer, annotations: list) -> list:
    """Extrait les 5 features réelles (sem_sim, skill_rate, exp_score, form_score, apr_rate)
    en faisant tourner le pipeline BERT complet sur chaque paire (offre, CV)."""
    rows = []
    for i, ann in enumerate(annotations):
        try:
            score_raw, details = scorer.score(ann["offre"], ann["cv"])
            # Récupérer les features brutes (avant MLP)
            sem_sim        = details["bert_semantic"]      # similarité cosinus BERT
            skill_rate     = details["bert_skills"]        # skill match rate (0-1)
            exp_score      = details["experience"] / 100   # expérience (0-1)
            formation_score = details["formation"] / 100   # formation (0-1)
            # appreciated_rate : si pas de compétences appréciées → 0.5 par défaut
            appreciees = getattr(ann["offre"], "competences_appreciees", None) or []
            criteres = details.get("criteres", {}).get("apprecies", [])
            if criteres:
                apr_matched = sum(1 for c in criteres if c.get("matched"))
                apr_rate = apr_matched / len(criteres)
            else:
                apr_rate = 0.5

            row = [sem_sim, skill_rate, exp_score, formation_score, apr_rate, ann["score"]]
            rows.append(row)
            print(f"  [{i+1:3d}/{len(annotations)}] {ann['label'][:40]:<40} -> features ok  (target={ann['score']:.2f})")
        except Exception as e:
            print(f"  [{i+1:3d}] ERREUR {ann.get('label', '?')}: {e}")
    return rows


def main():
    print("=" * 70)
    print("TalentMatch — Calibration MLP avec donnees realistes")
    print("=" * 70)

    print("\n1) Chargement du scorer BERT v2.0...")
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    print(f"   Modele: v2.0={scorer._use_v2}  MLP actuel={scorer._mlp is not None}")

    print(f"\n2) Extraction features sur {len(ANNOTATIONS)} exemples annotes...")
    raw_data = extract_features(scorer, ANNOTATIONS)
    print(f"   {len(raw_data)} exemples extraits avec succes")

    print("\n3) Augmentation des donnees...")
    augmented = augment_realistic(raw_data, n=3000)
    random.shuffle(augmented)
    print(f"   Total apres augmentation: {len(augmented)} exemples")

    print("\n4) Preparation du dataset...")
    tensors = torch.tensor(augmented, dtype=torch.float32)
    X = tensors[:, :5]
    y = tensors[:, 5]
    split = int(len(X) * 0.85)
    X_train, y_train = X[:split], y[:split]
    X_val,   y_val   = X[split:], y[split:]
    train_ds = TensorDataset(X_train, y_train)
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)

    print("\n5) Entrainement MLP calibre...")
    mlp = ScoringMLP()
    optimizer = torch.optim.AdamW(mlp.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=200)

    best_val = float('inf')
    best_state = None

    for epoch in range(200):
        mlp.train()
        for xb, yb in train_loader:
            optimizer.zero_grad()
            pred = mlp(xb) / 100
            loss = F.mse_loss(pred, yb)
            loss.backward()
            optimizer.step()
        scheduler.step()

        if (epoch + 1) % 40 == 0:
            mlp.eval()
            with torch.no_grad():
                val_pred = mlp(X_val) / 100
                val_loss = F.mse_loss(val_pred, y_val).item()
            print(f"   Epoch {epoch+1:3d}/200 | Val Loss: {val_loss:.5f}")
            if val_loss < best_val:
                best_val = val_loss
                best_state = {k: v.clone() for k, v in mlp.state_dict().items()}

    mlp.load_state_dict(best_state)
    mlp.eval()

    print("\n6) Verification sur cas de reference...")
    print("-" * 65)
    VERIF = [
        ([0.90, 1.00, 1.00, 1.00, 1.00], "Excellent parfait (tout 100%)"),
        ([0.70, 1.00, 1.00, 1.00, 0.60], "Excellent (sem=0.70, tout competences)"),
        ([0.65, 0.75, 0.80, 0.80, 0.50], "Bon profil (sem=0.65, sk=75%, exp=80%)"),
        ([0.55, 0.60, 0.70, 0.70, 0.30], "Bon profil limite (sem=0.55, sk=60%)"),
        ([0.45, 0.50, 0.60, 0.60, 0.30], "A evaluer (sem=0.45, sk=50%, exp=60%)"),
        ([0.40, 0.40, 0.50, 0.50, 0.10], "A evaluer bas (sem=0.40, sk=40%)"),
        ([0.20, 0.10, 0.30, 0.30, 0.00], "Non adapte (sem=0.20, sk=10%)"),
        ([0.08, 0.00, 0.20, 0.20, 0.00], "Hors domaine (sem=0.08, sk=0%)"),
        ([0.60, 0.80, 0.20, 1.00, 0.50], "Stage junior (sem=0.60, exp=20%)"),
        ([0.75, 0.80, 1.00, 1.00, 0.80], "Senior confirme (sem=0.75, exp=100%)"),
    ]

    with torch.no_grad():
        for features, label in VERIF:
            x = torch.tensor([features], dtype=torch.float32)
            score = float(mlp(x))
            decision = (
                "Excellent"    if score >= 80 else
                "Bon profil"   if score >= 65 else
                "A evaluer"    if score >= 50 else
                "Non adapte"
            )
            print(f"  {label}")
            print(f"    -> {score:.1f}%  [{decision}]")

    print("\n7) Sauvegarde...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(mlp.state_dict(), os.path.join(MODEL_DIR, 'scoring_mlp.pt'))

    config = {
        "version": "TalentMatch-BERT v2.0 — MLP calibre donnees reelles",
        "mlp_input": ["sem_sim", "skill_rate", "exp_score", "formation_score", "appreciated_rate"],
        "mlp_dims": [5, 128, 64, 32, 1],
        "thresholds": {"excellent": 80, "bon_profil": 65, "a_evaluer": 50, "non_adapte": 0},
        "decisions": {
            "excellent":  "Excellent candidat",
            "bon_profil": "Bon profil - Entretien recommande",
            "a_evaluer":  "Profil partiel - A evaluer",
            "non_adapte": "Profil non adapte",
        },
        "training": {
            "n_annotations": len(raw_data),
            "n_augmented": len(augmented),
            "val_loss_finale": round(best_val, 6),
            "domaines": [
                "IT Python", "IT Java", "IT DevOps", "IT Data Science",
                "IT Frontend", "IT Mobile", "Finance Comptabilite",
                "Analyse Financiere", "RH", "Ventes Commercial",
                "Ingenierie Mecanique", "Genie Civil BTP",
                "Marketing Digital", "Sante", "Enseignement",
                "Design UX", "Aeronautique", "Automobile",
                "Droit", "Supply Chain", "Gestion de Projet",
                "Communication", "Stage Junior", "Senior Management",
            ],
        },
    }
    with open(os.path.join(MODEL_DIR, 'scoring_config.json'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"   scoring_mlp.pt sauvegarde dans {MODEL_DIR}")
    print(f"   Val Loss finale: {best_val:.5f}")
    print("\nCalibration terminee avec succes!")


if __name__ == "__main__":
    main()
