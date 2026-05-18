from __future__ import annotations

import os

# Forcer le mode offline — modèle chargé depuis le cache local uniquement
os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",   "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rapidfuzz import fuzz  # type: ignore

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as _F
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

from app.models.candidate import Candidate
from app.models.job_offer import JobOffer
from app.services.matching.match_engine import (
    _candidate_education_level,
    _candidate_skills,
    _candidate_text_for_semantic,
    _candidate_years,
    _extract_offer_skills,
    _extract_required_education_level,
    _extract_required_years,
    _normalize_skill,
    _offer_text_for_semantic,
)



# Équivalences sémantiques bidirectionnelles par domaine métier.
# Si l'offre demande "iOS" et le candidat a "Swift" → match (et vice-versa).
# Couvre tous les domaines : IT, RH, Marketing, Finance, Droit, Santé, BTP...
_TECH_EXPANSION: Dict[str, frozenset] = {

    # ── JavaScript / Frontend ────────────────────────────────────────────────
    "javascript":  frozenset({"js", "es6", "es2015", "es2022", "ecmascript", "vanilla js", "vanillajs", "node", "nodejs", "node.js"}),
    "js":          frozenset({"javascript", "es6", "ecmascript", "typescript"}),
    "typescript":  frozenset({"ts", "javascript", "js", "angular", "react", "vue"}),
    "ts":          frozenset({"typescript", "javascript"}),
    "react":       frozenset({"reactjs", "react.js", "react js", "react 18", "react hooks", "redux", "next.js", "nextjs", "vite"}),
    "reactjs":     frozenset({"react", "react.js", "react js", "next.js", "nextjs", "redux"}),
    "next.js":     frozenset({"nextjs", "react", "reactjs", "ssr", "server side rendering"}),
    "nextjs":      frozenset({"next.js", "react", "reactjs", "ssr"}),
    "vue":         frozenset({"vuejs", "vue.js", "vue 3", "nuxt", "nuxt.js", "nuxtjs", "pinia", "vuex"}),
    "vuejs":       frozenset({"vue", "vue.js", "nuxt", "nuxt.js"}),
    "angular":     frozenset({"angularjs", "angular 2", "angular 14", "angular 16", "typescript", "rxjs", "ngrx"}),
    "angularjs":   frozenset({"angular", "javascript"}),
    "html":        frozenset({"html5", "html 5", "markup", "web", "frontend"}),
    "html5":       frozenset({"html", "web", "frontend", "css"}),
    "css":         frozenset({"css3", "sass", "scss", "less", "tailwind", "tailwindcss", "bootstrap", "styled components"}),
    "tailwind":    frozenset({"tailwindcss", "css", "css3", "utility-first css"}),
    "bootstrap":   frozenset({"css", "css3", "responsive design", "frontend"}),

    # ── Backend / Frameworks ─────────────────────────────────────────────────
    "node.js":     frozenset({"nodejs", "node", "javascript", "js", "express", "express.js", "nestjs", "fastify"}),
    "nodejs":      frozenset({"node.js", "node", "javascript", "express", "nestjs"}),
    "express":     frozenset({"express.js", "node.js", "nodejs", "javascript", "api rest"}),
    "django":      frozenset({"python", "drf", "django rest framework", "orm django"}),
    "flask":       frozenset({"python", "api rest", "microservices"}),
    "fastapi":     frozenset({"python", "api rest", "pydantic", "async python"}),
    "spring":      frozenset({"spring boot", "java", "spring framework", "hibernate", "maven"}),
    "spring boot": frozenset({"spring", "java", "api rest", "microservices", "maven", "gradle"}),
    "laravel":     frozenset({"php", "mvc", "eloquent", "api rest"}),
    "php":         frozenset({"laravel", "symfony", "wordpress", "php 8", "composer"}),
    "symfony":     frozenset({"php", "doctrine", "twig", "api platform"}),
    "rails":       frozenset({"ruby on rails", "ruby", "activerecord", "mvc"}),
    "ruby":        frozenset({"rails", "ruby on rails"}),
    ".net":        frozenset({"dotnet", "c#", "asp.net", "asp.net core", "blazor", "entity framework"}),
    "asp.net":     frozenset({".net", "c#", "dotnet", "asp.net core", "mvc .net"}),
    "c#":          frozenset({"csharp", ".net", "asp.net", "unity", "dotnet", "xamarin"}),
    "golang":      frozenset({"go", "go lang", "gin", "goroutine", "grpc go"}),
    "go":          frozenset({"golang", "go lang", "gin", "goroutine"}),
    "rust":        frozenset({"rust lang", "cargo", "tokio", "actix"}),

    # ── Bases de données ─────────────────────────────────────────────────────
    "mongodb":     frozenset({"mongo", "nosql", "document database", "mongoose", "atlas"}),
    "nosql":       frozenset({"mongodb", "cassandra", "couchdb", "dynamodb", "firebase"}),
    "redis":       frozenset({"cache", "in-memory", "redis cache", "pub/sub redis"}),
    "elasticsearch": frozenset({"elastic", "elk", "kibana", "logstash", "opensearch", "full text search"}),
    "oracle":      frozenset({"oracle db", "oracle sql", "pl/sql", "oracle database"}),
    "sqlite":      frozenset({"sql", "base de données légère", "embedded database"}),

    # ── APIs / Architecture ───────────────────────────────────────────────────
    "api rest":    frozenset({"restful", "rest api", "api restful", "http api", "openapi", "swagger", "json api"}),
    "restful":     frozenset({"api rest", "rest api", "http", "json", "openapi"}),
    "graphql":     frozenset({"graph ql", "apollo", "hasura", "relay", "api graphql"}),
    "microservices": frozenset({"micro services", "architecture microservices", "soa", "service mesh", "grpc"}),
    "grpc":        frozenset({"protocol buffers", "protobuf", "microservices", "rpc"}),
    "websocket":   frozenset({"ws", "socket.io", "temps réel", "realtime", "sse"}),

    # ── Versionnement / DevTools ──────────────────────────────────────────────
    "git":         frozenset({"github", "gitlab", "bitbucket", "git flow", "versionnement", "version control"}),
    "github":      frozenset({"git", "github actions", "pull request", "open source"}),
    "gitlab":      frozenset({"git", "gitlab ci", "devops", "merge request"}),
    "linux":       frozenset({"ubuntu", "debian", "centos", "rhel", "bash", "shell", "unix", "cli"}),
    "bash":        frozenset({"shell", "linux", "scripting", "zsh", "terminal"}),

    # ── Tests / Qualité ───────────────────────────────────────────────────────
    "tests unitaires": frozenset({"unit testing", "tdd", "jest", "pytest", "junit", "mocha", "jasmine", "karma", "vitest"}),
    "tdd":         frozenset({"test driven development", "tests unitaires", "bdd", "unit testing"}),
    "jest":        frozenset({"tests unitaires", "javascript testing", "react testing", "vitest"}),
    "pytest":      frozenset({"tests unitaires", "python testing", "unittest"}),
    "junit":       frozenset({"tests unitaires", "java testing", "mockito"}),
    "cypress":     frozenset({"e2e testing", "end to end", "playwright", "selenium", "tests fonctionnels"}),
    "selenium":    frozenset({"e2e testing", "tests automatisés", "webdriver", "cypress"}),

    # ── Langages supplémentaires ──────────────────────────────────────────────
    "java":        frozenset({"jvm", "spring", "spring boot", "hibernate", "maven", "gradle", "j2ee", "jakarta ee"}),
    "c++":         frozenset({"cpp", "c plus plus", "qt", "stl", "cmake", "embedded c++"}),
    "c":           frozenset({"langage c", "c programming", "embedded c", "microcontroleur"}),
    "scala":       frozenset({"scala lang", "akka", "spark scala", "play framework"}),
    "r":           frozenset({"r language", "rstudio", "tidyverse", "ggplot2", "statistiques r"}),
    "matlab":      frozenset({"matlab simulink", "simulink", "octave", "numerical computing"}),

    # ── IA / Data Science ────────────────────────────────────────────────────
    "tensorflow":  frozenset({"tf", "keras", "tensorflow 2", "deep learning", "neural network"}),
    "pytorch":     frozenset({"torch", "deep learning", "neural network", "huggingface", "transformers"}),
    "scikit-learn": frozenset({"sklearn", "scikit learn", "machine learning", "python ml"}),
    "pandas":      frozenset({"dataframe", "python data", "numpy", "data manipulation"}),
    "numpy":       frozenset({"numerical python", "array", "pandas", "scipy"}),
    "huggingface": frozenset({"transformers", "bert", "llm", "nlp", "pytorch"}),
    "langchain":   frozenset({"llm", "rag", "openai", "llm framework", "chatbot"}),
    "openai":      frozenset({"chatgpt", "gpt", "gpt-4", "llm", "api openai"}),

    # ── Écosystème iOS ───────────────────────────────────────────────────────
    "ios":         frozenset({"swift", "objective-c", "objc", "swiftui", "xcode", "uikit", "cocoa", "cocoapods"}),
    "swift":       frozenset({"ios", "swiftui", "xcode", "objective-c"}),
    "swiftui":     frozenset({"swift", "ios"}),
    "objective-c": frozenset({"ios", "swift", "xcode"}),
    "xcode":       frozenset({"swift", "ios", "objective-c"}),

    # ── Écosystème Android ───────────────────────────────────────────────────
    "android":     frozenset({"kotlin", "java", "android sdk", "android studio", "jetpack", "gradle"}),
    "kotlin":      frozenset({"android", "android sdk", "jetpack", "android studio"}),
    "android sdk": frozenset({"android", "kotlin", "java"}),

    # ── Cross-platform mobile ────────────────────────────────────────────────
    "react native": frozenset({"reactnative", "react native", "javascript", "typescript", "expo"}),
    "reactnative":  frozenset({"react native", "javascript", "typescript"}),
    "flutter":      frozenset({"dart"}),
    "dart":         frozenset({"flutter"}),

    # ── Cloud / DevOps ───────────────────────────────────────────────────────
    "aws":           frozenset({"amazon web services", "ec2", "s3", "eks", "lambda", "iam", "cloudformation", "rds"}),
    "amazon web services": frozenset({"aws", "ec2", "s3", "eks"}),
    "gcp":           frozenset({"google cloud", "bigquery", "cloud run", "gke", "google cloud platform"}),
    "google cloud":  frozenset({"gcp", "bigquery", "cloud run", "gke"}),
    "azure":         frozenset({"microsoft azure", "aks", "azure devops", "azure functions"}),
    "microsoft azure": frozenset({"azure", "aks", "azure devops"}),
    "kubernetes":    frozenset({"k8s", "kubectl", "helm", "eks", "aks", "gke", "openshift"}),
    "k8s":           frozenset({"kubernetes", "kubectl", "helm"}),
    "terraform":     frozenset({"opentofu", "infrastructure as code", "iac", "terraform cloud"}),
    "iac":           frozenset({"terraform", "infrastructure as code", "ansible", "pulumi"}),
    "docker":        frozenset({"conteneur", "container", "dockerfile", "docker compose", "docker-compose"}),
    "ci/cd":         frozenset({"gitlab ci", "github actions", "jenkins", "circleci", "travis", "pipeline"}),
    "gitlab ci":     frozenset({"ci/cd", "devops", "pipeline"}),
    "github actions": frozenset({"ci/cd", "devops", "pipeline"}),

    # ── Data / BI ────────────────────────────────────────────────────────────
    "python":        frozenset({"pandas", "numpy", "scikit-learn", "pytorch", "tensorflow", "flask", "fastapi", "django"}),
    "machine learning": frozenset({"ml", "scikit-learn", "tensorflow", "pytorch", "xgboost", "modèle prédictif", "predictive model"}),
    "ml":            frozenset({"machine learning", "deep learning", "ia", "intelligence artificielle"}),
    "deep learning": frozenset({"dl", "neural network", "cnn", "rnn", "transformer", "bert", "llm"}),
    "nlp":           frozenset({"natural language processing", "traitement du langage", "bert", "gpt", "llm", "spacy"}),
    "power bi":      frozenset({"powerbi", "bi", "business intelligence", "tableau", "qlik", "looker"}),
    "tableau":       frozenset({"power bi", "bi", "business intelligence", "data visualization", "looker"}),
    "sql":           frozenset({"postgresql", "mysql", "sqlite", "t-sql", "plsql", "pl/sql", "oracle sql", "requête sql"}),
    "postgresql":    frozenset({"sql", "postgres", "psql"}),
    "mysql":         frozenset({"sql", "mariadb"}),
    "spark":         frozenset({"apache spark", "pyspark", "databricks", "hdfs", "hadoop"}),
    "dbt":           frozenset({"data build tool", "elt", "data transformation", "datawarehouse"}),
    "data warehouse": frozenset({"dw", "datawarehouse", "snowflake", "bigquery", "redshift", "dbt"}),

    # ── RH / Human Resources ─────────────────────────────────────────────────
    "recrutement":   frozenset({"talent acquisition", "sourcing", "chasse de têtes", "headhunting", "hiring", "recruitment"}),
    "talent acquisition": frozenset({"recrutement", "sourcing", "recruitment", "hiring"}),
    "sirh":          frozenset({"sap hr", "workday", "successfactors", "peoplesoft", "hris", "oracle hcm"}),
    "hris":          frozenset({"sirh", "workday", "successfactors", "sap hr"}),
    "workday":       frozenset({"sirh", "hris", "paie", "payroll"}),
    "successfactors": frozenset({"sirh", "hris", "sap", "performance management"}),
    "gpec":          frozenset({"gestion des compétences", "gestion prévisionnelle", "skills management", "workforce planning"}),
    "droit social":  frozenset({"droit du travail", "relations sociales", "labor law", "droit de la convention collective"}),
    "paie":          frozenset({"payroll", "bulletins de salaire", "charges sociales", "silae", "sage paie"}),
    "onboarding":    frozenset({"intégration", "integration", "accueil salarié"}),

    # ── Marketing Digital ─────────────────────────────────────────────────────
    "seo":           frozenset({"référencement naturel", "référencement", "search engine optimization", "google search", "ahrefs", "semrush"}),
    "référencement": frozenset({"seo", "référencement naturel", "seo technique"}),
    "sem":           frozenset({"google ads", "adwords", "search engine marketing", "paid search", "ppc"}),
    "google ads":    frozenset({"sem", "adwords", "ppc", "paid search", "google adwords"}),
    "meta ads":      frozenset({"facebook ads", "instagram ads", "social ads", "paid social"}),
    "facebook ads":  frozenset({"meta ads", "paid social", "instagram ads"}),
    "hubspot":       frozenset({"crm", "marketing automation", "inbound marketing", "salesforce"}),
    "google analytics": frozenset({"ga4", "analytics", "web analytics", "gtm", "google tag manager"}),
    "ga4":           frozenset({"google analytics", "analytics", "web analytics"}),
    "content marketing": frozenset({"marketing de contenu", "copywriting", "rédaction web", "inbound"}),
    "community management": frozenset({"gestion réseaux sociaux", "social media", "animation réseaux", "social media management"}),
    "growth hacking": frozenset({"growth marketing", "acquisition", "conversion", "funnel", "a/b test"}),

    # ── Finance / Comptabilité ────────────────────────────────────────────────
    "ifrs":          frozenset({"normes comptables internationales", "ias", "normes ifrs", "international financial reporting standards"}),
    "normes comptables": frozenset({"ifrs", "pcg", "plan comptable général", "us gaap", "gaap"}),
    "sap fi":        frozenset({"sap", "sap finance", "fi/co", "sap co", "erp finance"}),
    "sap":           frozenset({"erp", "sap fi", "sap mm", "sap hr", "sap s/4hana"}),
    "erp":           frozenset({"sap", "oracle erp", "sage", "microsoft dynamics", "nav", "navision"}),
    "contrôle de gestion": frozenset({"controlling", "reporting financier", "financial controlling", "management control"}),
    "reporting financier": frozenset({"financial reporting", "contrôle de gestion", "tableau de bord", "kpi financiers"}),
    "trésorerie":    frozenset({"cash management", "gestion de trésorerie", "flux de trésorerie", "cash flow"}),
    "audit":         frozenset({"audit financier", "commissariat aux comptes", "internal audit", "contrôle interne"}),
    "dcf":           frozenset({"discounted cash flow", "valorisation", "valuation", "modélisation financière", "financial modeling"}),
    "m&a":           frozenset({"fusion acquisition", "mergers acquisitions", "due diligence", "lbo", "private equity"}),
    "bloomberg":     frozenset({"terminal bloomberg", "reuters", "marchés financiers", "financial markets"}),
    "comptabilité":  frozenset({"accounting", "bookkeeping", "bilan", "compte de résultat", "grand livre"}),

    # ── Vente / Sales ─────────────────────────────────────────────────────────
    "salesforce":    frozenset({"crm", "sfdc", "salesforce crm", "salesforce sales cloud"}),
    "crm":           frozenset({"salesforce", "hubspot", "dynamics crm", "zoho", "pipedrive"}),
    "prospection":   frozenset({"cold calling", "cold emailing", "outbound", "lead generation", "génération de leads"}),
    "négociation":   frozenset({"negotiation", "closing", "sales closing", "deal closing"}),
    "b2b":           frozenset({"business to business", "vente btob", "vente entreprise", "grands comptes"}),
    "grands comptes": frozenset({"key account", "kam", "key account management", "enterprise sales"}),
    "pipe":          frozenset({"pipeline commercial", "sales pipeline", "prévisions commerciales"}),

    # ── Droit / Legal ─────────────────────────────────────────────────────────
    "droit des affaires": frozenset({"business law", "droit commercial", "droit des contrats", "corporate law"}),
    "droit du travail": frozenset({"labor law", "employment law", "droit social", "relations sociales"}),
    "compliance":    frozenset({"conformité", "rgpd", "gdpr", "aml", "kyc", "conformité réglementaire"}),
    "rgpd":          frozenset({"gdpr", "protection des données", "data protection", "compliance"}),
    "contentieux":   frozenset({"litigation", "litige", "arbitrage", "médiation", "procédure judiciaire"}),
    "contrats":      frozenset({"contracts", "rédaction contrats", "contract drafting", "négociation contrats"}),
    "due diligence": frozenset({"audit juridique", "legal audit", "m&a juridique", "vdd"}),

    # ── Santé / Healthcare ────────────────────────────────────────────────────
    "médecine générale": frozenset({"médecin généraliste", "general practice", "gp", "médecine clinique", "médecine de famille", "généraliste"}),
    "diagnostic clinique": frozenset({"examen clinique", "clinical diagnosis", "sémiologie", "diagnostic médical", "diagnostic", "bilan clinique"}),
    "prescription médicale": frozenset({"ordonnance", "prescription", "prescriptions", "thérapeutique médicale", "ordonnances médicales"}),
    "urgences médicales": frozenset({"urgentiste", "médecine d'urgence", "samu", "smur", "emergency medicine", "urgences", "sau", "médecin urgentiste"}),
    "suivi patient": frozenset({"suivi médical", "patient care", "prise en charge", "consultation médicale", "suivi thérapeutique", "suivi clinique", "gestion patient"}),
    "dossier médical électronique": frozenset({"dme", "ehr", "his", "dossier patient", "dossier informatisé", "dpi", "electronic health record", "logiciel médical"}),
    "cardiologie basique": frozenset({"cardiologie", "notions de cardiologie", "ecg", "auscultation cardiaque", "cardiology"}),
    "éthique médicale": frozenset({"déontologie médicale", "déontologie", "code de déontologie", "éthique professionnelle", "medical ethics"}),
    "pharmacologie": frozenset({"médicaments", "pharmacothérapie", "thérapeutique", "pharmacocinétique", "pharmacodynamie", "traitements médicamenteux"}),
    "pédiatrie":     frozenset({"médecine pédiatrique", "médecine de l'enfant", "nourrisson", "pediatrics", "enfants", "médecine infantile"}),
    "ecg":           frozenset({"électrocardiogramme", "électrocardiographie", "tracé ecg", "electrocardiogram", "electrocardiography", "ecg interprétation"}),
    "vaccination":   frozenset({"vaccin", "vaccins", "immunisation", "programme vaccinal", "vaccinations", "immunization"}),
    "réanimation":   frozenset({"rea", "soins intensifs", "réanimation cardio-pulmonaire", "rcp", "bls", "acls", "icu", "intensive care", "soins critiques"}),
    "soins infirmiers": frozenset({"nursing", "soins", "patient care", "soins hospitaliers", "soins intensifs"}),
    "urgences":      frozenset({"emergency", "emergency care", "urgences hospitalières", "sau", "smur"}),
    "dossier patient": frozenset({"dpi", "electronic health record", "ehr", "dossier informatisé", "epic"}),
    "acls":          frozenset({"bls", "réanimation cardio-pulmonaire", "rcp", "advanced cardiac life support"}),
    "pharmacie":     frozenset({"médicament", "dispensation", "pharmacovigilance", "officine", "pharmaceutical"}),

    # ── Génie Civil / BTP ────────────────────────────────────────────────────
    "béton armé":    frozenset({"reinforced concrete", "calcul béton", "beton", "rc design", "eurocode"}),
    "autocad":       frozenset({"autocad civil 3d", "dao", "dessin assisté par ordinateur", "autocad architecture"}),
    "bim":           frozenset({"revit", "building information modeling", "bim revit", "autocad bim", "archicad"}),
    "revit":         frozenset({"bim", "bim revit", "autodesk revit"}),
    "travaux publics": frozenset({"tp", "génie civil", "civil engineering", "infrastructure", "voirie"}),
    "géotechnique":  frozenset({"sol", "fondations", "etude de sol", "sondage", "mécanique des sols"}),

    # ── Génie Mécanique ──────────────────────────────────────────────────────
    "solidworks":    frozenset({"cao", "catia", "conception assistée", "3d design", "autocad mechanical"}),
    "catia":         frozenset({"cao", "solidworks", "plm", "conception aéronautique"}),
    "cao":           frozenset({"solidworks", "catia", "conception assistée par ordinateur", "autocad", "inventor"}),
    "lean":          frozenset({"lean manufacturing", "six sigma", "lean six sigma", "kaizen", "amélioration continue"}),
    "six sigma":     frozenset({"lean", "lean six sigma", "dmaic", "qualité", "amélioration continue"}),
    "maintenance":   frozenset({"gmao", "maintenance préventive", "maintenance curative", "tpm", "fiabilité"}),
    "thermodynamique": frozenset({"mécanique des fluides", "transfert thermique", "energétique", "hvac"}),

    # ── Design UX ────────────────────────────────────────────────────────────
    "figma":         frozenset({"sketch", "adobe xd", "ux design", "prototypage", "design system"}),
    "ux design":     frozenset({"user experience", "expérience utilisateur", "ux", "figma", "user research"}),
    "ui design":     frozenset({"user interface", "interface utilisateur", "ui", "design graphique", "figma"}),
    "user research": frozenset({"recherche utilisateur", "ux research", "tests utilisateurs", "usability testing"}),
    "design system": frozenset({"storybook", "composants ui", "ui kit", "design tokens"}),
    "accessibilité": frozenset({"wcag", "aria", "a11y", "accessibilité web", "accessibility"}),

    # ── Supply Chain / Logistique ─────────────────────────────────────────────
    "sap mm":        frozenset({"sap", "achats", "gestion stocks", "mm module", "procurement sap"}),
    "achats":        frozenset({"procurement", "sourcing", "achats stratégiques", "purchasing", "appels d'offres"}),
    "s&op":          frozenset({"sales and operations planning", "planification", "demand planning", "supply planning"}),
    "logistique":    frozenset({"supply chain", "entrepôt", "wms", "transport", "approvisionnement"}),
    "wms":           frozenset({"warehouse management system", "entrepôt", "logistique", "gestion entrepôt"}),
    "lean manufacturing": frozenset({"lean", "kaizen", "5s", "kanban", "just in time", "jit"}),

    # ── Gestion de Projet ─────────────────────────────────────────────────────
    "scrum":         frozenset({"agile", "sprint", "kanban", "scrum master", "méthode agile"}),
    "agile":         frozenset({"scrum", "kanban", "safe", "lean agile", "méthode agile", "itération"}),
    "pmp":           frozenset({"prince2", "gestion de projet", "project management", "certification projet"}),
    "jira":          frozenset({"confluence", "atlassian", "gestion tickets", "project tracking", "trello"}),
    "ms project":    frozenset({"microsoft project", "gantt", "planification projet", "planning"}),
    "parties prenantes": frozenset({"stakeholders", "gestion parties prenantes", "stakeholder management"}),
}


