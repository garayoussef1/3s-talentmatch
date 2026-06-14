"""
Génération du dataset universel pour réentraîner le FusionMLP.

50 domaines professionnels × plusieurs profils CV × plusieurs niveaux d'offre
→ ~3000 paires avec labels qualité basés sur la compatibilité réelle.

Lancement :
    python -m scripts.generate_mlp_dataset_universal

Sortie : data/mlp_training_universal/dataset.csv
"""
from __future__ import annotations

import csv
import os
import sys
import random
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# ── Setup path ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# ── Constantes ────────────────────────────────────────────────────────────────
OUT_DIR  = Path(__file__).resolve().parents[2] / "data" / "mlp_training_universal"
OUT_FILE = OUT_DIR / "dataset.csv"
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ─────────────────────────────────────────────────────────────────────────────
# 50 PROFILS DOMAINES PROFESSIONNELS
# Chaque domaine : isco, name, skills (requis), edu_min, exp_range, titre_offre
# ─────────────────────────────────────────────────────────────────────────────
DOMAINS: List[Dict] = [
    # ── IT / INFORMATIQUE ────────────────────────────────────────────────────
    {"isco": "25", "name": "Développement React/Frontend",
     "skills": ["react", "javascript", "typescript", "html", "css", "git", "webpack", "jest"],
     "adjacent_skills": ["vue.js", "angular", "node.js", "graphql", "redux"],
     "edu_min": 3, "exp_range": (0, 8), "edu_label": "Bac+3",
     "titre": "Développeur Front-End React",
     "desc": "Développer des interfaces utilisateurs réactives avec React et TypeScript. Intégration d'APIs REST."},

    {"isco": "25", "name": "Développement Backend Python/Django",
     "skills": ["python", "django", "flask", "postgresql", "api rest", "git", "docker", "linux"],
     "adjacent_skills": ["fastapi", "redis", "celery", "aws", "microservices"],
     "edu_min": 3, "exp_range": (0, 8), "edu_label": "Bac+3",
     "titre": "Développeur Backend Python",
     "desc": "Conception et développement d'APIs REST performantes avec Django/FastAPI. Gestion base de données."},

    {"isco": "25", "name": "DevOps / Cloud Infrastructure",
     "skills": ["docker", "kubernetes", "ci/cd", "aws", "terraform", "linux", "ansible", "git"],
     "adjacent_skills": ["gcp", "azure", "helm", "prometheus", "grafana", "nginx"],
     "edu_min": 3, "exp_range": (2, 10), "edu_label": "Bac+3",
     "titre": "Ingénieur DevOps",
     "desc": "Automatisation des pipelines CI/CD, déploiement cloud, orchestration Kubernetes."},

    {"isco": "25", "name": "Data Science / Machine Learning",
     "skills": ["python", "machine learning", "deep learning", "pandas", "scikit-learn", "tensorflow", "sql", "statistiques"],
     "adjacent_skills": ["pytorch", "nlp", "computer vision", "spark", "hadoop", "r"],
     "edu_min": 5, "exp_range": (0, 8), "edu_label": "Bac+5",
     "titre": "Data Scientist",
     "desc": "Développement de modèles prédictifs, analyse de données, déploiement de solutions ML en production."},

    {"isco": "25", "name": "Cybersécurité",
     "skills": ["pentesting", "sécurité réseau", "firewall", "siem", "analyse de logs", "linux", "python", "cryptographie"],
     "adjacent_skills": ["nmap", "metasploit", "burp suite", "iso 27001", "gestion des risques"],
     "edu_min": 3, "exp_range": (1, 10), "edu_label": "Bac+3",
     "titre": "Analyste Cybersécurité",
     "desc": "Protection des systèmes d'information, tests d'intrusion, gestion des incidents de sécurité."},

    {"isco": "25", "name": "Développement Mobile iOS/Android",
     "skills": ["swift", "kotlin", "ios", "android", "react native", "git", "api rest", "tests unitaires"],
     "adjacent_skills": ["flutter", "xcode", "android studio", "firebase", "app store"],
     "edu_min": 3, "exp_range": (0, 7), "edu_label": "Bac+3",
     "titre": "Développeur Mobile",
     "desc": "Développement d'applications mobiles natives iOS et Android. Publication sur les stores."},

    {"isco": "25", "name": "UX/UI Design",
     "skills": ["figma", "ux design", "ui design", "prototypage", "wireframes", "user research", "adobe xd", "sketch"],
     "adjacent_skills": ["design system", "accessibility", "usability testing", "photoshop", "motion design"],
     "edu_min": 3, "exp_range": (0, 8), "edu_label": "Bac+3",
     "titre": "Designer UX/UI",
     "desc": "Conception d'expériences utilisateur, création de maquettes, tests d'utilisabilité."},

    {"isco": "25", "name": "Data Engineer / Big Data",
     "skills": ["spark", "hadoop", "python", "sql", "etl", "airflow", "kafka", "data warehouse"],
     "adjacent_skills": ["databricks", "snowflake", "dbt", "aws glue", "bigquery"],
     "edu_min": 5, "exp_range": (1, 9), "edu_label": "Bac+5",
     "titre": "Data Engineer",
     "desc": "Construction et maintenance de pipelines de données, architecture data lakehouse."},

    # ── SANTÉ ─────────────────────────────────────────────────────────────────
    {"isco": "22", "name": "Médecine Générale",
     "skills": ["médecine générale", "diagnostic clinique", "pharmacologie", "prescription", "dossier médical", "pédiatrie", "urgences"],
     "adjacent_skills": ["cardiologie basique", "dermatologie", "médecine préventive"],
     "edu_min": 8, "exp_range": (0, 20), "edu_label": "Bac+8",
     "titre": "Médecin Généraliste",
     "desc": "Prise en charge globale des patients, suivi médical, prescription et orientation vers spécialistes."},

    {"isco": "22", "name": "Chirurgie",
     "skills": ["chirurgie générale", "bloc opératoire", "anatomie", "techniques chirurgicales", "soins post-opératoires"],
     "adjacent_skills": ["laparoscopie", "chirurgie orthopédique", "anesthésie locorégionale"],
     "edu_min": 8, "exp_range": (0, 20), "edu_label": "Bac+8",
     "titre": "Chirurgien",
     "desc": "Réalisation d'interventions chirurgicales en bloc opératoire, suivi pré et post-opératoire."},

    {"isco": "22", "name": "Pharmacie",
     "skills": ["pharmacologie", "dispensation médicaments", "conseil patient", "ordonnances", "pharmacovigilance", "biologie"],
     "adjacent_skills": ["chimie pharmaceutique", "réglementation pharmaceutique", "industrie pharmaceutique"],
     "edu_min": 5, "exp_range": (0, 15), "edu_label": "Bac+5",
     "titre": "Pharmacien",
     "desc": "Dispensation de médicaments, conseil pharmaceutique, gestion des stocks et ordonnances."},

    {"isco": "32", "name": "Soins infirmiers",
     "skills": ["soins infirmiers", "administration médicaments", "surveillance patient", "soins de base", "dossier de soins", "hygiène"],
     "adjacent_skills": ["soins intensifs", "urgences", "soins à domicile", "pédiatrie"],
     "edu_min": 3, "exp_range": (0, 15), "edu_label": "Bac+3",
     "titre": "Infirmier(ère)",
     "desc": "Réalisation de soins infirmiers, administration des médicaments, surveillance et accompagnement des patients."},

    {"isco": "32", "name": "Kinésithérapie",
     "skills": ["kinésithérapie", "massages thérapeutiques", "rééducation", "bilan fonctionnel", "physiothérapie", "anatomie"],
     "adjacent_skills": ["ostéopathie", "sport et rééducation", "rééducation neurologique"],
     "edu_min": 3, "exp_range": (0, 15), "edu_label": "Bac+3",
     "titre": "Kinésithérapeute",
     "desc": "Rééducation et réadaptation des patients, massages thérapeutiques, bilan fonctionnel."},

    # ── FINANCE / COMPTABILITÉ ────────────────────────────────────────────────
    {"isco": "24", "name": "Comptabilité Générale",
     "skills": ["comptabilité générale", "bilan", "compte de résultat", "tva", "clôture comptable", "excel", "saisie comptable"],
     "adjacent_skills": ["sage", "cegid", "audit", "fiscalité", "paie"],
     "edu_min": 2, "exp_range": (0, 12), "edu_label": "Bac+2",
     "titre": "Comptable",
     "desc": "Tenue de la comptabilité générale, préparation des bilans, déclarations fiscales et TVA."},

    {"isco": "24", "name": "Audit et Contrôle de Gestion",
     "skills": ["audit", "contrôle de gestion", "analyse financière", "budget", "reporting", "excel", "normes ifrs"],
     "adjacent_skills": ["consolidation", "sap", "tableau de bord", "kpis", "business intelligence"],
     "edu_min": 5, "exp_range": (0, 12), "edu_label": "Bac+5",
     "titre": "Auditeur / Contrôleur de Gestion",
     "desc": "Réalisation d'audits internes, contrôle de gestion, élaboration de budgets et tableaux de bord."},

    {"isco": "24", "name": "Finance d'Entreprise",
     "skills": ["finance d'entreprise", "modélisation financière", "valorisation", "excel", "m&a", "lbo", "due diligence"],
     "adjacent_skills": ["bloomberg", "python finance", "gestion de trésorerie", "levée de fonds"],
     "edu_min": 5, "exp_range": (0, 10), "edu_label": "Bac+5",
     "titre": "Analyste Financier",
     "desc": "Modélisation financière, analyse d'investissements, valorisation d'entreprises."},

    # ── RESSOURCES HUMAINES ───────────────────────────────────────────────────
    {"isco": "24", "name": "Recrutement",
     "skills": ["recrutement", "sourcing", "entretiens", "assessment center", "linkedin", "ats", "onboarding", "marque employeur"],
     "adjacent_skills": ["talent acquisition", "chasse de têtes", "rh généraliste", "employer branding"],
     "edu_min": 3, "exp_range": (0, 10), "edu_label": "Bac+3",
     "titre": "Chargé(e) de Recrutement",
     "desc": "Gestion complète du processus de recrutement, sourcing de candidats, conduite d'entretiens."},

    {"isco": "24", "name": "Ressources Humaines Généraliste",
     "skills": ["rh généraliste", "droit du travail", "paie", "gestion administrative rh", "formation", "relations sociales", "gpec"],
     "adjacent_skills": ["sirh", "people analytics", "hrbp", "gestion des talents"],
     "edu_min": 3, "exp_range": (1, 15), "edu_label": "Bac+3",
     "titre": "Responsable RH",
     "desc": "Gestion RH globale, relations sociales, paie, formation et développement des compétences."},

    # ── MARKETING / COMMUNICATION ─────────────────────────────────────────────
    {"isco": "24", "name": "Marketing Digital",
     "skills": ["marketing digital", "seo", "sea", "google analytics", "réseaux sociaux", "content marketing", "emailing", "crm"],
     "adjacent_skills": ["google ads", "facebook ads", "hubspot", "growth hacking", "a/b testing"],
     "edu_min": 3, "exp_range": (0, 10), "edu_label": "Bac+3",
     "titre": "Chargé(e) de Marketing Digital",
     "desc": "Gestion de la stratégie digitale, SEO/SEA, animation des réseaux sociaux et campagnes emailing."},

    {"isco": "24", "name": "Communication / RP",
     "skills": ["communication", "relations presse", "rédaction", "relations publiques", "événementiel", "community management"],
     "adjacent_skills": ["attaché de presse", "communication institutionnelle", "brand content"],
     "edu_min": 3, "exp_range": (0, 10), "edu_label": "Bac+3",
     "titre": "Chargé(e) de Communication",
     "desc": "Mise en oeuvre de la stratégie de communication, relations presse et médias."},

    # ── DROIT ─────────────────────────────────────────────────────────────────
    {"isco": "26", "name": "Droit des Affaires",
     "skills": ["droit des affaires", "droit des contrats", "droit des sociétés", "contentieux", "conseil juridique", "rédaction contrats"],
     "adjacent_skills": ["droit commercial", "droit de la concurrence", "m&a juridique"],
     "edu_min": 5, "exp_range": (0, 15), "edu_label": "Bac+5",
     "titre": "Juriste en Droit des Affaires",
     "desc": "Conseil juridique, rédaction et négociation de contrats commerciaux, gestion des contentieux."},

    {"isco": "26", "name": "Droit du Travail / RH Juridique",
     "skills": ["droit du travail", "relations sociales", "négociation collective", "contentieux prud'homal", "conseil rh juridique"],
     "adjacent_skills": ["droit de la sécurité sociale", "droit de la protection sociale"],
     "edu_min": 5, "exp_range": (0, 15), "edu_label": "Bac+5",
     "titre": "Juriste Droit Social",
     "desc": "Conseil en droit du travail, gestion des relations sociales et contentieux prudhomaux."},

    # ── ENSEIGNEMENT / FORMATION ───────────────────────────────────────────────
    {"isco": "23", "name": "Enseignement Secondaire",
     "skills": ["pédagogie", "animation de cours", "évaluation", "gestion de classe", "programmes scolaires", "sciences"],
     "adjacent_skills": ["accompagnement individualisé", "numérique éducatif", "soutien scolaire"],
     "edu_min": 5, "exp_range": (0, 20), "edu_label": "Bac+5",
     "titre": "Enseignant(e)",
     "desc": "Enseignement en collège ou lycée, préparation et animation de cours, évaluation des élèves."},

    {"isco": "23", "name": "Formation Professionnelle",
     "skills": ["animation de formation", "ingénierie pédagogique", "e-learning", "présentiel", "évaluation des acquis"],
     "adjacent_skills": ["lms", "moodle", "certification qualiopi", "bilan de compétences"],
     "edu_min": 3, "exp_range": (0, 15), "edu_label": "Bac+3",
     "titre": "Formateur(trice) Professionnel(le)",
     "desc": "Conception et animation de formations professionnelles en présentiel et distanciel."},

    # ── INGÉNIERIE / BTP ──────────────────────────────────────────────────────
    {"isco": "21", "name": "Génie Civil / BTP",
     "skills": ["génie civil", "calcul de structure", "béton armé", "autocad", "planification chantier", "suivi de travaux"],
     "adjacent_skills": ["revit", "robot structural", "eurocodes", "aménagement urbain"],
     "edu_min": 5, "exp_range": (0, 15), "edu_label": "Bac+5",
     "titre": "Ingénieur Génie Civil",
     "desc": "Conception et suivi de projets de construction, calculs de structure, coordination chantiers."},

    {"isco": "21", "name": "Génie Électrique / Électronique",
     "skills": ["électricité industrielle", "électronique", "automatisme", "plc", "variateurs", "schémas électriques", "autocad electrical"],
     "adjacent_skills": ["robotique", "cfc", "hta/hbt", "maintenance électrique"],
     "edu_min": 3, "exp_range": (0, 12), "edu_label": "Bac+3",
     "titre": "Ingénieur Électrique",
     "desc": "Conception de systèmes électriques industriels, automatisme et maintenance."},

    {"isco": "21", "name": "Génie Mécanique",
     "skills": ["solidworks", "catia", "conception mécanique", "calcul mécanique", "fabrication", "dessin industriel"],
     "adjacent_skills": ["ansys", "cfao", "impression 3d", "lean manufacturing"],
     "edu_min": 3, "exp_range": (0, 12), "edu_label": "Bac+3",
     "titre": "Ingénieur Mécanique",
     "desc": "Conception de pièces et systèmes mécaniques, simulation numérique et industrialisation."},

    {"isco": "21", "name": "Architecture",
     "skills": ["architecture", "autocad", "revit", "permis de construire", "conception architecturale", "réglementation construction"],
     "adjacent_skills": ["bim", "modélisation 3d", "aménagement intérieur", "paysagisme"],
     "edu_min": 5, "exp_range": (0, 15), "edu_label": "Bac+5",
     "titre": "Architecte",
     "desc": "Conception architecturale, dépôt de permis de construire, suivi de chantier."},

    # ── GESTION DE PROJET / MANAGEMENT ────────────────────────────────────────
    {"isco": "24", "name": "Gestion de Projet IT",
     "skills": ["gestion de projet", "agile", "scrum", "jira", "planification", "gestion des risques", "budget projet"],
     "adjacent_skills": ["prince2", "pmp", "kanban", "ms project", "safe"],
     "edu_min": 5, "exp_range": (2, 15), "edu_label": "Bac+5",
     "titre": "Chef de Projet IT",
     "desc": "Pilotage de projets informatiques en méthode agile, coordination équipes, gestion du budget."},

    {"isco": "24", "name": "Supply Chain / Logistique",
     "skills": ["supply chain", "logistique", "gestion de stock", "approvisionnement", "sap", "transport", "incoterms"],
     "adjacent_skills": ["lean", "5s", "kaizen", "wms", "douane"],
     "edu_min": 3, "exp_range": (0, 12), "edu_label": "Bac+3",
     "titre": "Responsable Supply Chain",
     "desc": "Gestion des flux logistiques, approvisionnement, optimisation des stocks et transports."},

    # ── COMMERCE / VENTE ──────────────────────────────────────────────────────
    {"isco": "52", "name": "Commerce B2B / Vente",
     "skills": ["développement commercial", "prospection", "négociation", "crm", "salesforce", "présentation commerciale", "closing"],
     "adjacent_skills": ["vente conseil", "account management", "business development", "key account"],
     "edu_min": 2, "exp_range": (0, 12), "edu_label": "Bac+2",
     "titre": "Commercial(e) B2B",
     "desc": "Développement et fidélisation d'un portefeuille clients entreprises, atteinte des objectifs commerciaux."},

    {"isco": "52", "name": "Commerce Immobilier",
     "skills": ["transaction immobilière", "estimation immobilière", "droit immobilier", "négociation", "prospection immobilière"],
     "adjacent_skills": ["gestion locative", "promotion immobilière", "expertise immobilière"],
     "edu_min": 2, "exp_range": (0, 15), "edu_label": "Bac+2",
     "titre": "Agent Immobilier",
     "desc": "Transaction, estimation et vente de biens immobiliers. Gestion du portefeuille clients."},

    # ── GRAPHISME / DESIGN CRÉATIF ─────────────────────────────────────────────
    {"isco": "26", "name": "Design Graphique",
     "skills": ["photoshop", "illustrator", "indesign", "graphisme", "identité visuelle", "mise en page", "typographie"],
     "adjacent_skills": ["after effects", "motion design", "print", "web design", "branding"],
     "edu_min": 3, "exp_range": (0, 10), "edu_label": "Bac+3",
     "titre": "Graphiste",
     "desc": "Création d'identités visuelles, supports de communication print et digital."},

    {"isco": "26", "name": "Journalisme / Rédaction",
     "skills": ["rédaction", "journalisme", "enquête", "reportage", "interview", "mise en page éditoriale", "anglais"],
     "adjacent_skills": ["presse écrite", "web journalisme", "podcast", "vidéo journalisme"],
     "edu_min": 3, "exp_range": (0, 12), "edu_label": "Bac+3",
     "titre": "Journaliste",
     "desc": "Production de contenus journalistiques, interviews, reportages terrain."},

    # ── PSYCHOLOGIE / SOCIAL ───────────────────────────────────────────────────
    {"isco": "26", "name": "Psychologie Clinique",
     "skills": ["psychologie clinique", "entretiens thérapeutiques", "bilan psychologique", "thérapies cognitivo-comportementales", "écoute active"],
     "adjacent_skills": ["psychothérapie", "neuropsychologie", "psychologie du travail"],
     "edu_min": 5, "exp_range": (0, 15), "edu_label": "Bac+5",
     "titre": "Psychologue Clinicien(ne)",
     "desc": "Suivi psychologique, bilans cliniques et accompagnement thérapeutique des patients."},

    {"isco": "26", "name": "Travail Social / Éducation Spécialisée",
     "skills": ["travail social", "accompagnement social", "éducation spécialisée", "protection de l'enfance", "insertion professionnelle"],
     "adjacent_skills": ["aide sociale", "médiation sociale", "droit social"],
     "edu_min": 3, "exp_range": (0, 15), "edu_label": "Bac+3",
     "titre": "Éducateur(trice) Spécialisé(e)",
     "desc": "Accompagnement de personnes en difficulté sociale, éducation spécialisée."},

    # ── TRADUCTION / LANGUES ───────────────────────────────────────────────────
    {"isco": "26", "name": "Traduction / Interprétariat",
     "skills": ["traduction", "anglais", "espagnol", "allemand", "terminologie", "outils de tao", "localisation"],
     "adjacent_skills": ["interprétation simultanée", "rédaction bilingue", "traduction juridique"],
     "edu_min": 3, "exp_range": (0, 15), "edu_label": "Bac+3",
     "titre": "Traducteur(trice)",
     "desc": "Traduction de documents techniques et commerciaux, localisation de contenus."},

    # ── HÔTELLERIE / RESTAURATION ─────────────────────────────────────────────
    {"isco": "51", "name": "Cuisine / Chef de Cuisine",
     "skills": ["cuisine française", "pâtisserie", "gestion cuisine", "haccp", "fiches techniques", "gestion des coûts"],
     "adjacent_skills": ["cuisine du monde", "gastronomie", "chef de partie", "traiteur"],
     "edu_min": 2, "exp_range": (0, 15), "edu_label": "Bac+2",
     "titre": "Chef Cuisinier",
     "desc": "Direction d'une brigade, élaboration des menus, gestion des commandes et contrôle qualité."},

    {"isco": "51", "name": "Hôtellerie / Réception",
     "skills": ["accueil hôtelier", "gestion réservations", "logiciel pms", "relation client", "front office", "anglais"],
     "adjacent_skills": ["conciergerie", "spa management", "yield management"],
     "edu_min": 2, "exp_range": (0, 12), "edu_label": "Bac+2",
     "titre": "Réceptionniste / Chef de Réception",
     "desc": "Accueil des clients, gestion des réservations et coordination des équipes de réception."},

    # ── ARTISANAT / INDUSTRIE ─────────────────────────────────────────────────
    {"isco": "74", "name": "Électricité Bâtiment / Industrie",
     "skills": ["électricité bâtiment", "électricité industrielle", "habilitation électrique", "lecture de plans", "câblage"],
     "adjacent_skills": ["automatisme", "plc", "dépannage électrique", "courants faibles"],
     "edu_min": 2, "exp_range": (0, 15), "edu_label": "Bac+2",
     "titre": "Électricien",
     "desc": "Installation et maintenance d'équipements électriques en bâtiment ou industrie."},

    {"isco": "72", "name": "Soudure / Chaudronnerie",
     "skills": ["soudure tig", "soudure mig", "chaudronnerie", "lecture de plans", "traçage", "assemblage métallique"],
     "adjacent_skills": ["soudure plasma", "tuyauterie industrielle", "contrôle qualité soudure"],
     "edu_min": 2, "exp_range": (0, 20), "edu_label": "Bac+2",
     "titre": "Soudeur / Chaudronnier",
     "desc": "Réalisation de soudures et assemblages métalliques selon les plans et procédures."},

    {"isco": "71", "name": "Maçonnerie / Gros Œuvre",
     "skills": ["maçonnerie", "béton", "coffrage", "fondations", "lecture de plans btp", "sécurité chantier"],
     "adjacent_skills": ["carrelage", "plâtrerie", "ravalement façade"],
     "edu_min": 0, "exp_range": (0, 20), "edu_label": "CAP/BEP",
     "titre": "Maçon",
     "desc": "Construction de murs, fondations et ouvrages en béton selon les plans architecturaux."},

    {"isco": "72", "name": "Mécanique Automobile",
     "skills": ["mécanique automobile", "diagnostic électronique", "entretien véhicule", "réparation moteur", "pneumatiques"],
     "adjacent_skills": ["carrosserie", "véhicules électriques", "contrôle technique"],
     "edu_min": 2, "exp_range": (0, 20), "edu_label": "Bac+2",
     "titre": "Mécanicien Automobile",
     "desc": "Entretien et réparation de véhicules, diagnostic électronique, montage pneumatiques."},

    # ── AGRICULTURE / ENVIRONNEMENT ────────────────────────────────────────────
    {"isco": "61", "name": "Agriculture / Agronomie",
     "skills": ["agronomie", "cultures", "irrigation", "phytosanitaires", "machinisme agricole", "gestion d'exploitation"],
     "adjacent_skills": ["agriculture biologique", "permaculture", "viticulture"],
     "edu_min": 2, "exp_range": (0, 20), "edu_label": "Bac+2",
     "titre": "Technicien(ne) Agricole",
     "desc": "Conseil et suivi technique des exploitations agricoles, gestion des cultures."},

    # ── TRANSPORT / LOGISTIQUE ─────────────────────────────────────────────────
    {"isco": "83", "name": "Transport / Conduite",
     "skills": ["permis poids lourd", "code de la route", "logistique transport", "gestion des livraisons", "fimo", "carte conducteur"],
     "adjacent_skills": ["transport international", "adr matières dangereuses", "gps"],
     "edu_min": 0, "exp_range": (0, 20), "edu_label": "CAP/BEP",
     "titre": "Chauffeur Poids Lourd",
     "desc": "Livraison de marchandises en France et Europe, gestion des tournées et documents de transport."},

    # ── ADMINISTRATION PUBLIQUE ────────────────────────────────────────────────
    {"isco": "41", "name": "Administration / Secrétariat",
     "skills": ["secrétariat", "pack office", "word", "excel", "accueil", "rédaction administrative", "gestion agenda"],
     "adjacent_skills": ["gestion documentaire", "archivage", "comptabilité basique"],
     "edu_min": 2, "exp_range": (0, 15), "edu_label": "Bac+2",
     "titre": "Assistant(e) Administratif(ve)",
     "desc": "Gestion administrative, accueil téléphonique, rédaction de courriers et gestion documentaire."},

    # ── SÉCURITÉ / PRÉVENTION ─────────────────────────────────────────────────
    {"isco": "54", "name": "Sécurité / Protection",
     "skills": ["sécurité", "surveillance", "contrôle d'accès", "habilitation", "ssiap", "gestes et postures", "secourisme"],
     "adjacent_skills": ["sécurité incendie", "gardiennage", "prévention des risques"],
     "edu_min": 0, "exp_range": (0, 20), "edu_label": "CAP/BEP",
     "titre": "Agent de Sécurité",
     "desc": "Surveillance de site, contrôle des accès, prévention des risques et gestion des incidents."},

    # ── BIOLOGIE / CHIMIE / RECHERCHE ─────────────────────────────────────────
    {"isco": "21", "name": "Biologie / Recherche Scientifique",
     "skills": ["biologie moléculaire", "techniques de laboratoire", "pcr", "microscopie", "rédaction scientifique", "statistiques"],
     "adjacent_skills": ["biochimie", "génétique", "bioinformatique", "r", "python"],
     "edu_min": 5, "exp_range": (0, 15), "edu_label": "Bac+5",
     "titre": "Biologiste / Chercheur",
     "desc": "Recherche scientifique en laboratoire, expérimentation, rédaction de publications."},

    {"isco": "21", "name": "Chimie Industrielle",
     "skills": ["chimie industrielle", "analyse chimique", "chromatographie", "sécurité laboratoire", "bpf", "contrôle qualité"],
     "adjacent_skills": ["chimie organique", "industries pharmaceutiques", "iso 9001"],
     "edu_min": 3, "exp_range": (0, 12), "edu_label": "Bac+3",
     "titre": "Technicien(ne) Chimiste",
     "desc": "Réalisation d'analyses chimiques, contrôle qualité des produits, gestion des équipements."},

    # ── ENVIRONNEMENT / DÉVELOPPEMENT DURABLE ─────────────────────────────────
    {"isco": "21", "name": "Environnement / HSE",
     "skills": ["hse", "iso 14001", "analyse environnementale", "gestion des déchets", "réglementation", "audits environnementaux"],
     "adjacent_skills": ["bilan carbone", "développement durable", "energie renouvelable"],
     "edu_min": 3, "exp_range": (0, 12), "edu_label": "Bac+3",
     "titre": "Chargé(e) HSE",
     "desc": "Mise en oeuvre de la politique HSE, audits, gestion des risques environnementaux."},

    # ── OPTIQUE / PARAMÉDICAL ─────────────────────────────────────────────────
    {"isco": "32", "name": "Optique / Optométrie",
     "skills": ["optométrie", "verres correcteurs", "montures", "examen de vue", "adaptation lentilles", "conseil client"],
     "adjacent_skills": ["audioprothèse", "orthoptie", "basse vision"],
     "edu_min": 2, "exp_range": (0, 15), "edu_label": "Bac+2",
     "titre": "Opticien(ne)-Lunetier(e)",
     "desc": "Réalisation d'examens de vue, vente et montage de lunettes, adaptation de lentilles."},

    # ── PETITE ENFANCE ────────────────────────────────────────────────────────
    {"isco": "53", "name": "Petite Enfance / Crèche",
     "skills": ["petite enfance", "développement de l'enfant", "activités pédagogiques", "soins aux nourrissons", "protocoles hygiène"],
     "adjacent_skills": ["atsem", "auxiliaire puéricultrice", "animateur périscolaire"],
     "edu_min": 2, "exp_range": (0, 15), "edu_label": "Bac+2",
     "titre": "Auxiliaire de Puériculture",
     "desc": "Accueil et prise en charge des jeunes enfants en structure collective."},

    # ── MANAGEMENT / DIRECTION ────────────────────────────────────────────────
    {"isco": "13", "name": "Management Technique / DSI",
     "skills": ["management", "stratégie informatique", "gestion d'équipe", "budget it", "gouvernance it", "transformation digitale"],
     "adjacent_skills": ["codir", "it roadmap", "sécurité si", "cloud strategy"],
     "edu_min": 5, "exp_range": (5, 20), "edu_label": "Bac+5",
     "titre": "Directeur(trice) Technique / DSI",
     "desc": "Direction technique, définition de la stratégie informatique, management des équipes IT."},
]

