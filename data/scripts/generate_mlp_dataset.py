"""
TalentMatch — Génération programmatique du dataset MLP
======================================================
Génère ~500 paires (offre, CV, score) couvrant 32 postes × 5 niveaux
+ croisements inter-domaines automatiques.

Avantages vs annotation manuelle :
  - Aucune annotation manuelle
  - Diversité garantie (5 niveaux par poste)
  - Cross-domain couverts systématiquement

Usage (depuis backend/) :
    python ../data/scripts/generate_mlp_dataset.py
"""
from __future__ import annotations

import os, sys, json, random
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

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
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

FORMATION_LABELS = {
    1: "CAP/BEP", 2: "BTS/DUT", 3: "Licence", 4: "Licence Pro",
    5: "Master/Ingénieur", 6: "Doctorat/PhD",
}

def _build_candidate(poste: str, skills: list[str], exp_years: int,
                     formation: int, school: str, extra_text: str = "") -> Candidate:
    skills_str = ", ".join(skills)
    diplome = FORMATION_LABELS.get(formation, "Master")
    raw = (
        f"{poste}. {exp_years} ans d'expérience. "
        f"Compétences : {skills_str}. "
        f"Formation : {diplome}. "
        + extra_text
    )
    parsed = {
        "competences": skills,
        "formations": [{"diplome": diplome, "etablissement": school}],
        "experiences": [{"poste": poste, "description": f"{skills_str} {exp_years} ans"}],
        "metadata": {"annees_experience_totales": exp_years, "niveau_formation_max": formation},
    }
    return Candidate(raw_text=raw, parsed_data=parsed)