import re as _re

# ─────────────────────────────────────────────────────────────────────────────
# ONTOLOGIE MÉTIER — Tous domaines professionnels (inspirée ESCO)
# (pattern regex, domaine, niveau_rôle 1-5, compétences_implicites)
# niveau : 1=stagiaire  2=junior  3=intermédiaire  4=senior  5=expert/directeur
# ─────────────────────────────────────────────────────────────────────────────
_PROFESSION_ONTOLOGY: List[Tuple[str, str, int, List[str]]] = [

    # ── SANTÉ ─────────────────────────────────────────────────────────────────
    (r"médecin\s+généraliste|médecin\s+général|general\s+practitioner|généraliste\s+médical", "sante", 5,
     ["médecine générale", "diagnostic clinique", "prescription médicale", "suivi patient",
      "dossier médical électronique", "éthique médicale", "pharmacologie",
      "pédiatrie", "cardiologie basique", "vaccination"]),
    (r"urgentiste|médecin.+urgences?|médecin.+urgentiste|emergency\s+physician", "sante", 5,
     ["urgences médicales", "diagnostic clinique", "prescription médicale",
      "ecg", "réanimation", "suivi patient", "éthique médicale"]),
    (r"\bcardiologue\b", "sante", 5,
     ["cardiologie basique", "ecg", "diagnostic clinique", "prescription médicale",
      "suivi patient", "éthique médicale"]),
    (r"\bpédiatre\b|pediatrician", "sante", 5,
     ["pédiatrie", "diagnostic clinique", "prescription médicale", "vaccination",
      "suivi patient", "éthique médicale"]),
    (r"\bpsychiatre\b|neuropsychiatre", "sante", 5,
     ["psychiatrie", "diagnostic clinique", "prescription médicale",
      "suivi patient", "éthique médicale"]),
    (r"\bchirurgien\b", "sante", 5,
     ["chirurgie", "diagnostic clinique", "prescription médicale",
      "bloc opératoire", "éthique médicale"]),
    (r"\bgynécologue\b|obstétricien", "sante", 5,
     ["gynécologie", "diagnostic clinique", "prescription médicale",
      "suivi patient", "éthique médicale"]),
    (r"\bradiologue\b", "sante", 5,
     ["radiologie", "imagerie médicale", "diagnostic clinique", "éthique médicale"]),
    (r"anesthésiste|anesthésiologiste", "sante", 5,
     ["anesthésie", "réanimation", "pharmacologie", "éthique médicale"]),
    (r"\bmédecin\b|physician\b", "sante", 5,
     ["diagnostic clinique", "prescription médicale", "suivi patient",
      "éthique médicale", "dossier médical électronique"]),
    (r"infirmier|infirmière|\bnurse\b", "sante_paramedical", 3,
     ["soins infirmiers", "suivi patient", "dossier médical électronique",
      "vaccination", "prise en charge"]),
    (r"\bpharmacien(?:ne)?\b|pharmacist", "sante_pharma", 4,
     ["pharmacologie", "médicaments", "dispensation", "conseil patient", "ordonnances"]),
    (r"kinésithérapeute|physiothérapeute|\bkiné\b", "sante_paramedical", 4,
     ["kinésithérapie", "rééducation", "suivi patient"]),
    (r"sage.femme|midwife", "sante_paramedical", 4,
     ["gynécologie", "suivi patient", "vaccination"]),
    (r"chirurgien.dentiste|\bdentiste\b|dentist", "sante", 5,
     ["soins dentaires", "diagnostic", "chirurgie dentaire", "éthique médicale"]),
    (r"aide.soignant|auxiliaire.de.vie", "sante_paramedical", 2,
     ["soins de base", "suivi patient"]),
    (r"ingénieur\s+biomédical|technicien\s+biomédical|biomedical\s+engineer", "ingenierie", 3,
     ["dispositifs médicaux", "maintenance biomédicale", "matériel médical"]),

    # ── DROIT / JURIDIQUE ─────────────────────────────────────────────────────
    (r"avocat.+affaires|corporate\s+lawyer", "droit", 5,
     ["droit des sociétés", "droit commercial", "rédaction juridique",
      "négociation", "conseil juridique", "contentieux", "veille juridique"]),
    (r"\bavocat(?:e)?\b|attorney\b|barrister\b|\blawyer\b", "droit", 5,
     ["droit civil", "droit commercial", "rédaction juridique", "plaidoirie",
      "conseil juridique", "contentieux", "négociation", "jurisprudence", "veille juridique"]),
    (r"juriste.d.entreprise|in.house\s+counsel", "droit", 4,
     ["droit des contrats", "droit commercial", "compliance",
      "rédaction juridique", "conseil juridique", "veille juridique"]),
    (r"\bjuriste\b|legal\s+counsel|conseiller\s+juridique", "droit", 4,
     ["droit des contrats", "rédaction juridique", "veille juridique",
      "conseil juridique", "droit commercial"]),
    (r"\bnotaire\b|notary\b", "droit", 5,
     ["actes notariés", "droit immobilier", "droit de la famille", "rédaction juridique"]),
    (r"\bhuissier\b", "droit", 4,
     ["signification actes", "saisies", "constats", "droit processuel"]),
    (r"\bmagistrat\b|\bprocureur\b|\bjuge\b", "droit", 5,
     ["droit pénal", "procédure pénale", "jurisprudence", "droit civil"]),
    (r"compliance.officer|responsable.conformité", "droit", 4,
     ["compliance", "réglementation", "audit", "risk management", "veille juridique"]),
    (r"paralegal|assistant\s+juridique|clerc\s+(?:de\s+)?notaire", "droit", 2,
     ["recherche juridique", "rédaction courriers", "veille juridique"]),
    (r"stagiaire.+(?:juridique|avocat|droit)|étudiant.+droit", "droit", 1,
     ["recherche juridique", "veille juridique"]),

    # ── INFORMATIQUE / IT ─────────────────────────────────────────────────────
    (r"développeur?.+(?:full.stack|fullstack)", "it", 4,
     ["javascript", "html", "css", "api rest", "base de données", "git"]),
    (r"développeur?.+(?:frontend|front.end)", "it", 3,
     ["javascript", "html", "css", "react", "responsive design", "git"]),
    (r"développeur?.+(?:backend|back.end)", "it", 3,
     ["api rest", "base de données", "sql", "git", "architecture"]),
    (r"développeur?.+python|python\s+developer", "it", 3,
     ["python", "api rest", "sql", "git", "algorithmes"]),
    (r"développeur?.+java\b|java\s+developer", "it", 3,
     ["java", "spring", "sql", "git", "api rest"]),
    (r"data\s+scientist|scientist\s+data", "it", 4,
     ["python", "machine learning", "statistiques", "pandas", "scikit-learn", "sql"]),
    (r"data\s+engineer|ingénieur?.+données", "it", 4,
     ["python", "sql", "etl", "spark", "pipeline données", "base de données"]),
    (r"data\s+analyst|analyste.+(?:données|data)", "it", 3,
     ["sql", "excel", "power bi", "statistiques", "visualisation données"]),
    (r"devops\s+engineer|ingénieur?.+devops", "it", 4,
     ["docker", "kubernetes", "ci/cd", "linux", "terraform", "aws"]),
    (r"architecte.+(?:logiciel|solution|cloud|système|si)\b", "it", 5,
     ["architecture logicielle", "design patterns", "microservices", "cloud", "api rest", "sécurité"]),
    (r"(?:responsable|chef\s+de)\s+projet\s+(?:informatique|it|digital|si)", "it", 4,
     ["gestion de projet", "agile", "scrum", "planification", "pilotage"]),
    (r"administrateur?\s+système|sysadmin|system\s+administrator", "it", 3,
     ["linux", "windows server", "virtualisation", "backup", "monitoring"]),
    (r"ingénieur?.+(?:cybersécurité|sécurité\s+informatique)", "it", 4,
     ["cybersécurité", "pentesting", "firewall", "iso 27001"]),
    (r"ingénieur?.+(?:full.?stack|fullstack|frontend|front.end|backend|back.end)", "it", 3,
     ["développement logiciel", "javascript", "api rest", "git"]),
    (r"ingénieur?.+(?:cloud|sre|site.reliability|plateforme)", "it", 4,
     ["docker", "kubernetes", "ci/cd", "linux", "aws"]),
    (r"ingénieur?.+(?:données|data\s+science|data\s+engineer|intelligence\s+artificielle|machine\s+learning|ia\b|ai\b|nlp)", "it", 4,
     ["python", "sql", "machine learning", "pandas"]),
    (r"ingénieur?.+(?:informatique|numérique|digital|web|mobile|applications?)\b", "it", 3,
     ["développement logiciel", "git", "algorithmes"]),
    (r"engineer\s+(?:full.?stack|frontend|backend|cloud|software|data|ai|ml|web)", "it", 3,
     ["développement logiciel", "git", "algorithmes"]),
    (r"développeur?.+(?:junior|débutant)|junior\s+developer", "it", 2,
     ["développement logiciel", "git", "html", "javascript"]),
    (r"développeur?|developer\b|software\s+engineer|ingénieur?.+logiciel", "it", 3,
     ["développement logiciel", "git", "algorithmes", "tests"]),

    # ── FINANCE / COMPTABILITÉ ────────────────────────────────────────────────
    (r"expert.comptable|chartered\s+accountant|\bcpa\b", "finance", 5,
     ["audit", "normes ifrs", "consolidation", "fiscalité",
      "comptabilité générale", "bilan", "liasse fiscale"]),
    (r"commissaire\s+aux\s+comptes|\bcac\b|statutory\s+auditor", "finance", 5,
     ["audit légal", "commissariat aux comptes", "normes ifrs", "comptabilité générale"]),
    (r"directeur\s+financier|\bdaf\b|\bcfo\b|chief\s+financial", "finance", 5,
     ["stratégie financière", "trésorerie", "audit", "budget", "normes ifrs", "reporting financier"]),
    (r"contrôleur\s+de\s+gestion|controller\b", "finance", 4,
     ["contrôle de gestion", "reporting financier", "budget", "analyse financière", "excel"]),
    (r"analyste\s+financier|financial\s+analyst", "finance", 4,
     ["analyse financière", "modélisation financière", "excel", "reporting financier"]),
    (r"auditeur?.+(?:interne|externe|financier)|auditor\b", "finance", 4,
     ["audit", "contrôle interne", "normes ifrs", "risques", "compliance"]),
    (r"responsable\s+(?:comptable|finance)|chef\s+comptable", "finance", 4,
     ["comptabilité générale", "bilan", "tva", "fiscalité", "clôture comptable"]),
    (r"\bcomptable\b|accountant\b", "finance", 3,
     ["comptabilité générale", "bilan", "tva", "saisie comptable", "rapprochement bancaire", "excel"]),
    (r"gestionnaire.+(?:paie|salaires)|payroll\s+specialist", "finance", 3,
     ["paie", "charges sociales", "bulletins de salaire", "droit social"]),

    # ── RESSOURCES HUMAINES ───────────────────────────────────────────────────
    (r"directeur?.+(?:ressources\s+humaines|rh)|\bdrh\b|chief\s+people", "rh", 5,
     ["stratégie rh", "management", "relations sociales", "droit du travail", "recrutement", "gpec"]),
    (r"responsable.+(?:ressources\s+humaines|rh)|\brrh\b|hr\s+manager", "rh", 4,
     ["recrutement", "gestion administrative rh", "droit du travail", "relations sociales", "formation"]),
    (r"chargé\s+de\s+recrutement|talent\s+acquisition|\brecruiter\b", "rh", 3,
     ["recrutement", "sourcing", "entretiens", "onboarding"]),
    (r"\bhrbp\b|hr\s+business\s+partner|partenaire\s+rh", "rh", 4,
     ["conseil rh", "gestion des talents", "relations sociales", "droit du travail"]),
    (r"gestionnaire\s+rh|assistant?\s+rh|hr\s+assistant", "rh", 2,
     ["gestion administrative rh", "contrats", "congés", "sirh"]),

    # ── MARKETING / COMMUNICATION ─────────────────────────────────────────────
    (r"directeur?.+marketing|\bcmo\b|chief\s+marketing", "marketing", 5,
     ["stratégie marketing", "budget", "management", "brand management", "communication"]),
    (r"responsable\s+marketing|marketing\s+manager", "marketing", 4,
     ["stratégie marketing", "communication", "budget", "campagnes marketing"]),
    (r"traffic\s+manager|responsable\s+sea|paid\s+media", "marketing", 3,
     ["google ads", "sem", "seo", "google analytics", "a/b testing"]),
    (r"community\s+manager|responsable\s+réseaux\s+sociaux", "marketing", 3,
     ["réseaux sociaux", "content marketing", "rédaction"]),
    (r"growth\s+hacker|growth\s+marketer", "marketing", 3,
     ["growth hacking", "a/b testing", "acquisition", "google analytics", "seo"]),

    # ── INGÉNIERIE / BTP ──────────────────────────────────────────────────────
    (r"ingénieur?.+(?:génie\s+civil|structure|béton)", "ingenierie", 4,
     ["génie civil", "calcul de structure", "béton armé", "autocad", "planification"]),
    (r"ingénieur?.+(?:électrique|électronique|electrical)", "ingenierie", 4,
     ["électricité", "circuits électriques", "autocad", "schémas électriques"]),
    (r"ingénieur?.+(?:mécanique|mechanical)", "ingenierie", 4,
     ["mécanique", "catia", "solidworks", "calcul mécanique"]),
    (r"conducteur\s+de\s+travaux|chef\s+de\s+chantier", "ingenierie", 4,
     ["gestion de chantier", "planification", "gestion équipe", "sécurité chantier"]),
    (r"\barchitecte\b(?!\s+(?:logiciel|solution|cloud|si))", "ingenierie", 5,
     ["architecture", "autocad", "revit", "permis de construire"]),
    (r"ingénieur?.+qualité|quality\s+engineer", "ingenierie", 4,
     ["iso 9001", "contrôle qualité", "audit qualité", "amélioration continue"]),
    (r"\bingénieur?\b|\bengineer\b", "ingenierie", 3,
     ["analyse technique", "résolution de problèmes", "rédaction technique"]),

    # ── ÉDUCATION / RECHERCHE ─────────────────────────────────────────────────
    (r"professeur?|enseignant?|\bteacher\b", "education", 4,
     ["pédagogie", "animation de cours", "évaluation", "conception pédagogique"]),
    (r"\bformateur?\b|\btrainer\b", "education", 3,
     ["animation de formation", "pédagogie", "conception de supports"]),
    (r"chercheur?|researcher\b|chargé\s+de\s+recherche", "education", 5,
     ["recherche", "rédaction scientifique", "analyse de données", "publications"]),

    # ── COMMERCE / VENTE ──────────────────────────────────────────────────────
    (r"directeur?.+(?:commercial|ventes)|sales\s+director", "commerce", 5,
     ["stratégie commerciale", "management", "négociation", "budget ventes", "crm"]),
    (r"responsable.+(?:commercial|ventes)|sales\s+manager", "commerce", 4,
     ["développement commercial", "négociation", "gestion équipe", "crm"]),
    (r"\bcommercial?\b|sales\s+representative|attaché\s+commercial", "commerce", 3,
     ["prospection", "négociation", "crm", "développement commercial"]),
]