# ─────────────────────────────────────────────────────────────────────────────
# Niveaux éducation : correspondance label → entier
# ─────────────────────────────────────────────────────────────────────────────
EDU_LEVELS = {
    "CAP/BEP": 1, "Bac": 1, "Bac+2": 2, "Bac+3": 3,
    "Bac+4": 4, "Bac+5": 5, "Bac+8": 8,
}

# ─────────────────────────────────────────────────────────────────────────────
# Profils CV par qualité de match
# ─────────────────────────────────────────────────────────────────────────────
def _build_pair(
    domain: Dict,
    cv_skill_rate: float,     # 0-1 : part des skills requises présentes dans le CV
    cv_edu: int,              # niveau éducation candidat
    cv_exp: int,              # années expérience candidat
    domain_match: str,        # "same", "adjacent", "different"
    adj_domain: Optional[Dict] = None,
) -> Dict:
    """Construit une paire (offre, CV) avec ses features et son label."""

    req_skills = domain["skills"]
    req_edu    = EDU_LEVELS.get(domain["edu_label"], domain["edu_min"])
    req_exp    = domain["exp_range"][0]   # expérience minimum requise

    # ── Skills du CV ─────────────────────────────────────────────────────────
    n_match = max(0, int(cv_skill_rate * len(req_skills)))

    if domain_match == "same":
        cv_skills = req_skills[:n_match] + domain.get("adjacent_skills", [])[:2]
    elif domain_match == "adjacent":
        # Quelques skills communs + skills de domaine adjacent
        adj = adj_domain or domain
        common = req_skills[:max(1, n_match // 2)]
        adj_s  = adj.get("skills", [])[:4]
        cv_skills = common + adj_s
    else:
        # Domaine différent : aucun skill commun
        adj = adj_domain or domain
        cv_skills = adj.get("skills", req_skills[:2])[:6]

    # ── Textes offre et CV ───────────────────────────────────────────────────
    offer_text = (
        f"{domain['titre']}. {domain['desc']} "
        f"Compétences requises : {', '.join(req_skills)}. "
        f"Expérience minimum : {req_exp} ans. Formation : {domain['edu_label']}."
    )
    cv_title = domain["titre"] if domain_match == "same" else (
        adj_domain["titre"] if adj_domain else "Professionnel expérimenté"
    )
    cv_text = (
        f"{cv_title}. "
        f"Compétences : {', '.join(cv_skills)}. "
        f"Expérience : {cv_exp} ans. Formation : {cv_edu} ans post-bac."
    )

    # ── Features calculables sans BGE-M3 ────────────────────────────────────
    req_norms = {_norm(s) for s in req_skills}
    cv_norms  = {_norm(s) for s in cv_skills}
    skills_raw = len(req_norms & cv_norms) / max(1, len(req_norms))

    edu_gap_norm = max(-1.0, min(1.0, (req_edu - cv_edu) / 5.0))

    exp_score = 1.0 if cv_exp >= req_exp else max(0.1, cv_exp / max(1, req_exp))

    # domain_compat_score : signal numérique de compatibilité domaine
    # Le MLP apprend directement depuis ce signal — pas de règle post-scoring.
    _DOMAIN_COMPAT = {"same": 1.0, "adjacent": 0.65, "different": 0.0}
    domain_compat_score = _DOMAIN_COMPAT[domain_match]

    # ── Label ground-truth ──────────────────────────────────────────────────
    label = _compute_label(
        domain_match=domain_match,
        skills_raw=skills_raw,
        edu_gap_norm=edu_gap_norm,
        exp_score=exp_score,
    )

    return {
        "offer_text": offer_text,
        "cv_text": cv_text,
        "skills_raw": round(skills_raw, 4),
        "edu_gap_norm": round(edu_gap_norm, 4),
        "exp_score": round(exp_score, 4),
        "domain_compat_score": round(domain_compat_score, 4),
        "label": round(label, 4),
        "domain_match": domain_match,
        "domain_name": domain["name"],
    }


def _norm(s: str) -> str:
    import unicodedata, re
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _compute_label(
    domain_match: str,
    skills_raw: float,
    edu_gap_norm: float,
    exp_score: float,
) -> float:
    """
    Label ground-truth — le MLP apprend ces patterns depuis les features.

    Logique :
    - same domain    : 0.40 à 0.85 selon compétences
    - adjacent domain: 0.25 à 0.55 MAIS pénalisé fort si grand écart formation
      (ex: infirmier Bac+3 → médecin Bac+8 : label ~0.10, pas 0.45)
    - different domain: 0.05 à 0.20
    """
    # Base selon domaine
    if domain_match == "same":
        base = 0.40 + skills_raw * 0.45   # 0.40 à 0.85

    elif domain_match == "adjacent":
        # Grand écart formation dans un domaine adjacent = rédhibitoire
        # ex: infirmier (Bac+3) → médecin (Bac+8) : edu_gap_norm = (8-3)/5 = 1.0
        if edu_gap_norm >= 0.8:
            # Quasi-incompatible malgré l'adjacence : traité comme "different"
            base = 0.05 + skills_raw * 0.12   # 0.05 à 0.17
        elif edu_gap_norm >= 0.5:
            # Écart significatif : plafonné bas
            base = 0.12 + skills_raw * 0.18   # 0.12 à 0.30
        else:
            # Adjacence réelle, formation compatible
            base = 0.25 + skills_raw * 0.30   # 0.25 à 0.55

    else:  # different
        base = 0.05 + skills_raw * 0.15   # 0.05 à 0.20

    # Modulation expérience (±30%)
    base *= (0.7 + 0.3 * exp_score)

    # Clip et léger bruit pour éviter l'overfitting
    base = max(0.04, min(0.95, base))
    base += random.gauss(0, 0.012)
    return max(0.04, min(0.95, base))


# ─────────────────────────────────────────────────────────────────────────────
# Génération du dataset
# ─────────────────────────────────────────────────────────────────────────────
def generate_dataset() -> List[Dict]:
    pairs = []

    for i, domain in enumerate(DOMAINS):
        req_edu = EDU_LEVELS.get(domain["edu_label"], domain["edu_min"])
        exp_min, exp_max = domain["exp_range"]

        # ── Paires SAME DOMAIN (bonne correspondance) ─────────────────────────
        for skill_rate in [0.95, 0.80, 0.65, 0.50, 0.35]:
            for edu_offset in [0, -1, -2]:
                for exp_mult in [1.0, 0.5, 2.0]:
                    cv_edu = max(1, req_edu + edu_offset)
                    cv_exp = max(0, int((exp_min + (exp_max - exp_min) * 0.5) * exp_mult))
                    pairs.append(_build_pair(
                        domain, skill_rate, cv_edu, cv_exp, "same"
                    ))

        # ── Paires ADJACENT DOMAIN ────────────────────────────────────────────
        # Prendre un domaine voisin dans la liste
        adj_idx = (i + 1) % len(DOMAINS)
        adj_domain = DOMAINS[adj_idx]
        for skill_rate in [0.40, 0.25, 0.10]:
            for edu_offset in [0, -1]:
                cv_edu = max(1, req_edu + edu_offset)
                cv_exp = max(0, exp_min)
                pairs.append(_build_pair(
                    domain, skill_rate, cv_edu, cv_exp,
                    "adjacent", adj_domain
                ))

        # ── Paires DIFFERENT DOMAIN ────────────────────────────────────────────
        diff_idx = (i + 7) % len(DOMAINS)
        diff_domain = DOMAINS[diff_idx]
        for _ in range(4):
            cv_edu = random.randint(1, 5)
            cv_exp = random.randint(0, 10)
            pairs.append(_build_pair(
                domain, 0.0, cv_edu, cv_exp,
                "different", diff_domain
            ))

    print(f"  Paires générées (sans features BGE) : {len(pairs)}")
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Calcul des features BGE-M3
# ─────────────────────────────────────────────────────────────────────────────
def compute_bge_features(pairs: List[Dict]) -> List[Dict]:
    """Approximation des features sem_bge/comp_bge depuis skills_raw (pas de chargement BGE-M3).
    Évite la contention mémoire avec le backend qui a déjà BGE-M3 chargé.
    Le signal domain_compat_score porte l'essentiel de l'information de domaine.
    """
    print("  Calcul features approchées (sem_bge ~ skills_raw, pas de BGE-M3)...")
    for p in pairs:
        sr = p["skills_raw"]
        p["sem_bge"]  = round(0.4 + sr * 0.5, 4)
        p["comp_bge"] = round(sr, 4)
        p["exp_bge"]  = round(p["exp_score"], 4)
        p["form_bge"] = round(max(0.1, 1.0 - max(0, p["edu_gap_norm"])), 4)
    print(f"  Features calculées pour {len(pairs)} paires.")
    return pairs

    BATCH = 64
    offer_texts = [p["offer_text"] for p in pairs]
    cv_texts    = [p["cv_text"]    for p in pairs]

    print(f"  Encoding {len(offer_texts)} offres...")
    offer_embs = model.encode(offer_texts, batch_size=BATCH, normalize_embeddings=True, show_progress_bar=True)
    print(f"  Encoding {len(cv_texts)} CVs...")
    cv_embs    = model.encode(cv_texts,    batch_size=BATCH, normalize_embeddings=True, show_progress_bar=True)

    # Skills encodés séparément
    offer_skills_texts = [
        ", ".join(DOMAINS[i % len(DOMAINS)]["skills"])
        for i in range(len(pairs))
    ]
    cv_skills_texts = [
        p["cv_text"].split("Compétences :")[1].split(".")[0].strip()
        if "Compétences :" in p["cv_text"] else p["cv_text"][:100]
        for p in pairs
    ]
    print("  Encoding skills...")
    offer_skills_embs = model.encode(offer_skills_texts, batch_size=BATCH, normalize_embeddings=True, show_progress_bar=False)
    cv_skills_embs    = model.encode(cv_skills_texts,    batch_size=BATCH, normalize_embeddings=True, show_progress_bar=False)

    for i, p in enumerate(pairs):
        sem   = float(np.dot(offer_embs[i], cv_embs[i]))
        comp  = float(np.dot(offer_skills_embs[i], cv_skills_embs[i]))
        p["sem_bge"]  = round(max(0.0, min(1.0, sem)), 4)
        p["comp_bge"] = round(max(0.0, min(1.0, comp)), 4)
        p["exp_bge"]  = round(p["exp_score"], 4)
        p["form_bge"] = round(max(0.1, 1.0 - max(0, p["edu_gap_norm"])), 4)
        # domain_compat_score déjà calculé dans _build_pair

    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(" Génération dataset universel FusionMLP")
    print(f" Domaines : {len(DOMAINS)}")
    print(f"{'='*60}\n")

    print("[1/3] Génération des paires...")
    pairs = generate_dataset()

    print("\n[2/3] Calcul features BGE-M3...")
    pairs = compute_bge_features(pairs)

    print(f"\n[3/3] Sauvegarde -> {OUT_FILE}")
    fieldnames = [
        "sem_bge", "comp_bge", "exp_bge", "form_bge",
        "skills_raw", "edu_gap_norm", "domain_compat_score",
        "label", "domain_name", "domain_match",
    ]
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in pairs:
            writer.writerow({k: p[k] for k in fieldnames})

    # Stats
    labels = [p["label"] for p in pairs]
    same_n = sum(1 for p in pairs if p["domain_match"] == "same")
    adj_n  = sum(1 for p in pairs if p["domain_match"] == "adjacent")
    diff_n = sum(1 for p in pairs if p["domain_match"] == "different")

    print(f"\n{'='*60}")
    print(f" Dataset sauvegardé : {OUT_FILE}")
    print(f" Total paires       : {len(pairs)}")
    print(f" Same domain        : {same_n}")
    print(f" Adjacent domain    : {adj_n}")
    print(f" Different domain   : {diff_n}")
    print(f" Label moyen        : {sum(labels)/len(labels):.3f}")
    print(f" Label min/max      : {min(labels):.3f} / {max(labels):.3f}")
    print(f"\n Prochaine étape : python -m scripts.train_mlp_universal")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