def _build_offer(titre: str, desc: str, required: list[str],
                 appreciated: list[str]) -> JobOffer:
    return JobOffer(
        titre=titre,
        description=desc,
        competences_requises=required,
        competences_appreciees=appreciated,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Pool de CVs "mauvais domaine" — réutilisés comme négatifs pour tous les postes
# ─────────────────────────────────────────────────────────────────────────────

WRONG_DOMAIN_POOL = [
    {"domain": "medecin", "poste": "Médecin Généraliste",
     "skills": ["Médecine", "Diagnostic clinique", "Prescription médicale", "Consultations"],
     "exp": 7, "formation": 6, "school": "Faculté de Médecine", "score": 0.22},
    {"domain": "comptable", "poste": "Expert Comptable",
     "skills": ["Comptabilité", "Sage", "Excel", "TVA", "Bilan", "Fiscalité"],
     "exp": 6, "formation": 5, "school": "ISCAE", "score": 0.21},
    {"domain": "maçon", "poste": "Chef de Chantier BTP",
     "skills": ["Maçonnerie", "Coffrage", "Béton", "Suivi chantier", "Sécurité BTP"],
     "exp": 8, "formation": 2, "school": "", "score": 0.19},
    {"domain": "designer", "poste": "Graphiste / Motion Designer",
     "skills": ["Photoshop", "Illustrator", "After Effects", "InDesign", "Motion design"],
     "exp": 4, "formation": 3, "school": "ESAD", "score": 0.21},
    {"domain": "conducteur", "poste": "Chauffeur Poids Lourd",
     "skills": ["Conduite PL", "Livraison", "Gestion tournées", "Permis C+E"],
     "exp": 5, "formation": 1, "school": "", "score": 0.18},
    {"domain": "cuisinier", "poste": "Chef Cuisinier",
     "skills": ["Cuisine", "Pâtisserie", "Gestion cuisine", "HACCP", "Gestion équipe"],
     "exp": 6, "formation": 2, "school": "École Hôtelière", "score": 0.19},
    {"domain": "electricien", "poste": "Électricien Industriel",
     "skills": ["Câblage électrique", "Armoires électriques", "Habilitation électrique", "Maintenance"],
     "exp": 5, "formation": 2, "school": "", "score": 0.20},
    {"domain": "vendeur", "poste": "Vendeur Retail",
     "skills": ["Service client", "Vente", "Caisse", "Merchandising", "Stock"],
     "exp": 3, "formation": 2, "school": "", "score": 0.22},
    {"domain": "prof_arabe", "poste": "Professeur Arabe",
     "skills": ["Langue arabe", "Pédagogie", "Grammaire arabe", "Cours", "Évaluation"],
     "exp": 10, "formation": 5, "school": "Université Zitouna", "score": 0.21},
    {"domain": "agriculteur", "poste": "Ingénieur Agronome",
     "skills": ["Agriculture", "Agronomie", "Irrigation", "Sols", "Production végétale"],
     "exp": 5, "formation": 5, "school": "INAT", "score": 0.20},
]

# ─────────────────────────────────────────────────────────────────────────────
# Catalogue de postes — 32 profils × 5 niveaux
# Niveaux : excellent(0.90-0.95) | bon(0.74-0.86) | a_evaluer(0.55-0.68)
#           | junior(0.38-0.50)  | adjacent(0.42-0.60)
# ─────────────────────────────────────────────────────────────────────────────

CATALOG = [

    # ══════════════════════════════════════════════════════ IT — Python Backend
    {
        "id": "it_python_senior",
        "domain": "it",
        "offre": _build_offer(
            "Développeur Python Senior",
            "Développeur Python senior 5 ans minimum. FastAPI, PostgreSQL, Docker obligatoire. Kubernetes AWS apprécié. Bac+5.",
            ["Python", "FastAPI", "PostgreSQL", "Docker"],
            ["Kubernetes", "AWS", "Redis"],
        ),
        "candidates": [
            ("excellent",  "Senior Python Developer",  ["Python","FastAPI","PostgreSQL","Docker","Kubernetes","AWS","Redis","microservices"],  7, 5, "ENSI Tunis",   0.93),
            ("bon",        "Python Developer",          ["Python","FastAPI","PostgreSQL","Docker","AWS"],                                       4, 5, "ESPRIT",       0.76),
            ("a_evaluer",  "Python Developer",          ["Python","FastAPI","PostgreSQL"],                                                      2, 3, "",             0.62),
            ("junior",     "Développeur Junior Python", ["Python","Flask"],                                                                     1, 3, "",             0.40),
            ("adjacent",   "Développeur PHP Symfony",   ["PHP","Symfony","MySQL","JavaScript","Docker"],                                        4, 3, "",             0.45),
        ],
    },

    # ══════════════════════════════════════════════════════ IT — Java Spring
    {
        "id": "it_java_spring",
        "domain": "it",
        "offre": _build_offer(
            "Développeur Java Spring Boot",
            "Développeur Java 3 ans. Spring Boot, Hibernate, MySQL indispensable. Microservices, Docker apprécié. Bac+5.",
            ["Java", "Spring Boot", "Hibernate", "MySQL"],
            ["Microservices", "Docker", "Kafka"],
        ),
        "candidates": [
            ("excellent",  "Senior Java Developer",     ["Java","Spring Boot","Hibernate","MySQL","Microservices","Docker","Kafka","JUnit"],    6, 5, "INSAT",        0.93),
            ("bon",        "Java Developer",             ["Java","Spring Boot","Hibernate","MySQL","Docker"],                                    3, 5, "FST Tunis",    0.78),
            ("a_evaluer",  "Java Developer Junior",      ["Java","Spring Boot","MySQL"],                                                         2, 3, "",             0.58),
            ("junior",     "Stagiaire Java",             ["Java","SQL"],                                                                         0, 5, "ESPRIT",       0.38),
            ("adjacent",   "Développeur C# .NET",        ["C#", ".NET", "ASP.NET", "SQL Server", "Entity Framework"],                           4, 5, "",             0.48),
        ],
    },

    # ══════════════════════════════════════════════════════ IT — DevOps
    {
        "id": "it_devops",
        "domain": "it",
        "offre": _build_offer(
            "Ingénieur DevOps Cloud",
            "DevOps 4 ans. Docker, Kubernetes, Terraform, AWS obligatoire. CI/CD GitLab Jenkins. Bac+5.",
            ["Docker", "Kubernetes", "Terraform", "AWS", "CI/CD"],
            ["Ansible", "Prometheus", "Grafana"],
        ),
        "candidates": [
            ("excellent",  "Senior DevOps Engineer",     ["Docker","Kubernetes","Terraform","AWS","CI/CD","Ansible","Prometheus","Grafana","GCP"], 6, 5, "Polytechnique", 0.94),
            ("bon",        "DevOps Engineer",             ["Docker","Kubernetes","Terraform","AWS","CI/CD"],                                        4, 5, "INSAT",         0.82),
            ("a_evaluer",  "Admin Systèmes Linux",        ["Linux","Docker","Bash","CI/CD","Ansible"],                                              3, 3, "",              0.60),
            ("junior",     "Développeur Backend Python",  ["Python","Flask","Docker"],                                                              2, 3, "",              0.42),
            ("adjacent",   "Administrateur Réseaux",      ["Cisco","Réseaux","VLAN","VPN","Firewall","Linux"],                                      5, 5, "",              0.50),
        ],
    },

    # ══════════════════════════════════════════════════════ IT — Data Science
    {
        "id": "it_data_science",
        "domain": "it",
        "offre": _build_offer(
            "Data Scientist Senior",
            "Data Scientist 3 ans. Python, TensorFlow/PyTorch, SQL. MLOps, Spark apprécié. Bac+5.",
            ["Python", "Machine Learning", "TensorFlow", "SQL"],
            ["MLOps", "Spark", "Deep Learning", "NLP"],
        ),
        "candidates": [
            ("excellent",  "Senior Data Scientist",      ["Python","Machine Learning","TensorFlow","PyTorch","SQL","MLOps","Spark","Deep Learning","NLP"], 5, 6, "ENSI", 0.93),
            ("bon",        "Data Scientist",              ["Python","Machine Learning","TensorFlow","SQL","MLOps"],                                          3, 5, "INSAT", 0.82),
            ("a_evaluer",  "Data Analyst",                ["Python","SQL","Excel","PowerBI","Statistiques"],                                                2, 5, "",      0.60),
            ("junior",     "Stagiaire Data Science",      ["Python","SQL","NumPy","Pandas"],                                                                0, 5, "ESPRIT", 0.42),
            ("adjacent",   "Data Engineer",               ["Python","Spark","Kafka","Airflow","SQL","ETL","Hadoop"],                                        4, 5, "",      0.58),
        ],
    },

    # ══════════════════════════════════════════════════════ IT — Frontend React
    {
        "id": "it_frontend_react",
        "domain": "it",
        "offre": _build_offer(
            "Développeur Frontend React",
            "Développeur React 3 ans. TypeScript, Redux, REST API, CSS/Tailwind. Next.js, GraphQL apprécié.",
            ["React", "TypeScript", "Redux", "CSS"],
            ["Next.js", "GraphQL", "Jest", "Tailwind"],
        ),
        "candidates": [
            ("excellent",  "Senior Frontend Developer",   ["React","TypeScript","Redux","CSS","Next.js","GraphQL","Jest","Tailwind","Vite"],  5, 5, "ESPRIT",  0.92),
            ("bon",        "Frontend Developer React",    ["React","TypeScript","Redux","CSS","Next.js"],                                      3, 5, "FST",     0.80),
            ("a_evaluer",  "Frontend Developer",          ["React","JavaScript","CSS","HTML"],                                                 2, 3, "",        0.58),
            ("junior",     "Développeur Web Junior",      ["HTML","CSS","JavaScript","jQuery"],                                                1, 3, "",        0.35),
            ("adjacent",   "Développeur Angular",         ["Angular","TypeScript","RxJS","CSS","REST API"],                                    4, 5, "",        0.55),
        ],
    },

    # ══════════════════════════════════════════════════════ IT — Mobile Flutter
    {
        "id": "it_mobile_flutter",
        "domain": "it",
        "offre": _build_offer(
            "Développeur Mobile Flutter",
            "Développeur Flutter 2 ans. Dart, Firebase, iOS et Android. Publication stores exigée.",
            ["Flutter", "Dart", "Firebase", "iOS", "Android"],
            ["GetX", "Bloc pattern", "REST API"],
        ),
        "candidates": [
            ("excellent",  "Senior Flutter Developer",    ["Flutter","Dart","Firebase","iOS","Android","GetX","Bloc","REST API"],              4, 5, "INSAT",  0.92),
            ("bon",        "Flutter Developer",           ["Flutter","Dart","Firebase","iOS","Android"],                                        2, 5, "ESPRIT", 0.78),
            ("a_evaluer",  "Développeur Android Kotlin",  ["Android","Kotlin","Jetpack","Firebase","REST API"],                                3, 5, "",       0.52),
            ("junior",     "Stagiaire Mobile",            ["Flutter","Dart"],                                                                   0, 5, "ESPRIT", 0.38),
            ("adjacent",   "Développeur iOS Swift",       ["iOS","Swift","SwiftUI","Xcode","CocoaPods"],                                        4, 5, "",       0.48),
        ],
    },

    # ══════════════════════════════════════════════════════ IT — FullStack
    {
        "id": "it_fullstack",
        "domain": "it",
        "offre": _build_offer(
            "Développeur Full Stack Node.js / React",
            "Full Stack 2 ans. React frontend, Node.js backend, MongoDB, REST API, Git. TypeScript Docker apprécié.",
            ["React", "Node.js", "MongoDB", "REST API", "Git"],
            ["TypeScript", "Docker", "AWS", "GraphQL"],
        ),
        "candidates": [
            ("excellent",  "Senior Full Stack Developer", ["React","Node.js","MongoDB","REST API","Git","TypeScript","Docker","AWS","GraphQL"], 5, 5, "ENSI",   0.93),
            ("bon",        "Full Stack Developer",        ["React","Node.js","MongoDB","REST API","Git","TypeScript"],                           3, 3, "ESPRIT", 0.80),
            ("a_evaluer",  "Développeur PHP/JS",         ["PHP","JavaScript","MySQL","jQuery","Git"],                                           4, 3, "",       0.48),
            ("junior",     "Stagiaire Full Stack",        ["React","Node.js","MongoDB"],                                                         0, 5, "ESPRIT", 0.42),
            ("adjacent",   "Développeur Django Python",   ["Python","Django","PostgreSQL","REST API","Git"],                                     3, 5, "",       0.55),
        ],
    },

    # ══════════════════════════════════════════════════════ IT — Cybersécurité
    {
        "id": "it_cybersec",
        "domain": "it",
        "offre": _build_offer(
            "Ingénieur Cybersécurité",
            "Ingénieur cybersécurité 3 ans. Pentest, SIEM, ISO 27001, audit sécurité. OSCP apprécié.",
            ["Cybersécurité", "Pentest", "SIEM", "ISO 27001"],
            ["OSCP", "Kali Linux", "SOC", "Forensics"],
        ),
        "candidates": [
            ("excellent",  "Senior Security Engineer",    ["Cybersécurité","Pentest","SIEM","ISO 27001","OSCP","Kali Linux","SOC","Forensics"], 5, 5, "SupCom",  0.93),
            ("bon",        "Security Analyst",            ["Cybersécurité","Pentest","SIEM","ISO 27001"],                                         3, 5, "INSAT",   0.80),
            ("a_evaluer",  "Admin Systèmes Sécurité",     ["Linux","Firewall","VPN","Active Directory","Antivirus"],                              4, 3, "",        0.55),
            ("junior",     "Stagiaire Cybersécurité",     ["Réseaux","Linux","Python","CTF"],                                                     0, 5, "ESPRIT",  0.38),
            ("adjacent",   "Admin Réseaux Senior",        ["Cisco","Réseaux","VLAN","Firewall","VPN","Linux","CCNP"],                             5, 5, "",        0.52),
        ],
    },

    # ══════════════════════════════════════════════════════ Finance — Comptable
    {
        "id": "finance_comptable",
        "domain": "finance",
        "offre": _build_offer(
            "Responsable Comptable",
            "Comptable confirmé 5 ans. Sage, Excel avancé, fiscalité tunisienne, bilan, TVA. IFRS, audit apprécié. Bac+3.",
            ["Comptabilité", "Sage", "Excel", "Fiscalité", "TVA"],
            ["IFRS", "Audit", "Contrôle de gestion"],
        ),
        "candidates": [
            ("excellent",  "Expert Comptable",            ["Comptabilité","Sage","Excel","Fiscalité","TVA","IFRS","Audit","Contrôle de gestion"], 7, 5, "ISCAE",  0.93),
            ("bon",        "Responsable Comptable",       ["Comptabilité","Sage","Excel","Fiscalité","TVA","IFRS"],                                4, 5, "IHEC",   0.80),
            ("a_evaluer",  "Assistant Comptable",         ["Comptabilité","Sage","Excel","TVA"],                                                   2, 3, "",       0.58),
            ("junior",     "Aide-Comptable",              ["Comptabilité","Excel"],                                                                1, 3, "",       0.38),
            ("adjacent",   "Contrôleur de Gestion",       ["Contrôle de gestion","Reporting","Budget","Excel","PowerBI"],                          4, 5, "IHEC",   0.55),
        ],
    },

    # ══════════════════════════════════════════════════════ Finance — Analyste
    {
        "id": "finance_analyste",
        "domain": "finance",
        "offre": _build_offer(
            "Analyste Financier",
            "Analyste financier 3 ans. Modélisation financière, Excel, analyse bilans, reporting. Bloomberg, VBA apprécié. Bac+5.",
            ["Finance", "Excel", "Modélisation financière", "Analyse financière"],
            ["Bloomberg", "VBA", "PowerBI", "Python Finance"],
        ),
        "candidates": [
            ("excellent",  "Senior Analyste Financier",   ["Finance","Excel","Modélisation financière","Analyse financière","Bloomberg","VBA","PowerBI"], 5, 5, "IHEC",  0.92),
            ("bon",        "Analyste Financier",          ["Finance","Excel","Modélisation financière","Analyse financière","PowerBI"],                    3, 5, "ESPRIT",0.80),
            ("a_evaluer",  "Contrôleur de Gestion",       ["Finance","Excel","Reporting","Budget","Tableaux de bord"],                                     4, 5, "",      0.65),
            ("junior",     "Analyste Junior",             ["Finance","Excel","Analyse financière"],                                                         1, 5, "",      0.50),
            ("adjacent",   "Auditeur Externe",            ["Audit","Comptabilité","Analyse financière","IFRS","Bilan"],                                     3, 5, "ISCAE", 0.60),
        ],
    },

    # ══════════════════════════════════════════════════════ Finance — Contrôle gestion
    {
        "id": "finance_controle_gestion",
        "domain": "finance",
        "offre": _build_offer(
            "Contrôleur de Gestion Senior",
            "Contrôleur de gestion 4 ans. Reporting, tableaux de bord, analyse des écarts, budget. SAP, PowerBI apprécié.",
            ["Contrôle de gestion", "Reporting", "Budget", "Analyse des écarts"],
            ["SAP", "PowerBI", "Excel avancé", "VBA"],
        ),
        "candidates": [
            ("excellent",  "Senior Contrôleur de Gestion", ["Contrôle de gestion","Reporting","Budget","Analyse des écarts","SAP","PowerBI","VBA","Excel avancé"], 6, 5, "IHEC",   0.93),
            ("bon",        "Contrôleur de Gestion",        ["Contrôle de gestion","Reporting","Budget","Analyse des écarts","PowerBI"],                              4, 5, "IHEC",   0.82),
            ("a_evaluer",  "Responsable Comptable",        ["Comptabilité","Sage","Excel","TVA","Bilan"],                                                            5, 5, "ISCAE",  0.52),
            ("junior",     "Assistant Contrôle de Gestion",["Contrôle de gestion","Excel","Reporting"],                                                              1, 5, "",       0.48),
            ("adjacent",   "Analyste Financier",           ["Finance","Excel","Modélisation financière","Bloomberg","VBA"],                                          4, 5, "IHEC",   0.62),
        ],
    },

    # ══════════════════════════════════════════════════════ RH — Responsable RH
    {
        "id": "rh_responsable",
        "domain": "rh",
        "offre": _build_offer(
            "Responsable Ressources Humaines",
            "RH confirmé 4 ans. Recrutement, GPEC, paie, SIRH. Workday, droit du travail apprécié. Bac+5.",
            ["Recrutement", "GPEC", "Paie", "SIRH"],
            ["Workday", "Droit du travail", "Formation", "Talent management"],
        ),
        "candidates": [
            ("excellent",  "Directeur RH",                ["Recrutement","GPEC","Paie","SIRH","Workday","Droit du travail","Formation","Talent management"], 9, 5, "ESCP",  0.94),
            ("bon",        "Responsable RH",               ["Recrutement","GPEC","Paie","SIRH","Workday"],                                                   5, 5, "IHEC",  0.82),
            ("a_evaluer",  "Chargé de Recrutement",        ["Recrutement","Sourcing","ATS","Entretiens"],                                                     3, 5, "",      0.62),
            ("junior",     "Assistant RH",                 ["Recrutement","Paie"],                                                                            1, 3, "",      0.42),
            ("adjacent",   "Juriste Social",               ["Droit du travail","Contentieux social","Conventions collectives","RGPD"],                         4, 5, "",      0.48),
        ],
    },

    # ══════════════════════════════════════════════════════ RH — Recrutement
    {
        "id": "rh_recrutement",
        "domain": "rh",
        "offre": _build_offer(
            "Chargé de Recrutement",
            "Chargé de recrutement 2 ans. Sourcing LinkedIn, ATS, entretiens, assessment. Employer branding apprécié.",
            ["Recrutement", "Sourcing", "LinkedIn", "Entretiens"],
            ["ATS", "Assessment", "Employer branding", "Onboarding"],
        ),
        "candidates": [
            ("excellent",  "Senior Talent Acquisition",   ["Recrutement","Sourcing","LinkedIn","Entretiens","ATS","Assessment","Employer branding","Onboarding"], 5, 5, "ESCP", 0.92),
            ("bon",        "Chargé de Recrutement",       ["Recrutement","Sourcing","LinkedIn","Entretiens","ATS"],                                               3, 5, "IHEC", 0.82),
            ("a_evaluer",  "Assistant RH Recrutement",    ["Recrutement","LinkedIn","Entretiens"],                                                                 1, 3, "",     0.58),
            ("junior",     "Stagiaire RH",                ["Recrutement","Excel"],                                                                                  0, 5, "",     0.38),
            ("adjacent",   "Responsable Formation",       ["Formation","Plan de formation","LMS","E-learning","Bilan compétences"],                               4, 5, "",     0.45),
        ],
    },

    # ══════════════════════════════════════════════════════ Droit — Juriste entreprise
    {
        "id": "droit_juriste_entreprise",
        "domain": "droit",
        "offre": _build_offer(
            "Juriste d'Entreprise",
            "Juriste droit des affaires 3 ans. Contrats commerciaux, droit du travail, RGPD, contentieux. Master Droit.",
            ["Droit des affaires", "Contrats commerciaux", "Droit du travail", "RGPD"],
            ["Contentieux", "Propriété intellectuelle", "Négociation", "Fusions-acquisitions"],
        ),
        "candidates": [
            ("excellent",  "Senior Juriste Entreprise",   ["Droit des affaires","Contrats commerciaux","Droit du travail","RGPD","Contentieux","Propriété intellectuelle","Négociation"], 6, 5, "Faculté Droit Tunis", 0.93),
            ("bon",        "Juriste Entreprise",          ["Droit des affaires","Contrats commerciaux","Droit du travail","RGPD"],                                                          3, 5, "Faculté Droit",       0.80),
            ("a_evaluer",  "Juriste Junior",              ["Droit des affaires","Contrats commerciaux","RGPD"],                                                                             1, 5, "Faculté Droit",       0.55),
            ("junior",     "Paralégal",                   ["Droit des affaires","Rédaction juridique"],                                                                                     2, 3, "",                    0.38),
            ("adjacent",   "Avocat d'Affaires",           ["Droit commercial","Contrats","Contentieux","Plaidoirie","Négociation"],                                                          5, 5, "Barreau Tunis",       0.68),
        ],
    },

    # ══════════════════════════════════════════════════════ Droit — Compliance
    {
        "id": "droit_compliance",
        "domain": "droit",
        "offre": _build_offer(
            "Responsable Conformité / Compliance",
            "Compliance officer 3 ans. RGPD, AML/KYC, réglementations financières, audit conformité. Bac+5 droit ou finance.",
            ["Conformité", "RGPD", "AML", "KYC"],
            ["Réglementations financières", "Audit conformité", "Risques", "Reporting réglementaire"],
        ),
        "candidates": [
            ("excellent",  "Senior Compliance Officer",   ["Conformité","RGPD","AML","KYC","Audit conformité","Réglementations financières","Risques"],  5, 5, "Sciences Po", 0.93),
            ("bon",        "Compliance Officer",          ["Conformité","RGPD","AML","KYC","Audit conformité"],                                           3, 5, "",            0.82),
            ("a_evaluer",  "Juriste RGPD",                ["RGPD","Droit du numérique","Protection données","Conformité"],                                3, 5, "",            0.62),
            ("junior",     "Assistant Compliance",        ["Conformité","RGPD"],                                                                           1, 5, "",            0.42),
            ("adjacent",   "Auditeur Interne",            ["Audit","Contrôle interne","Risques","Procédures","ISO 27001"],                                  4, 5, "ISCAE",       0.58),
        ],
    },

    # ══════════════════════════════════════════════════════ Marketing — Digital
    {
        "id": "marketing_digital",
        "domain": "marketing",
        "offre": _build_offer(
            "Responsable Marketing Digital",
            "Marketing digital 3 ans. SEO, Google Ads, réseaux sociaux, email marketing, Analytics. HubSpot, Meta Ads apprécié. Bac+5.",
            ["SEO", "Google Ads", "Réseaux sociaux", "Email marketing", "Analytics"],
            ["HubSpot", "Meta Ads", "Content marketing", "CRO"],
        ),
        "candidates": [
            ("excellent",  "Digital Marketing Manager",   ["SEO","Google Ads","Réseaux sociaux","Email marketing","Analytics","HubSpot","Meta Ads","CRO"], 5, 5, "IHEC",  0.93),
            ("bon",        "Responsable Marketing Digital",["SEO","Google Ads","Réseaux sociaux","Email marketing","Analytics"],                             3, 5, "ESPRIT",0.82),
            ("a_evaluer",  "SEO Manager",                  ["SEO","Analytics","Content marketing","Google Search Console"],                                  4, 5, "",      0.65),
            ("junior",     "Community Manager",            ["Réseaux sociaux","Community management"],                                                       1, 3, "",      0.42),
            ("adjacent",   "Traffic Manager",              ["Google Ads","Meta Ads","SEM","Analytics","Tracking"],                                           3, 5, "",      0.60),
        ],
    },

    # ══════════════════════════════════════════════════════ Marketing — Product Manager
    {
        "id": "marketing_product",
        "domain": "marketing",
        "offre": _build_offer(
            "Product Manager",
            "Product Manager 3 ans. Roadmap produit, user stories, UX, data-driven. Agile Scrum, A/B testing apprécié.",
            ["Gestion de produit", "Roadmap", "User stories", "UX", "Data analyse"],
            ["Agile", "A/B testing", "SQL", "Figma"],
        ),
        "candidates": [
            ("excellent",  "Senior Product Manager",       ["Gestion de produit","Roadmap","User stories","UX","Data analyse","Agile","A/B testing","SQL","Figma"], 5, 5, "HEC Paris", 0.93),
            ("bon",        "Product Manager",               ["Gestion de produit","Roadmap","User stories","UX","Data analyse","Agile"],                              3, 5, "ESPRIT",    0.82),
            ("a_evaluer",  "Chef de Projet IT",             ["Gestion de projet","Agile","Scrum","Jira","Planning"],                                                  4, 5, "",          0.58),
            ("junior",     "Business Analyst Junior",       ["Analyse fonctionnelle","User stories","Agile"],                                                          1, 5, "",          0.42),
            ("adjacent",   "UX/UI Designer",                ["UX Design","Figma","Prototypage","User research","Design System"],                                       4, 5, "",          0.52),
        ],
    },

    # ══════════════════════════════════════════════════════ Santé — Médecin généraliste
    {
        "id": "sante_medecin",
        "domain": "sante",
        "offre": _build_offer(
            "Médecin Généraliste",
            "Médecin généraliste cabinet médical. Doctorat médecine obligatoire. Consultations, prescriptions, suivi patients, pédiatrie, ECG.",
            ["Médecine générale", "Diagnostic clinique", "Prescription médicale", "Suivi patient"],
            ["Urgences médicales", "Pédiatrie", "ECG", "Vaccination"],
        ),
        "candidates": [
            ("excellent",  "Médecin Généraliste",           ["Médecine générale","Diagnostic clinique","Prescription médicale","Suivi patient","Urgences médicales","Pédiatrie","ECG","Vaccination"], 8, 6, "Faculté Médecine Tunis", 0.94),
            ("bon",        "Médecin Généraliste",            ["Médecine générale","Diagnostic clinique","Prescription médicale","Suivi patient"],                                                       4, 6, "Faculté Médecine",       0.84),
            ("a_evaluer",  "Médecin Urgentiste",             ["Urgences médicales","Réanimation","Diagnostic clinique","ECG","Triage"],                                                                 5, 6, "Faculté Médecine",       0.65),
            ("junior",     "Interne en Médecine",            ["Médecine générale","Diagnostic clinique"],                                                                                               1, 6, "Faculté Médecine",       0.52),
            ("adjacent",   "Infirmier(ère) Diplômé(e)",      ["Soins infirmiers","Suivi patient","ECG","Vaccination","Pansements"],                                                                     5, 3, "ISET Santé",             0.45),
        ],
    },

    # ══════════════════════════════════════════════════════ Santé — Infirmier
    {
        "id": "sante_infirmier",
        "domain": "sante_paramedical",
        "offre": _build_offer(
            "Infirmier(ère) de Bloc Opératoire",
            "Infirmier bloc opératoire (IBODE) 2 ans. Bloc, stérilisation, instrumentation, urgences. Diplôme IBODE requis.",
            ["Soins infirmiers", "Bloc opératoire", "Stérilisation", "Instrumentation chirurgicale"],
            ["Urgences", "Réanimation", "Anesthésie", "Dossier patient"],
        ),
        "candidates": [
            ("excellent",  "Infirmier IBODE Senior",        ["Soins infirmiers","Bloc opératoire","Stérilisation","Instrumentation chirurgicale","Urgences","Réanimation","Anesthésie"], 5, 5, "Institut Soins Infirmiers", 0.93),
            ("bon",        "Infirmier de Bloc",             ["Soins infirmiers","Bloc opératoire","Stérilisation","Instrumentation chirurgicale"],                                         3, 5, "ISET Santé",               0.82),
            ("a_evaluer",  "Infirmier Polyvalent",          ["Soins infirmiers","Urgences","Dossier patient","Pansements"],                                                                 3, 3, "ISET Santé",               0.58),
            ("junior",     "Aide-Soignant",                 ["Soins infirmiers","Hygiène","Aide patient"],                                                                                  2, 2, "",                        0.38),
            ("adjacent",   "Infirmier Urgences",            ["Soins infirmiers","Urgences","Triage","Réanimation","ECG"],                                                                    4, 3, "ISET Santé",               0.55),
        ],
    },

    # ══════════════════════════════════════════════════════ Ingénierie — Mécanique
    {
        "id": "ingenierie_mecanique",
        "domain": "ingenierie",
        "offre": _build_offer(
            "Ingénieur Mécanique Conception",
            "Ingénieur mécanique 3 ans. SolidWorks, CATIA, calcul de structure, RDM. ANSYS, normes ISO apprécié. Bac+5.",
            ["SolidWorks", "CATIA", "Calcul de structure", "Résistance des matériaux"],
            ["ANSYS", "Gestion de projet", "Normes ISO", "Fatigue matériaux"],
        ),
        "candidates": [
            ("excellent",  "Senior Ingénieur Mécanique",    ["SolidWorks","CATIA","Calcul de structure","Résistance des matériaux","ANSYS","Normes ISO","Fatigue matériaux"], 6, 5, "ENIM",   0.93),
            ("bon",        "Ingénieur Mécanique",           ["SolidWorks","CATIA","Calcul de structure","Résistance des matériaux","ANSYS"],                                    3, 5, "ENIM",   0.82),
            ("a_evaluer",  "Technicien Mécanique",          ["SolidWorks","Dessin technique","Maintenance mécanique"],                                                           4, 2, "",       0.48),
            ("junior",     "Stagiaire Génie Mécanique",     ["SolidWorks","Résistance des matériaux"],                                                                           0, 5, "ENIM",   0.38),
            ("adjacent",   "Ingénieur Industriel",          ["Lean manufacturing","AMDEC","5S","Gestion production","SolidWorks"],                                                4, 5, "",       0.52),
        ],
    },

    # ══════════════════════════════════════════════════════ Ingénierie — Génie Civil
    {
        "id": "ingenierie_genie_civil",
        "domain": "ingenierie",
        "offre": _build_offer(
            "Ingénieur Génie Civil",
            "Ingénieur génie civil 3 ans. AutoCAD, béton armé, suivi chantier, métrés. Revit, MS Project apprécié. Bac+5.",
            ["AutoCAD", "Béton armé", "Suivi chantier", "Métrés"],
            ["Revit", "MS Project", "Normes NF", "VRD"],
        ),
        "candidates": [
            ("excellent",  "Senior Ingénieur Génie Civil",  ["AutoCAD","Béton armé","Suivi chantier","Métrés","Revit","MS Project","Normes NF","VRD"],  6, 5, "ENIT",   0.93),
            ("bon",        "Ingénieur Génie Civil",         ["AutoCAD","Béton armé","Suivi chantier","Métrés","Revit"],                                   3, 5, "ENIT",   0.82),
            ("a_evaluer",  "Conducteur de Travaux",         ["Suivi chantier","AutoCAD","Métrés","Sécurité chantier"],                                     5, 3, "",       0.58),
            ("junior",     "Stagiaire Génie Civil",         ["AutoCAD","Béton armé"],                                                                      0, 5, "ENIT",   0.38),
            ("adjacent",   "Architecte",                    ["AutoCAD","ArchiCAD","Dessin architectural","Plans","Revit"],                                   4, 5, "ENAU",   0.52),
        ],
    },

    # ══════════════════════════════════════════════════════ Ingénierie — Qualité
    {
        "id": "ingenierie_qualite",
        "domain": "ingenierie",
        "offre": _build_offer(
            "Ingénieur Qualité",
            "Ingénieur qualité 3 ans. ISO 9001, AMDEC, 8D, audits qualité. SPC, Lean, IATF apprécié.",
            ["Qualité", "ISO 9001", "AMDEC", "8D"],
            ["SPC", "Lean", "IATF 16949", "MSA"],
        ),
        "candidates": [
            ("excellent",  "Senior Ingénieur Qualité",      ["Qualité","ISO 9001","AMDEC","8D","SPC","Lean","IATF 16949","MSA"],  5, 5, "ENIM",   0.93),
            ("bon",        "Ingénieur Qualité",             ["Qualité","ISO 9001","AMDEC","8D","SPC"],                              3, 5, "ENIM",   0.82),
            ("a_evaluer",  "Technicien Qualité",            ["Qualité","ISO 9001","Contrôle qualité","Audits"],                    4, 2, "",       0.55),
            ("junior",     "Stagiaire Qualité",             ["Qualité","ISO 9001","AMDEC"],                                         0, 5, "ENIM",   0.38),
            ("adjacent",   "Ingénieur Production",          ["Gestion production","Lean","5S","AMDEC","Amélioration continue"],    4, 5, "",       0.55),
        ],
    },

    # ══════════════════════════════════════════════════════ Gestion de projet
    {
        "id": "gestion_projet",
        "domain": "management",
        "offre": _build_offer(
            "Chef de Projet IT",
            "Chef de projet IT 5 ans. Agile Scrum, Jira, gestion des risques, planning, budget. PMP ou PRINCE2 apprécié.",
            ["Gestion de projet", "Agile", "Scrum", "Gestion des risques", "Planning"],
            ["PMP", "PRINCE2", "Jira", "Confluence"],
        ),
        "candidates": [
            ("excellent",  "Senior Chef de Projet IT",      ["Gestion de projet","Agile","Scrum","Gestion des risques","Planning","PMP","Jira","Confluence"], 7, 5, "IHEC",   0.93),
            ("bon",        "Chef de Projet IT",             ["Gestion de projet","Agile","Scrum","Gestion des risques","Planning","Jira"],                    4, 5, "ESPRIT", 0.82),
            ("a_evaluer",  "Chef de Projet Junior",         ["Gestion de projet","Agile","Jira"],                                                              2, 3, "",       0.55),
            ("junior",     "Développeur aspirant PM",       ["React","JavaScript","Agile"],                                                                     3, 3, "",       0.32),
            ("adjacent",   "Scrum Master",                  ["Agile","Scrum","Kanban","Facilitation","Jira","Confluence"],                                      4, 5, "",       0.65),
        ],
    },

    # ══════════════════════════════════════════════════════ Supply Chain
    {
        "id": "supply_chain",
        "domain": "logistique",
        "offre": _build_offer(
            "Responsable Supply Chain",
            "Supply chain manager 4 ans. SAP, gestion stocks, planification, approvisionnement, transport. S&OP, Lean apprécié.",
            ["Supply Chain", "SAP", "Gestion stocks", "Planification", "Approvisionnement"],
            ["S&OP", "Lean", "Transport", "WMS"],
        ),
        "candidates": [
            ("excellent",  "Senior Supply Chain Manager",   ["Supply Chain","SAP","Gestion stocks","Planification","Approvisionnement","S&OP","Lean","WMS"],  6, 5, "IHEC",   0.93),
            ("bon",        "Supply Chain Manager",          ["Supply Chain","SAP","Gestion stocks","Planification","Approvisionnement"],                       4, 5, "IHEC",   0.82),
            ("a_evaluer",  "Gestionnaire Stocks",           ["Gestion stocks","SAP","Inventaires","Réapprovisionnement"],                                      3, 3, "",       0.58),
            ("junior",     "Assistant Logistique",          ["Logistique","Stocks","Transport"],                                                                2, 3, "",       0.42),
            ("adjacent",   "Responsable Achats",            ["Achats","Négociation fournisseurs","SAP","Appels d'offres","Sourcing"],                           4, 5, "",       0.60),
        ],
    },

    # ══════════════════════════════════════════════════════ Commercial / Ventes
    {
        "id": "commercial_senior",
        "domain": "commerce",
        "offre": _build_offer(
            "Responsable Commercial Senior",
            "Commercial senior 5 ans B2B. Salesforce, négociation, grands comptes, prospection. HubSpot, reporting KPI apprécié.",
            ["Vente B2B", "CRM", "Salesforce", "Négociation", "Gestion grands comptes"],
            ["HubSpot", "Marketing digital", "Reporting KPI"],
        ),
        "candidates": [
            ("excellent",  "Senior Commercial B2B",         ["Vente B2B","CRM","Salesforce","Négociation","Gestion grands comptes","HubSpot","Reporting KPI"], 7, 5, "IHEC",   0.93),
            ("bon",        "Responsable Commercial",        ["Vente B2B","CRM","Salesforce","Négociation","Gestion grands comptes"],                            4, 5, "IHEC",   0.82),
            ("a_evaluer",  "Commercial Terrain",            ["Vente","Prospection","Négociation","Service client"],                                              3, 3, "",       0.58),
            ("junior",     "Vendeur Junior",                ["Vente","Service client"],                                                                          1, 2, "",       0.32),
            ("adjacent",   "Business Developer",            ["Développement commercial","Partenariats","Négociation","Prospection","CRM"],                       4, 5, "",       0.68),
        ],
    },

    # ══════════════════════════════════════════════════════ Design UX/UI
    {
        "id": "design_ux",
        "domain": "design",
        "offre": _build_offer(
            "UX/UI Designer Senior",
            "UX/UI Designer 3 ans. Figma, prototypage, user research, design system. Adobe XD, CSS apprécié.",
            ["Figma", "UX Design", "Prototypage", "User Research"],
            ["Design System", "Adobe XD", "CSS", "Zeplin"],
        ),
        "candidates": [
            ("excellent",  "Senior UX/UI Designer",         ["Figma","UX Design","Prototypage","User Research","Design System","Adobe XD","CSS","Zeplin"],  5, 5, "ESAD",   0.93),
            ("bon",        "UX/UI Designer",                ["Figma","UX Design","Prototypage","User Research","Design System"],                              3, 5, "ESPRIT", 0.82),
            ("a_evaluer",  "Graphiste",                     ["Photoshop","Illustrator","InDesign","Figma"],                                                    4, 3, "",       0.45),
            ("junior",     "Stagiaire UX Design",           ["Figma","UX Design"],                                                                             0, 5, "ESAD",   0.38),
            ("adjacent",   "Product Designer",              ["Figma","UX Design","Design System","Prototypage","User stories"],                                 3, 5, "",       0.68),
        ],
    },

    # ══════════════════════════════════════════════════════ Enseignement
    {
        "id": "enseignement_maths",
        "domain": "education",
        "offre": _build_offer(
            "Professeur Mathématiques",
            "Professeur de mathématiques lycée. Master mathématiques requis. Pédagogie, cours, examens. Informatique apprécié.",
            ["Mathématiques", "Pédagogie", "Cours", "Gestion classe"],
            ["Statistiques", "Informatique", "Soutien scolaire"],
        ),
        "candidates": [
            ("excellent",  "Professeur Mathématiques",       ["Mathématiques","Pédagogie","Cours","Gestion classe","Statistiques","Informatique"],  8, 5, "ENS Tunis",  0.93),
            ("bon",        "Enseignant Mathématiques",       ["Mathématiques","Pédagogie","Cours","Gestion classe"],                                 4, 5, "FSM",        0.82),
            ("a_evaluer",  "Formateur Adultes Maths",        ["Mathématiques","Formation adultes","Pédagogie"],                                      5, 3, "",           0.60),
            ("junior",     "Doctorant Mathématiques",        ["Mathématiques","Statistiques","Recherche"],                                           1, 6, "FSM",        0.48),
            ("adjacent",   "Professeur Physique-Chimie",     ["Physique","Chimie","Pédagogie","Cours","Gestion classe","Mathématiques"],              6, 5, "FSM",        0.60),
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Construction des paires (offre, CV, score)
# ─────────────────────────────────────────────────────────────────────────────

def build_annotations(catalog: list, wrong_pool: list) -> list:
    annotations = []

    for job in catalog:
        offre = job["offre"]
        domain = job["domain"]

        # Niveaux du même domaine
        for level, poste, skills, exp, formation, school, target in job["candidates"]:
            cv = _build_candidate(poste, skills, exp, formation, school)
            annotations.append({
                "offre": offre,
                "cv": cv,
                "score": target,
                "label": f"{job['id']} — {level}",
            })

        # 3 CVs de mauvais domaine pour ce poste
        wrong_choices = [w for w in wrong_pool if w["domain"] != domain]
        for w in random.sample(wrong_choices, min(3, len(wrong_choices))):
            cv = _build_candidate(
                w["poste"], w["skills"], w["exp"], w["formation"], w["school"]
            )
            annotations.append({
                "offre": offre,
                "cv": cv,
                "score": w["score"],
                "label": f"{job['id']} — wrong_domain_{w['domain']}",
            })

    return annotations


# ─────────────────────────────────────────────────────────────────────────────
# MLP (même architecture)
# ─────────────────────────────────────────────────────────────────────────────

class ScoringMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, 128), nn.ReLU(), nn.Dropout(0.15),
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.10),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1) * 100


def augment_realistic(examples: list, n: int = 4000) -> list:
    result = list(examples)
    for _ in range(n):
        if random.random() < 0.65:
            base = random.choice(examples)
            fs, label = base[:5], base[5]
            noise = [random.gauss(0, 0.04) for _ in range(5)]
            fs2 = [max(0.0, min(1.0, f + no)) for f, no in zip(fs, noise)]
            delta = sum(noise[i] * [0.22, 0.32, 0.20, 0.14, 0.12][i] for i in range(5))
            label2 = max(0.18, min(0.95, label + delta))
        else:
            a, b = random.sample(examples, 2)
            alpha = random.random()
            fs2 = [a[i] * alpha + b[i] * (1 - alpha) for i in range(5)]
            label2 = a[5] * alpha + b[5] * (1 - alpha)
        result.append(fs2 + [label2])
    return result


def extract_features(scorer: BERTMatchingScorer, annotations: list) -> list:
    rows = []
    for i, ann in enumerate(annotations):
        try:
            _, details = scorer.score(ann["offre"], ann["cv"])
            sem_sim       = details["bert_semantic"]
            skill_rate    = details["bert_skills"]
            exp_score     = details["experience"] / 100
            form_score    = details["formation"] / 100
            criteres      = details.get("criteres", {}).get("apprecies", [])
            apr_rate      = (sum(1 for c in criteres if c.get("matched")) / len(criteres)
                             if criteres else 0.5)
            rows.append([sem_sim, skill_rate, exp_score, form_score, apr_rate, ann["score"]])
            print(f"  [{i+1:3d}/{len(annotations)}] {ann['label'][:45]:<45} target={ann['score']:.2f}")
        except Exception as e:
            print(f"  [{i+1:3d}] ERREUR {ann.get('label', '?')}: {e}")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("TalentMatch — Generation programmatique MLP Dataset")
    print("=" * 70)

    print("\n1) Construction des annotations...")
    annotations = build_annotations(CATALOG, WRONG_DOMAIN_POOL)
    print(f"   {len(annotations)} paires generees ({len(CATALOG)} postes × ~5 niveaux + cross-domain)")

    print("\n2) Chargement du scorer BERT v2.0...")
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    print(f"   Modele v2.0={scorer._use_v2}")

    print(f"\n3) Extraction features BERT sur {len(annotations)} paires...")
    raw_data = extract_features(scorer, annotations)
    print(f"   {len(raw_data)} exemples extraits")

    print("\n4) Augmentation...")
    augmented = augment_realistic(raw_data, n=4000)
    random.shuffle(augmented)
    print(f"   Total: {len(augmented)} exemples apres augmentation")

    print("\n5) Preparation dataset...")
    tensors = torch.tensor(augmented, dtype=torch.float32)
    X, y = tensors[:, :5], tensors[:, 5]
    split = int(len(X) * 0.85)
    train_ds = TensorDataset(X[:split], y[:split])
    loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    X_val, y_val = X[split:], y[split:]

    print("\n6) Entrainement MLP...")
    mlp = ScoringMLP()
    optimizer = torch.optim.AdamW(mlp.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=300)
    best_val, best_state = float('inf'), None

    for epoch in range(300):
        mlp.train()
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = F.mse_loss(mlp(xb) / 100, yb)
            loss.backward()
            optimizer.step()
        scheduler.step()
        if (epoch + 1) % 60 == 0:
            mlp.eval()
            with torch.no_grad():
                val_loss = F.mse_loss(mlp(X_val) / 100, y_val).item()
            print(f"   Epoch {epoch+1:3d}/300 | Val Loss: {val_loss:.5f}")
            if val_loss < best_val:
                best_val = val_loss
                best_state = {k: v.clone() for k, v in mlp.state_dict().items()}

    mlp.load_state_dict(best_state)
    mlp.eval()

    print("\n7) Verification sur cas de reference...")
    print("-" * 65)
    VERIF = [
        ([0.90, 1.00, 1.00, 1.00, 1.00], "Excellent parfait"),
        ([0.72, 1.00, 1.00, 1.00, 0.60], "Excellent (sem=0.72)"),
        ([0.65, 0.80, 0.85, 0.85, 0.50], "Bon profil (sem=0.65, sk=80%)"),
        ([0.55, 0.65, 0.75, 0.75, 0.40], "Bon profil limite (sem=0.55)"),
        ([0.48, 0.55, 0.65, 0.65, 0.30], "A evaluer (sem=0.48, sk=55%)"),
        ([0.38, 0.30, 0.40, 0.40, 0.10], "A evaluer bas (sem=0.38, sk=30%)"),
        ([0.22, 0.08, 0.25, 0.30, 0.00], "Non adapte (sem=0.22, sk=8%)"),
        ([0.08, 0.00, 0.20, 0.20, 0.00], "Hors domaine total"),
        ([0.62, 0.78, 0.15, 1.00, 0.50], "Stage/Junior (exp faible)"),
        ([0.78, 0.85, 1.00, 1.00, 0.80], "Senior confirme"),
    ]
    with torch.no_grad():
        for features, label in VERIF:
            score = float(mlp(torch.tensor([features], dtype=torch.float32)))
            decision = ("Excellent" if score >= 80 else "Bon profil" if score >= 65
                        else "A evaluer" if score >= 50 else "Non adapte")
            print(f"  {label:<40} -> {score:5.1f}%  [{decision}]")

    print("\n8) Sauvegarde...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(mlp.state_dict(), os.path.join(MODEL_DIR, 'scoring_mlp.pt'))

    config = {
        "version": "TalentMatch-BERT v2.0 — MLP generation programmatique",
        "mlp_input": ["sem_sim", "skill_rate", "exp_score", "formation_score", "appreciated_rate"],
        "mlp_dims": [5, 128, 64, 32, 1],
        "thresholds": {"excellent": 80, "bon_profil": 65, "a_evaluer": 50, "non_adapte": 0},
        "decisions": {
            "excellent": "Excellent candidat",
            "bon_profil": "Bon profil - Entretien recommande",
            "a_evaluer":  "Profil partiel - A evaluer",
            "non_adapte": "Profil non adapte",
        },
        "training": {
            "n_annotations_base": len(annotations),
            "n_extracted": len(raw_data),
            "n_augmented": len(augmented),
            "val_loss_finale": round(best_val, 6),
            "n_postes_catalogue": len(CATALOG),
            "domaines": list({j["domain"] for j in CATALOG}),
        },
    }
    with open(os.path.join(MODEL_DIR, 'scoring_config.json'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"   scoring_mlp.pt sauvegarde dans {MODEL_DIR}")
    print(f"   Annotations base    : {len(annotations)}")
    print(f"   Apres augmentation  : {len(augmented)}")
    print(f"   Val Loss finale     : {best_val:.5f}")
    print("\nGeneration et calibration terminees avec succes!")


if __name__ == "__main__":
    main()