# ─────────────────────────────────────────────────────────────────────────────
# PRESTIGE DES INSTITUTIONS DE FORMATION
# 0.55 (faible) → 1.0 (excellence mondiale)  |  0.75 = neutre (inconnu)
# ─────────────────────────────────────────────────────────────────────────────
_INSTITUTION_PRESTIGE: Dict[str, float] = {
    # Grandes Écoles France
    "polytechnique": 1.0, "ecole polytechnique": 1.0,
    "hec paris": 1.0, "insead": 1.0,
    "centralensupelec": 0.98, "centrale paris": 0.98, "supelec": 0.97,
    "centrale lyon": 0.97, "mines paristech": 0.97, "ponts et chaussées": 0.97,
    "telecom paris": 0.96, "ensam": 0.95,
    "essec": 0.97, "edhec": 0.95, "escp": 0.95, "em lyon": 0.94,
    "sciences po paris": 0.97, "sciences po": 0.92,
    # Universités France
    "paris saclay": 0.90, "sorbonne": 0.87, "paris tech": 0.88,
    "grenoble inp": 0.85, "insa lyon": 0.85, "insa toulouse": 0.84,
    "université de paris": 0.80, "université paris": 0.80,
    "université lyon": 0.78, "université bordeaux": 0.78,
    "université toulouse": 0.78, "université strasbourg": 0.78,
    # Grandes Écoles / Universités Tunisie
    "esprit": 0.85, "insat": 0.85, "supcom": 0.85,
    "enim": 0.82, "enat": 0.82, "enig": 0.80, "ept": 0.84,
    "ihec": 0.80, "iscae": 0.78,
    "faculté de médecine": 0.78, "faculté de droit": 0.74,
    "faculté de pharmacie": 0.76,
    "fst": 0.72, "fsm": 0.72, "iset": 0.62,
    "université de tunis": 0.70, "université carthage": 0.72,
    "université sfax": 0.68, "université sousse": 0.68,
    "université monastir": 0.68, "université manouba": 0.68,
    # Internationales
    "mit": 1.0, "stanford": 1.0, "harvard": 1.0,
    "oxford": 1.0, "cambridge": 1.0,
    "imperial college": 0.98, "eth zurich": 0.98, "epfl": 0.98,
    "université de montréal": 0.84, "hec montréal": 0.88,
    "mcgill": 0.90,
}

# Domaines considérés comme "adjacents" (pénalité réduite de mismatch)
_ADJACENT_DOMAINS: frozenset = frozenset({
    ("sante", "sante_paramedical"), ("sante_paramedical", "sante"),
    ("sante", "sante_pharma"), ("sante_pharma", "sante"),
    ("sante_paramedical", "sante_pharma"), ("sante_pharma", "sante_paramedical"),
    ("droit", "rh"), ("rh", "droit"),
    ("finance", "commerce"), ("commerce", "finance"),
    ("finance", "rh"), ("rh", "finance"),
    ("it", "ingenierie"), ("ingenierie", "it"),
})


def _detect_profession_from_cv(
    raw_lower: str, parsed_data: Dict[str, Any]
) -> Tuple[Optional[str], int, List[str]]:
    """
    Détecte le domaine professionnel et les compétences implicites du candidat.
    Retourne (domaine, niveau_rôle 1-5, compétences_implicites).
    """
    candidate_texts: List[str] = []
    meta = parsed_data.get("metadata") or {}
    for key in ("titre_professionnel", "titre", "poste", "current_title", "intitule"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            candidate_texts.append(val.lower().strip())
    for exp in (parsed_data.get("experiences") or [])[:3]:
        if not isinstance(exp, dict):
            continue
        for key in ("poste", "title", "intitule", "fonction", "position"):
            val = exp.get(key)
            if isinstance(val, str) and val.strip():
                candidate_texts.append(val.lower().strip())
    candidate_texts.append(raw_lower[:500])
    for text in candidate_texts:
        for (pattern, domain, level, skills) in _PROFESSION_ONTOLOGY:
            if _re.search(pattern, text, _re.IGNORECASE):
                return domain, level, skills
    return None, 0, []


def _detect_offer_domain(offer: Any) -> Tuple[Optional[str], int]:
    """Détecte le domaine et niveau de rôle attendu dans l'offre."""
    offer_text = (
        (offer.titre or "") + " " + ((offer.description or "")[:400])
    ).lower()
    for (pattern, domain, level, _skills) in _PROFESSION_ONTOLOGY:
        if _re.search(pattern, offer_text, _re.IGNORECASE):
            return domain, level
    return None, 0


def _institution_prestige_score(parsed_data: Dict[str, Any]) -> float:
    """
    Score le prestige de l'institution de formation du candidat (0.55–1.0).
    Retourne 0.75 (neutre) si institution inconnue.
    """
    formations = parsed_data.get("formations") or parsed_data.get("education") or []
    if not isinstance(formations, list) or not formations:
        return 0.75
    best = 0.0
    for form in formations:
        if not isinstance(form, dict):
            continue
        ecole = (
            form.get("etablissement") or form.get("ecole") or
            form.get("school") or form.get("institution") or ""
        ).lower().strip()
        if not ecole:
            continue
        for name, prestige in _INSTITUTION_PRESTIGE.items():
            if name in ecole or ecole in name:
                best = max(best, prestige)
    return best if best > 0.0 else 0.75


def _detect_seniority_level(text: str) -> int:
    """
    Détecte le niveau de séniorité dans un texte (titre ou description).
    Retourne : 5=directeur/expert  4=senior  3=confirmé  2=junior  1=stagiaire  0=non détecté
    """
    t = text.lower()
    if any(w in t for w in ["directeur", "director", "vp ", "chief", "cto", "ceo", "daf", "drh", "head of"]):
        return 5
    if any(w in t for w in ["senior", "sr.", "sr ", "lead ", "principal", "expert", "confirmé", "expérimenté", "staff engineer"]):
        return 4
    if any(w in t for w in ["mid-level", "intermédiaire", "mid level", "confirmed", "autonome"]):
        return 3
    if any(w in t for w in ["junior", "jr.", "jr ", "débutant", "entry level", "entry-level", "graduate", "fresh"]):
        return 2
    if any(w in t for w in ["stagiaire", "stage", "pfe", "alternant", "alternance", "apprenti", "intern"]):
        return 1
    return 0


def _clip_words(text: str, max_tokens: int = 512) -> str:
    words = (text or "").split()
    if len(words) <= max_tokens:
        return " ".join(words)
    return " ".join(words[:max_tokens])


def _safe_list_of_strings(values: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(values, list):
        return out
    for v in values:
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
        elif isinstance(v, dict):
            name = v.get("name") or v.get("skill") or v.get("valeur")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
    return out


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = float(np.linalg.norm(a))
    b_norm = float(np.linalg.norm(b))
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


_MODELS_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "data", "models"
)
# MLP head weights are decoupled from the transformer — loaded independently.
_MLP_WEIGHTS_PATH = os.path.join(
    _MODELS_ROOT, "talentmatch-bert-v2.0", "scoring_mlp.pt"
)
# BGE-M3 — SOTA multilingual sentence embedder (~568M params, 1024-dim,
# normalized outputs, no prefix required).
_EMBEDDER_MODEL = "BAAI/bge-m3"
# Cross-encoder reranker — canonical pair with BGE-M3. Used to score the
# full (offer, CV) pair jointly for the s_semantique MLP feature.
_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
# BGE-M3 hidden size — used by _encode's zero-fallback when the model isn't loaded.
_EMBEDDER_DIM = 1024


class _ScoringMLP(nn.Module if _TORCH_AVAILABLE else object):
    """MLP 5 dimensions -> score 0-100% appris."""
    def __init__(self):
        if _TORCH_AVAILABLE:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(5, 128), nn.ReLU(), nn.Dropout(0.15),
                nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.10),
                nn.Linear(64, 32),  nn.ReLU(),
                nn.Linear(32, 1),   nn.Sigmoid(),
            )

    def forward(self, x):
        return self.net(x).squeeze(-1) * 100


class BERTMatchingScorer:
    def __init__(self, model_name: str = _EMBEDDER_MODEL):
        self._st_model   = None    # SentenceTransformer (bi-encoder)
        self._reranker   = None    # CrossEncoder (joint scorer)
        self._mlp        = None    # ScoringMLP 5D
        self._load_attempted = False
        self._reranker_load_attempted = False
        self.ready       = False
        self.reranker_ready = False
        self.load_error: Optional[str] = None
        self.reranker_load_error: Optional[str] = None
        self.model_name  = model_name
        self.model_version = model_name
        self.reranker_model_name = _RERANKER_MODEL

    def _ensure_loaded(self) -> bool:
        if self.ready or self._load_attempted:
            return self.ready
        self._load_attempted = True

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._st_model = SentenceTransformer(_EMBEDDER_MODEL)
            self.model_name    = _EMBEDDER_MODEL
            self.model_version = _EMBEDDER_MODEL
            self.ready = True
            # Charger le MLP si disponible (poids indépendants du transformer)
            self._load_mlp(_MLP_WEIGHTS_PATH)
            return True
        except Exception as e:
            self._st_model = None
            self.ready = False
            self.load_error = f"embedder_load_failed:{type(e).__name__}:{e}"
            return False

    def _ensure_reranker_loaded(self) -> bool:
        """Lazy-load the cross-encoder reranker. Independent of the embedder."""
        if self.reranker_ready or self._reranker_load_attempted:
            return self.reranker_ready
        self._reranker_load_attempted = True

        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            # max_length=512 matches bge-reranker-v2-m3's default; truncation handles longer.
            self._reranker = CrossEncoder(_RERANKER_MODEL, max_length=512)
            self.reranker_ready = True
            return True
        except Exception as e:
            self._reranker = None
            self.reranker_ready = False
            self.reranker_load_error = f"reranker_load_failed:{type(e).__name__}:{e}"
            return False

    def _load_mlp(self, mlp_path: str) -> None:
        """Load the 5-feature scoring MLP from a direct .pt path. Fail-soft."""
        if not _TORCH_AVAILABLE:
            return
        if not os.path.exists(mlp_path):
            return
        try:
            mlp = _ScoringMLP()
            mlp.load_state_dict(torch.load(mlp_path, map_location="cpu", weights_only=True))
            mlp.eval()
            self._mlp = mlp
        except Exception:
            self._mlp = None

    def _encode(self, texts: List[str]) -> np.ndarray:
        """Encode des textes en vecteurs normalisés via SentenceTransformer."""
        if self._st_model is None:
            return np.zeros((len(texts), _EMBEDDER_DIM))
        return self._st_model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True
        )

    def _mlp_score(
        self,
        sem_sim: float,
        skill_rate: float,
        exp_score: float,
        formation_score: float,
        appreciated_rate: float,
    ) -> Optional[float]:
        """Retourne le score MLP 0-1 ou None si MLP indisponible."""
        if self._mlp is None or not _TORCH_AVAILABLE:
            return None
        x = torch.tensor(
            [[sem_sim, skill_rate, exp_score, formation_score, appreciated_rate]],
            dtype=torch.float32,
        )
        with torch.no_grad():
            return float(self._mlp(x)) / 100.0

    def _get_model(self):
        """Compatibilité — retourne le SentenceTransformer chargé (ou None)."""
        self._ensure_loaded()
        return self._st_model

    def score_semantic(self, offer_text: str, cv_text: str) -> Tuple[float, Dict[str, Any]]:
        if not self._ensure_loaded():
            return 0.5, {"ready": False, "reason": self.load_error or "model_unavailable"}

        try:
            offer_input = _clip_words(offer_text, 128)
            cv_input    = _clip_words(cv_text,    128)
            emb = self._encode([offer_input, cv_input])
            sim = float(np.dot(emb[0], emb[1]))
            sim = max(0.0, min(1.0, sim))
            return float(sim), {
                "ready": True,
                "model": self.model_version,
                "method": "direct_cosine",
                "raw_similarity": round(sim, 4),
            }
        except Exception as e:
            return 0.5, {"ready": False, "reason": f"semantic_error:{type(e).__name__}"}

    def score_skills_bert(
        self,
        offer_skills: List[str],
        cv_skills: List[str],
    ) -> Tuple[float, Dict[str, Any]]:
        if not offer_skills or not cv_skills:
            return 0.5, {"note": "no_skills", "ready": self.ready, "model": self.model_name}

        if not self._ensure_loaded():
            return 0.5, {"ready": False, "reason": self.load_error or "model_unavailable"}

        try:
            offer_emb = self._encode([_normalize_skill(s) for s in offer_skills])
            cv_emb    = self._encode([_normalize_skill(s) for s in cv_skills])

            # Seuil 0.78 — calibré pour BGE-M3 dont les cosines sur vrais matches
            # sont typiquement 0.78–0.92, vs 0.55–0.75 pour MiniLM.
            # Bloque toujours Java≈Python et Jenkins≈TensorFlow (~0.60).
            THRESHOLD = 0.78

            per_skill: List[Dict[str, Any]] = []
            max_scores: List[float] = []
            for i, req in enumerate(offer_skills):
                best_sim, best_cv_skill = 0.0, None
                for j, cv_s in enumerate(cv_skills):
                    sim = float(np.dot(offer_emb[i], cv_emb[j]))
                    sim = max(0.0, min(1.0, sim))
                    if sim > best_sim:
                        best_sim = sim
                        best_cv_skill = cv_s

                # Rescaling : [THRESHOLD, 1] → [0, 1]  (en-dessous = 0)
                if best_sim >= THRESHOLD:
                    calibrated = (best_sim - THRESHOLD) / (1.0 - THRESHOLD)
                else:
                    calibrated = 0.0

                per_skill.append({
                    "required": req,
                    "best_match": best_cv_skill if best_sim >= THRESHOLD else None,
                    "raw_similarity": round(best_sim, 4),
                    "calibrated": round(calibrated, 4),
                    "matched": best_sim >= THRESHOLD,
                })
                max_scores.append(calibrated)

            score = float(np.mean(max_scores)) if max_scores else 0.5
            score = max(0.0, min(1.0, score))
            return score, {
                "ready": True,
                "model": self.model_name,
                "method": "contextual_bert",
                "offer_skills_count": len(offer_skills),
                "cv_skills_count": len(cv_skills),
                "per_skill": per_skill,
                "threshold": THRESHOLD,
                "matched_count": sum(1 for p in per_skill if p["matched"]),
            }
        except Exception as e:
            return 0.5, {
                "ready": False,
                "reason": f"skills_error:{type(e).__name__}",
                "model": self.model_name,
            }

    def detect_skill_inconsistencies(
        self,
        cv_skills: List[str],
        cv_experiences: Any,
        cv_raw_text: str,
    ) -> List[Dict[str, Any]]:
        ecosystems = {
            "react": "javascript",
            "angular": "typescript",
            "spring": "java",
            "django": "python",
            "laravel": "php",
        }

        raw_low = (cv_raw_text or "").lower()
        experiences_texts: List[str] = []
        if isinstance(cv_experiences, list):
            for exp in cv_experiences:
                if not isinstance(exp, dict):
                    continue
                parts: List[str] = []
                for key in ("poste", "title", "entreprise", "company", "description"):
                    val = exp.get(key)
                    if isinstance(val, str) and val.strip():
                        parts.append(val.strip())
                missions = exp.get("missions")
                if isinstance(missions, list):
                    for m in missions:
                        if isinstance(m, str) and m.strip():
                            parts.append(m.strip())
                if parts:
                    experiences_texts.append(" ".join(parts))

        exp_low_joined = "\n".join(experiences_texts).lower()

        by_skill: Dict[str, Dict[str, Any]] = {}

        def keep_most_severe(item: Dict[str, Any]) -> None:
            skill = str(item.get("skill") or "").strip()
            if not skill:
                return
            prev = by_skill.get(skill)
            if prev is None or int(item.get("level", 0)) > int(prev.get("level", 0)):
                by_skill[skill] = item

        for skill in cv_skills:
            s = (skill or "").strip()
            if not s:
                continue
            # Chercher aussi la forme normalisée (alias) dans le texte
            s_low = s.lower()
            s_norm = _normalize_skill(s)

            in_raw = s_low in raw_low or s_norm in raw_low
            if not in_raw:
                keep_most_severe({"skill": s, "level": 1, "reason": "absent_from_text"})

            in_exp = s_low in exp_low_joined or s_norm in exp_low_joined
            # Un skill absent du texte d'expérience peut être couvert par son écosystème.
            # Ex : "Swift" absent mais "iOS" ou "Xcode" présents → pas d'alerte.
            if not in_exp:
                eco_covers_exp = any(
                    equiv in exp_low_joined
                    for equiv in _TECH_EXPANSION.get(s_norm, frozenset())
                )
                in_exp = in_exp or eco_covers_exp
            if experiences_texts and not in_exp:
                keep_most_severe(
                    {"skill": s, "level": 2, "reason": "absent_from_experiences"}
                )

            if s_low in ecosystems:
                need = ecosystems[s_low]
                if need not in raw_low:
                    keep_most_severe(
                        {
                            "skill": s,
                            "level": 3,
                            "reason": f"missing_ecosystem:{need}",
                        }
                    )

            # Level 4 — BERT context check uniquement si le skill n'est PAS
            # mentionné dans le texte brut ni dans les expériences.
            # Si la skill est dans le texte brut (in_raw), level 2 suffit
            # — doubler avec level 4 serait une double pénalisation injuste.
            if self._ensure_loaded() and experiences_texts and not in_exp and not in_raw:
                try:
                    exp_context = " ".join(experiences_texts)
                    emb = self._encode([s, _clip_words(exp_context, 512)])
                    sim = _cosine(np.asarray(emb[0], dtype=float), np.asarray(emb[1], dtype=float))
                    if float(sim) < 0.25:
                        keep_most_severe(
                            {
                                "skill": s,
                                "level": 4,
                                "reason": "low_context_similarity",
                            }
                        )
                except Exception:
                    pass

            # Level 5 — Faux expert : compétence déclarée avec niveau expert/avancé
            # MAIS le texte des expériences contredit ce niveau (notions, cours, jamais en prod)
            _EXPERT_CLAIMS = frozenset({
                "expert", "maîtrise avancée", "maitrise avancee", "maitrise avancée",
                "spécialiste", "specialiste", "fort niveau", "haut niveau",
                "maîtrise complète", "maitrise complete", "avancé", "avance",
                "confirmé", "confirme", "maitrise",
            })
            _NOVICE_SIGNALS = frozenset({
                "notions", "notion", "tutoriel", "tutoriels", "udemy", "coursera",
                "cours en ligne", "formation en ligne", "jamais en production",
                "jamais utilisé en entreprise", "test personnel", "tests personnels",
                "quelques instances", "quelques expérimentations", "quelques experimentations",
                "débutant", "debutant", "initiation", "découverte", "decouverte",
                "pas encore en production", "n'ai jamais", "peu d'expérience",
                "peu d experience", "quelques cours", "autodidacte",
            })
            if experiences_texts:
                skill_idx = raw_low.find(s_low)
                if skill_idx == -1:
                    skill_idx = raw_low.find(s_norm)
                skill_expert_claimed = False
                if skill_idx != -1:
                    ctx_around = raw_low[max(0, skill_idx - 40): skill_idx + len(s_low) + 80]
                    skill_expert_claimed = any(claim in ctx_around for claim in _EXPERT_CLAIMS)

                exp_has_novice = any(sig in exp_low_joined for sig in _NOVICE_SIGNALS)

                if skill_expert_claimed and exp_has_novice:
                    keep_most_severe({
                        "skill": s,
                        "level": 5,
                        "reason": "fake_expert_detected",
                    })

        out = list(by_skill.values())
        out.sort(key=lambda x: int(x.get("level", 0)), reverse=True)
        return out

    def compute_confidence(
        self,
        talentmatch_score: float,
        bert_base_score: float,
        heuristic_score: float,
    ) -> Dict[str, Any]:
        """
        Mesure l'accord entre les 3 composantes du matching.

        Si les 3 scores sont proches  → HAUTE  confiance
        Si légère divergence          → MOYENNE confiance
        Si forte divergence           → BASSE   confiance (vérif. humaine)

        Utilisé pour signaler au recruteur que le système est incertain.
        """
        scores = [
            max(0.0, min(1.0, float(talentmatch_score))),
            max(0.0, min(1.0, float(bert_base_score))),
            max(0.0, min(1.0, float(heuristic_score))),
        ]
        ecart = max(scores) - min(scores)

        if ecart < 0.15:
            niveau  = "HAUTE"
            message = "Les 3 modèles sont d'accord"
        elif ecart < 0.30:
            niveau  = "MOYENNE"
            message = "Légère divergence entre modèles"
        else:
            niveau  = "BASSE"
            message = "Vérification humaine recommandée"

        return {
            "niveau":   niveau,
            "ecart":    round(ecart, 3),
            "message":  message,
        }

    # ══════════════════════════════════════════════════════════════
    # SCORING MULTI-DIMENSIONNEL — 4 dimensions indépendantes
    # ══════════════════════════════════════════════════════════════

    def score_competences(
        self,
        offer_skills: List[str],
        cv_skills: List[str],
    ) -> float:
        """
        Dimension 1 — Compétences (40% du score final).

        Compte combien de compétences requises le candidat possède.
        RapidFuzz (seuil 80%) gère les variantes orthographiques :
        "Reactjs" ≈ "React.js", "PostgreSQL" ≈ "Postgres", etc.

        Exemples :
            Offre [Python, FastAPI, React, Docker] / CV [Python, FastAPI] → 0.50
            Offre [Python] / CV [Python, Django, Git]                     → 1.00
        """
        if not offer_skills:
            return 0.5

        matches = 0
        for required in offer_skills:
            req_norm = _normalize_skill(required)
            for cv_s in cv_skills:
                cv_norm = _normalize_skill(cv_s)
                # Alias-exact : "ReactJS" == "react" == "React.js" après normalisation
                if req_norm == cv_norm:
                    matches += 1
                    break
                # token_set_ratio gère les inversions ("REST API" ≈ "API REST")
                if fuzz.token_set_ratio(req_norm, cv_norm) >= 80:
                    matches += 1
                    break

        return round(min(1.0, matches / len(offer_skills)), 4)

    def score_experience(
        self,
        cv_years: float,
        required_years: float,
        offer_text: str = "",
        cv_experience_text: str = "",
    ) -> float:
        """
        Dimension 2 — Expérience (20% du score final).

        50% ratio années  +  50% similarité sémantique BERT du domaine d'expérience.
        Si le modèle est indisponible, repli sur le ratio seul.

        Exemples :
            Requis 2 ans dev Python, CV 3 ans dev Python → 1.00 (ratio OK + domaine OK)
            Requis 2 ans dev Python, CV 3 ans marketing  → ~0.55 (ratio OK, domaine éloigné)
            Requis 0 ans                                 → 1.00 (pas de prérequis)
        """
        # Composante 1 : ratio années
        if not required_years or required_years <= 0:
            years_ratio = 1.0
        elif cv_years >= required_years:
            years_ratio = 1.0
        else:
            years_ratio = max(0.0, cv_years / required_years)

        # Composante 2 : pertinence sémantique du domaine d'expérience
        if offer_text and cv_experience_text:
            domain_sim, _ = self.score_semantic(offer_text, cv_experience_text)
        else:
            domain_sim = years_ratio  # fallback : repli sur le ratio

        score = years_ratio * 0.50 + domain_sim * 0.50
        return round(max(0.0, min(1.0, score)), 4)

    def score_formation(
        self,
        cv_edu: float,
        required_edu: float,
    ) -> float:
        """
        Dimension 3 — Formation (15% du score final).

        Comparaison niveaux diplôme (Bac=1 … Doctorat=6).
        Dépasser le niveau requis → 100%.

        Exemples :
            Requis Bac+5, CV Bac+3 → 0.60
            Requis Bac+3, CV Bac+5 → 1.00
            Requis 0               → 1.00
        """
        if not required_edu or required_edu <= 0:
            return 1.0
        if cv_edu >= required_edu:
            return 1.0
        return round(max(0.0, cv_edu / required_edu), 4)

    def score_semantique_rerank(
        self,
        offer_text: str,
        cv_text: str,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Score sémantique via cross-encoder (offre+CV ensemble — pas deux embeddings séparés).

        Retourne (score 0..1, détails). Sigmoid sur les logits du reranker.
        Fallback transparent vers `score_semantic` (bi-encodeur) si reranker indisponible.
        """
        if not offer_text or not cv_text:
            return 0.5, {"ready": False, "reason": "empty_text", "method": "rerank"}

        if not self._ensure_reranker_loaded():
            # Fallback bi-encodeur si le reranker ne charge pas
            bi_score, bi_detail = self.score_semantic(offer_text, cv_text)
            bi_detail["method"] = "bi_encoder_fallback"
            bi_detail["reranker_reason"] = self.reranker_load_error or "unavailable"
            return bi_score, bi_detail

        try:
            # Le reranker reçoit la paire entière, ne nécessite pas de normalisation.
            # On clippe à ~512 mots pour rester dans la fenêtre max_length=512 du modèle.
            offer_input = _clip_words(offer_text, 256)
            cv_input    = _clip_words(cv_text,    256)
            logit = self._reranker.predict([(offer_input, cv_input)])
            # CrossEncoder.predict peut retourner np.ndarray ou float — on normalise.
            if hasattr(logit, "__len__"):
                logit_val = float(logit[0])
            else:
                logit_val = float(logit)
            # bge-reranker-v2-m3 émet des logits → sigmoid pour [0, 1].
            score = 1.0 / (1.0 + np.exp(-logit_val))
            score = float(max(0.0, min(1.0, score)))
            return score, {
                "ready": True,
                "model": self.reranker_model_name,
                "method": "cross_encoder",
                "raw_logit": round(logit_val, 4),
            }
        except Exception as e:
            return 0.5, {
                "ready": False,
                "reason": f"rerank_error:{type(e).__name__}",
                "model": self.reranker_model_name,
                "method": "rerank",
            }

    def score_semantique(
        self,
        offer_text: str,
        cv_text: str,
    ) -> float:
        """
        Dimension 4 — Sémantique (alimente le MLP, feature `sem_sim`).

        Utilise le cross-encoder (BGE-reranker-v2-m3) si chargé — signal beaucoup plus
        fort que le simple cosinus bi-encodeur. Fallback bi-encodeur sinon.
        """
        score, _ = self.score_semantique_rerank(offer_text, cv_text)
        return float(score)

    def _analyze_offer_profile(
        self,
        offer: "JobOffer",
        required_years: float,
        required_edu: float,
        offer_skills_count: int,
    ) -> Dict[str, Any]:
        """
        Analyse tous les signaux de l'offre pour déterminer le profil réel.
        Retourne un dict de flags utilisés par _dynamic_weights.
        """
        titre   = (offer.titre        or "").lower()
        desc    = (offer.description  or "").lower()
        contrat = (offer.type_contrat or "").lower()
        full    = titre + " " + desc

        # ── Type de poste ─────────────────────────────────────────
        is_stage       = any(k in contrat or k in full for k in ["stage", "internship", "stagiaire"])
        is_alternance  = any(k in contrat or k in full for k in ["alternance", "apprentissage", "alternant"])
        is_junior      = any(k in full for k in ["junior", "débutant", "debutant", "entry level", "sans expérience", "1ère expérience", "premiere experience"])
        is_senior      = any(k in full for k in ["senior", "lead", "expert", "confirmé", "confirme", "principal", "architect", "responsable", "manager", "chef de projet", "directeur"])

        # ── Domaine du poste ──────────────────────────────────────
        TECHNICAL_KEYWORDS = ["développeur", "developpeur", "developer", "ingénieur logiciel",
                               "data", "devops", "backend", "frontend", "fullstack",
                               "machine learning", "ia ", "ai ", "mlops", "cloud", "sécurité", "securite",
                               "python", "java", "react", "angular", "node", ".net", "php"]
        MANAGEMENT_KEYWORDS = ["manager", "directeur", "chef de projet", "responsable",
                                "commercial", "business", "vente", "marketing", "rh ",
                                "ressources humaines", "consultant", "account"]
        is_technical   = any(k in full for k in TECHNICAL_KEYWORDS) or offer_skills_count >= 4
        is_management  = any(k in full for k in MANAGEMENT_KEYWORDS)

        # ── Formation explicitement requise ───────────────────────
        STRONG_EDU = ["bac+5", "master", "ingénieur", "ingenieur", "grande école",
                      "grande ecole", "doctorat", "mba", "bac +5"]
        NO_EDU     = ["sans diplôme", "sans diplome", "niveau bac", "autodidacte",
                      "formation non requise", "pas de diplôme"]
        edu_required_explicit  = any(k in full for k in STRONG_EDU) or required_edu >= 5
        edu_not_required       = any(k in full for k in NO_EDU) or required_edu == 0

        return {
            "is_stage":              is_stage,
            "is_alternance":         is_alternance,
            "is_junior":             is_junior,
            "is_senior":             is_senior,
            "is_technical":          is_technical,
            "is_management":         is_management,
            "edu_required_explicit": edu_required_explicit,
            "edu_not_required":      edu_not_required,
            "required_years":        required_years,
            "offer_skills_count":    offer_skills_count,
        }

    def _dynamic_weights(
        self,
        profile: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Poids adaptatifs — s'adapte à CE QUE L'OFFRE DEMANDE réellement.

        Exemples :
          Stage/Alternance  → exp≈0%, formation monte, compétences + sémantique priment
          Junior (0 ans)    → exp très faible, compétences + sémantique fortes
          Confirmé (2-4 ans)→ poids équilibrés
          Senior (5+ ans)   → exp très forte
          Technique (dev)   → compétences forte
          Management        → sémantique forte
          Diplôme exigé     → formation monte
          Pas de diplôme    → formation ≈ 0%
          Peu de skills     → sémantique compensatrice
        """
        # ── Poids initiaux de base ────────────────────────────────
        w_comp = 0.40
        w_exp  = 0.20
        w_form = 0.15
        w_sem  = 0.25

        required_years      = profile["required_years"]
        offer_skills_count  = profile["offer_skills_count"]

        # ── 1. Adapter selon le type de poste ────────────────────
        if profile["is_stage"] or profile["is_alternance"]:
            # Étudiant : exp quasi nulle, formation importante, skills + sémantique
            w_exp  = 0.03
            w_comp = 0.42
            w_form = 0.22
            w_sem  = 0.33

        elif profile["is_junior"] or required_years == 0:
            # Junior : peu d'exp attendue
            w_exp  = 0.06
            w_comp = 0.44
            w_form = 0.15
            w_sem  = 0.35

        elif profile["is_senior"] or required_years >= 5:
            # Senior : expérience très importante
            w_exp  = 0.33
            w_comp = 0.34
            w_form = 0.13
            w_sem  = 0.20

        elif required_years >= 3:
            # Confirmé
            w_exp  = 0.25
            w_comp = 0.38
            w_form = 0.14
            w_sem  = 0.23

        else:
            # Débutant / 1-2 ans
            w_exp  = 0.12
            w_comp = 0.43
            w_form = 0.15
            w_sem  = 0.30

        # ── 2. Adapter selon le domaine ──────────────────────────
        if profile["is_technical"] and not profile["is_management"]:
            # Poste technique → compétences techniques priment
            w_comp += 0.05
            w_sem  -= 0.05
        elif profile["is_management"] and not profile["is_technical"]:
            # Poste management/commercial → sémantique et soft skills priment
            w_sem  += 0.08
            w_comp -= 0.08

        # ── 3. Adapter selon la formation ────────────────────────
        if profile["edu_required_explicit"]:
            # Diplôme clairement exigé → formation pèse plus
            w_form += 0.08
            w_sem  -= 0.08
        elif profile["edu_not_required"]:
            # Pas de diplôme requis → formation quasi nulle
            delta   = w_form * 0.80
            w_form -= delta
            w_comp += delta * 0.5
            w_sem  += delta * 0.5

        # ── 4. Adapter selon le nombre de skills ─────────────────
        if offer_skills_count < 3:
            # Peu de skills listées → sémantique compensatrice
            delta   = w_comp * 0.35
            w_comp -= delta
            w_sem  += delta
        elif offer_skills_count >= 8:
            # Beaucoup de skills → les compétences sont le critère principal
            w_comp += 0.04
            w_sem  -= 0.04

        # ── Normaliser pour que la somme = 1.0 ───────────────────
        w_comp = max(0.05, w_comp)
        w_exp  = max(0.02, w_exp)
        w_form = max(0.02, w_form)
        w_sem  = max(0.05, w_sem)
        total  = w_comp + w_exp + w_form + w_sem
        return {
            "competences": round(w_comp / total, 4),
            "experience":  round(w_exp  / total, 4),
            "formation":   round(w_form / total, 4),
            "semantique":  round(w_sem  / total, 4),
        }

    def score(
        self,
        offer: JobOffer,
        candidate: Candidate,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Score final multi-dimensionnel TalentMatch — poids adaptatifs.

        Les poids changent selon ce que l'offre exige réellement :
        junior → expérience quasi-nulle, senior → expérience forte.

        Résultat absolu — indépendant des autres candidats.
        """
        # ── Extraction des données ────────────────────────────────
        offer_skills   = _extract_offer_skills(offer)
        cv_skills      = _candidate_skills(candidate)
        cand_years     = _candidate_years(candidate)
        cand_edu       = _candidate_education_level(candidate)
        desc_blob      = ((offer.description or "") + "\n" + (offer.titre or "")).strip()
        required_years = (
            int(offer.experience_requise)
            if getattr(offer, 'experience_requise', None) is not None
            else (_extract_required_years(desc_blob) or 0)
        )
        required_edu   = _extract_required_education_level(desc_blob) or 0
        offer_text     = _offer_text_for_semantic(offer)
        cv_text        = _candidate_text_for_semantic(candidate)

        # ── Texte d'expérience candidat (pour BERT expérience) ───
        parsed_for_exp = candidate.parsed_data if isinstance(candidate.parsed_data, dict) else {}
        exp_parts: List[str] = []
        for exp in (parsed_for_exp.get("experiences") or []):
            if not isinstance(exp, dict):
                continue
            for key in ("poste", "title", "entreprise", "company", "description"):
                val = exp.get(key)
                if isinstance(val, str) and val.strip():
                    exp_parts.append(val.strip())
        cv_experience_text = _clip_words(" ".join(exp_parts), 128) if exp_parts else ""

        # ── 4 dimensions ─────────────────────────────────────────
        # Compétences : hybride RapidFuzz + BERT + fallback texte brut
        # Normaliser les apostrophes typographiques (U+2019) → ASCII (U+0027)
        # pour que "pas d'expérience" soit détecté même dans les PDFs reportlab.
        raw_lower = (candidate.raw_text or "").lower().replace("’", "'").replace("‘", "'")

        # Filtrer les skills extraits par le parseur NLP mais mentionnés
        # uniquement dans un contexte négatif ("Aucune compétence en Python").
        # Le parseur détecte les mots-clés sans comprendre la négation.
        _NEGATIONS_CTX = ("pas de", "pas d'", "sans ", "aucune", "aucun",
                          "jamais", "no ", "not ", "without", "non ",
                          "zero", "n'ai pas", "n'a pas", "ne pas",
                          "peu utilis", "peu d'exp")

        def _is_negated(skill_name: str) -> bool:
            s_low  = skill_name.lower()
            s_norm = _normalize_skill(skill_name)
            all_negated = True
            for term in {s_low, s_norm}:
                idx = 0
                found_any = False
                while True:
                    pos = raw_lower.find(term, idx)
                    if pos == -1:
                        break
                    found_any = True
                    ctx = raw_lower[max(0, pos - 60): pos]
                    if not any(neg in ctx for neg in _NEGATIONS_CTX):
                        return False  # au moins une occurrence positive
                    idx = pos + 1
                if found_any:
                    all_negated = True
            # Si le skill n'est pas dans le texte brut du tout → non nié (extrait d'une section structurée)
            return raw_lower.count(s_low) > 0 and all_negated

        cv_skills_filtered = [s for s in cv_skills if not _is_negated(s)]

        # ── Inférence compétences implicites par titre professionnel ──────────
        _cand_domain, _cand_role_level, _implied_skills = _detect_profession_from_cv(
            raw_lower, parsed_for_exp
        )
        _implied_norms = {_normalize_skill(s) for s in cv_skills_filtered}
        for _imp in _implied_skills:
            if _normalize_skill(_imp) not in _implied_norms:
                cv_skills_filtered = cv_skills_filtered + [_imp]
                _implied_norms.add(_normalize_skill(_imp))

        cv_norms  = {_normalize_skill(s): s for s in cv_skills_filtered}

        skills_matched: List[Dict[str, str]] = []
        skills_missing: List[str] = []
        total_comp = 0.0

        for skill in offer_skills:
            norm = _normalize_skill(skill)
            # 1) Match exact après normalisation alias
            if norm in cv_norms:
                skills_matched.append({"skill": skill, "source": "extrait"})
                total_comp += 1.0
                continue
            # 2) Fuzzy match sur les skills parsés (filtrés — sans les niés)
            best_fz = max(
                (fuzz.token_set_ratio(norm, _normalize_skill(s)) for s in cv_skills_filtered),
                default=0,
            )
            if best_fz >= 80:
                skills_matched.append({"skill": skill, "source": "fuzzy"})
                total_comp += 1.0
                continue
            # 2b) Expansion écosystème — "iOS" satisfait par "Swift", "Android" par "Kotlin"
            cv_norms_set = {_normalize_skill(s) for s in cv_skills_filtered}
            eco_set = _TECH_EXPANSION.get(norm, frozenset())
            eco_found = bool(eco_set and cv_norms_set & eco_set)
            if not eco_found:
                # Sens inverse : le CV a "swift", l'offre demande "ios" (swift → {ios})
                for cv_norm in cv_norms_set:
                    if norm in _TECH_EXPANSION.get(cv_norm, frozenset()):
                        eco_found = True
                        break
            if eco_found:
                skills_matched.append({"skill": skill, "source": "ecosystem"})
                total_comp += 0.9
                continue

            # 3) Fallback texte brut — uniquement si la mention n'est pas niée.
            # Cherche la skill dans le texte brut, puis vérifie qu'aucun mot de
            # négation n'apparaît dans les 60 caractères qui précèdent.
            skill_lower = skill.lower()
            idx = raw_lower.find(norm) if norm in raw_lower else (
                raw_lower.find(skill_lower) if skill_lower in raw_lower else -1
            )
            if idx != -1:
                context_before = raw_lower[max(0, idx - 60):idx]
                if not any(neg in context_before for neg in _NEGATIONS_CTX):
                    skills_matched.append({"skill": skill, "source": "texte_brut"})
                    total_comp += 0.7
                    continue
            skills_missing.append(skill)

        s_fuzzy_v2    = round(min(1.0, total_comp / max(1, len(offer_skills))), 4) if offer_skills else 0.5
        s_bert_skills, _ = self.score_skills_bert(offer_skills, cv_skills_filtered)
        # Fuzzy est le signal principal (exact + alias + texte brut).
        # BERT peut ajouter au max +10% pour les synonymes proches (PyTorch ≈ TensorFlow)
        # mais ne peut pas compenser des skills complètement absents.
        _bert_bonus   = max(0.0, s_bert_skills - s_fuzzy_v2) * 0.20
        s_competences = round(min(1.0, s_fuzzy_v2 + _bert_bonus), 4)
        # Expérience  : ratio années + BERT domaine
        s_experience  = self.score_experience(cand_years, required_years, offer_text, cv_experience_text)
        s_formation   = self.score_formation(cand_edu, required_edu)

        # ── Prestige institution de formation ────────────────────────────────
        _prestige = _institution_prestige_score(parsed_for_exp)
        # 70% niveau diplôme + 30% prestige institution (ajustement modéré)
        s_formation = round(s_formation * (0.70 + 0.30 * _prestige), 4)

        # Formation domaine — Bac+5 Informatique ≠ Bac+5 Marketing pour un poste dev
        # Ajuste le score formation par la pertinence sémantique du domaine d'études
        if required_edu > 0:
            _edu_texts: List[str] = []
            _parsed_edu = parsed_for_exp.get("formations") or parsed_for_exp.get("education") or []
            if isinstance(_parsed_edu, list):
                for _edu in _parsed_edu:
                    if isinstance(_edu, dict):
                        for _key in ("diplome", "etablissement", "domaine", "specialite",
                                     "degree", "school", "titre", "field"):
                            _val = _edu.get(_key)
                            if isinstance(_val, str) and _val.strip():
                                _edu_texts.append(_val.strip())
            if _edu_texts and offer_text:
                _edu_domain_sim, _ = self.score_semantic(
                    offer_text, _clip_words(" ".join(_edu_texts), 128)
                )
                # 70% niveau diplôme + 30% pertinence domaine d'études
                s_formation = round(s_formation * 0.70 + _edu_domain_sim * 0.30, 4)

        s_semantique  = self.score_semantique(offer_text, cv_text)

        # ── Poids dynamiques selon le profil de l'offre ─────────
        offer_profile = self._analyze_offer_profile(offer, required_years, required_edu, len(offer_skills))
        W = self._dynamic_weights(offer_profile)

        # Fix 2 — Formation pénalisée si compétences faibles.
        # Un Bac+5 en Java ne compense pas un poste Python.
        if s_competences <= 0.50:
            s_formation = s_formation * 0.5

        # Fix 5 — Expérience pénalisée si domaine incompatible.
        # 5 ans de Java ne valent pas grand chose pour un poste Python/ML.
        if s_competences <= 0.40:
            s_experience = s_experience * (0.5 + s_competences)  # réduit graduellement

        # Plancher/plafond appliqués après MLP (voir section MLP ci-dessous)

        # ── Détection incohérences (signal qualitatif + quantitatif) ──
        parsed = candidate.parsed_data if isinstance(candidate.parsed_data, dict) else {}
        experiences = parsed.get("experiences") if isinstance(parsed, dict) else []
        cv_skills_lower = {s.lower() for s in cv_skills}
        skills_to_check = [s for s in offer_skills if s.lower() in cv_skills_lower]
        inconsistencies = self.detect_skill_inconsistencies(
            cv_skills=skills_to_check if skills_to_check else offer_skills[:5],
            cv_experiences=experiences,
            cv_raw_text=(candidate.raw_text or ""),
        )

        # ── Pénalités incohérences appliquées au score final ─────
        # Chaque niveau d'incohérence réduit le score pour refléter le risque réel.
        inco_penalty = 0.0
        has_fake_expert = False
        for _inc in inconsistencies:
            _lvl = int(_inc.get("level", 0))
            if _lvl == 2:
                inco_penalty += 0.05   # skill absent des expériences
            elif _lvl == 3:
                inco_penalty += 0.04   # écosystème manquant
            elif _lvl == 4:
                inco_penalty += 0.08   # BERT contexte trop faible
            elif _lvl == 5:
                inco_penalty += 0.15   # faux expert détecté
                has_fake_expert = True
        inco_penalty = min(inco_penalty, 0.20)   # cap global −20%
        # Pénalités appliquées après le MLP (voir section ci-dessous)

        # ── Matching compétences appréciées ──────────────────────
        appreciated_skills = _safe_list_of_strings(
            getattr(offer, "competences_appreciees", None) or []
        )
        criteres_apprecies: List[Dict[str, Any]] = []
        appreciated_matched = 0

        for _skill_apr in appreciated_skills:
            _norm_apr = _normalize_skill(_skill_apr)
            _matched_apr = False
            _source_apr: Optional[str] = None

            if _norm_apr in cv_norms:
                _matched_apr, _source_apr = True, "extrait"
            else:
                _best_fz_apr = max(
                    (fuzz.token_set_ratio(_norm_apr, _normalize_skill(s)) for s in cv_skills_filtered),
                    default=0,
                )
                if _best_fz_apr >= 80:
                    _matched_apr, _source_apr = True, "fuzzy"
                else:
                    _cv_norms_apr = {_normalize_skill(s) for s in cv_skills_filtered}
                    _eco_apr = _TECH_EXPANSION.get(_norm_apr, frozenset())
                    _eco_found_apr = bool(_eco_apr and _cv_norms_apr & _eco_apr)
                    if not _eco_found_apr:
                        for _cn in _cv_norms_apr:
                            if _norm_apr in _TECH_EXPANSION.get(_cn, frozenset()):
                                _eco_found_apr = True
                                break
                    if _eco_found_apr:
                        _matched_apr, _source_apr = True, "ecosystem"
                    else:
                        _sl_apr = _skill_apr.lower()
                        _idx_apr = (
                            raw_lower.find(_norm_apr) if _norm_apr in raw_lower
                            else raw_lower.find(_sl_apr) if _sl_apr in raw_lower
                            else -1
                        )
                        if _idx_apr != -1:
                            _ctx_apr = raw_lower[max(0, _idx_apr - 60): _idx_apr]
                            if not any(_neg in _ctx_apr for _neg in _NEGATIONS_CTX):
                                _matched_apr, _source_apr = True, "texte_brut"

            criteres_apprecies.append({
                "skill": _skill_apr,
                "matched": _matched_apr,
                "source": _source_apr,
            })
            if _matched_apr:
                appreciated_matched += 1

        # ── Taux compétences appréciées pour le MLP ──────────────
        apr_rate = (appreciated_matched / len(appreciated_skills)) if appreciated_skills else 0.5

        # ── Détection séniorité — pénalité si junior pour poste senior ──────
        _offer_senior_level = _detect_seniority_level(
            (offer.titre or "") + " " + (offer.description or "")[:200]
        )
        _cv_senior_texts = " ".join([
            raw_lower[:300],
            *[str(e.get("poste", "") or e.get("title", "")) for e in
              (parsed_for_exp.get("experiences") or [])[:2] if isinstance(e, dict)]
        ])
        _cand_senior_level = _detect_seniority_level(_cv_senior_texts)

        if _offer_senior_level >= 4 and 0 < _cand_senior_level <= 2:
            # Offre Senior/Expert mais candidat Junior/Stagiaire
            _senior_gap = _offer_senior_level - _cand_senior_level
            s_competences = round(max(0.0, s_competences - 0.10 * _senior_gap), 4)
            s_experience  = round(max(0.0, s_experience  - 0.15 * _senior_gap), 4)
        elif _offer_senior_level <= 1 and _cand_senior_level >= 4:
            # Offre stage mais candidat senior — surqualifié (pénalité légère)
            s_competences = round(min(s_competences, 0.85), 4)

        # ── Détection mismatch domaine professionnel ─────────────
        _offer_domain, _offer_role_level = _detect_offer_domain(offer)
        _domain_cap: Optional[float] = None   # cap sur score_final
        _domain_penalty_exp = 0.0             # pénalité sur s_experience

        if _offer_domain and _cand_domain:
            if _offer_domain != _cand_domain:
                _pair = (_offer_domain, _cand_domain)
                if _pair in _ADJACENT_DOMAINS:
                    _domain_cap = 0.62   # adjacent → au max "à évaluer" haut
                else:
                    _domain_cap = 0.44   # domaine différent → "non adapté"
            else:
                # Même domaine mais niveau de rôle insuffisant
                if _cand_role_level > 0 and _offer_role_level > 0:
                    _lvl_diff = _offer_role_level - _cand_role_level
                    if _lvl_diff >= 2:
                        _domain_penalty_exp = 0.20   # trop junior
                    elif _lvl_diff == 1:
                        _domain_penalty_exp = 0.10   # légèrement junior

        if _domain_penalty_exp > 0:
            s_experience = round(max(0.0, s_experience - _domain_penalty_exp), 4)

        # ── Score final — MLP ou formule pondérée ────────────────
        mlp_result = self._mlp_score(
            sem_sim          = float(s_semantique),
            skill_rate       = float(s_competences),
            exp_score        = float(s_experience),
            formation_score  = float(s_formation),
            appreciated_rate = float(apr_rate),
        )

        if mlp_result is not None:
            # Le MLP décide du score — pas une formule manuelle
            score_final = round(max(0.20, min(0.95, mlp_result)), 4)
        else:
            # Fallback : formule pondérée si MLP indisponible
            score_final = (
                s_competences * W["competences"]
                + s_experience  * W["experience"]
                + s_formation   * W["formation"]
                + s_semantique  * W["semantique"]
            )
            if s_competences < 0.25:
                score_final = min(score_final, 0.32)
            elif s_competences < 0.40:
                score_final = min(score_final, 0.42)
            elif s_competences <= 0.50:
                score_final = min(score_final, 0.52)
            score_final = round(max(0.20, min(0.95, score_final)), 4)

        # Bonus appréciées si MLP absent
        if mlp_result is None and appreciated_skills:
            _apr_bonus = apr_rate * 0.08
            score_final = round(min(0.95, score_final + _apr_bonus), 4)

        # ── Pénalités incohérences (appliquées après MLP) ────────
        score_final = round(max(0.20, score_final - inco_penalty), 4)
        if has_fake_expert:
            score_final = min(score_final, 0.45)

        # ── Cap domaine professionnel ─────────────────────────────
        if _domain_cap is not None:
            score_final = round(min(score_final, _domain_cap), 4)

        # ── Critères obligatoires (reformattés pour affichage) ────
        criteres_obligatoires: List[Dict[str, Any]] = []
        for _m in skills_matched:
            criteres_obligatoires.append({
                "skill": _m["skill"], "matched": True, "source": _m["source"]
            })
        for _ms in skills_missing:
            criteres_obligatoires.append({
                "skill": _ms, "matched": False, "source": None
            })

        # ── Score de confiance ────────────────────────────────────
        _n_inco   = len(inconsistencies)
        _has_l5   = has_fake_expert
        _has_l4   = any(i.get("level") == 4 for i in inconsistencies)
        if _has_l5 or _n_inco >= 3:
            _confidence = {"niveau": "BASSE",   "message": "Vérification humaine fortement recommandée"}
        elif _has_l4 or _n_inco >= 1:
            _confidence = {"niveau": "MOYENNE", "message": "Quelques incohérences détectées"}
        else:
            _confidence = {"niveau": "HAUTE",   "message": "Profil cohérent — modèle confiant"}

        # ── Décision automatique ─────────────────────────────────
        _pct = score_final * 100
        _decision = (
            "Excellent candidat"                if _pct >= 75 else
            "Bon profil - Entretien recommandé" if _pct >= 58 else
            "Profil partiel - À évaluer"        if _pct >= 42 else
            "Profil non adapté"
        )

        # ── Breakdown détaillé ───────────────────────────────────
        details: Dict[str, Any] = {
            "decision": _decision,
            # Dimensions en pourcentage
            "competences": round(s_competences * 100, 1),
            "experience":  round(s_experience  * 100, 1),
            "formation":   round(s_formation   * 100, 1),
            "semantique":  round(s_semantique  * 100, 1),
            "total":       round(score_final   * 100, 1),
            "poids": {
                "competences": f"{round(W['competences']*100)}% (BERT skills)",
                "experience":  f"{round(W['experience']*100)}% (BERT domaine + années)",
                "formation":   f"{round(W['formation']*100)}% (niveau diplôme + domaine)",
                "semantique":  f"{round(W['semantique']*100)}% (BERT global)",
            },
            "profil_offre": {
                "type":    "stage/alternance" if (offer_profile["is_stage"] or offer_profile["is_alternance"])
                           else "junior"    if (offer_profile["is_junior"] or required_years == 0)
                           else "senior"    if (offer_profile["is_senior"] or required_years >= 5)
                           else "confirmé"  if required_years >= 3
                           else "débutant",
                "domaine": "technique"  if offer_profile["is_technical"]
                           else "management" if offer_profile["is_management"]
                           else "général",
                "required_years":      required_years,
                "edu_explicite":       offer_profile["edu_required_explicit"],
            },
            # Critères comparatifs — obligatoires vs appréciés
            "criteres": {
                "obligatoires": criteres_obligatoires,
                "apprecies":    criteres_apprecies,
            },
            # Pénalités incohérences appliquées
            "inco_penalty_pct": round(inco_penalty * 100, 1),
            "has_fake_expert":  has_fake_expert,
            # Score de confiance
            "confidence":       _confidence,
            # Explication par skills (compat)
            "skills_matched":      skills_matched,
            "skills_missing":      skills_missing,
            "skills_match_rate":   round(len(skills_matched) / max(1, len(offer_skills)) * 100, 1),
            # Détails contextuels
            "offer_skills_count":  len(offer_skills),
            "cv_skills_count":     len(cv_skills),
            "required_years":      required_years,
            "candidate_years":     cand_years,
            "required_edu":        required_edu,
            "candidate_edu":       cand_edu,
            "inconsistencies":     inconsistencies,
            # Domaine professionnel détecté
            "candidate_domain":    _cand_domain,
            "offer_domain":        _offer_domain,
            "domain_cap_applied":  _domain_cap is not None,
            "institution_prestige": round(_prestige, 2),
            "implied_skills_added": _implied_skills,
            # Compat backend/frontend
            "ready":               bool(self.ready),
            "model":               self.model_name,
            "mlp_used":            mlp_result is not None,
            "bert_semantic":       round(s_semantique, 4),
            "bert_skills":         round(s_competences, 4),
        }

        return score_final, details