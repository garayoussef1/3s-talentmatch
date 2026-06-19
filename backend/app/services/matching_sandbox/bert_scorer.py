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
from app.services.matching_sandbox.esco_service import EscoService
from app.services.matching.match_engine import (
    _candidate_education_level,
    _candidate_skills,
    _candidate_text_for_semantic,
    _candidate_years,
    _extract_offer_skills,
    _extract_required_education_level,
    _extract_required_years,
    _normalize_offer_text,
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

# ── A1 : Chargement depuis skills_aliases.json (ESCO + curé multi-domaine) ──
# Remplace skill_expansion.json (pollué par des faux positifs ESCO).
# Généré par scripts/build_skills_aliases.py — relancer si besoin.
def _load_skill_expansion() -> Dict[str, frozenset]:
    import json as _json
    import os as _os
    import unicodedata as _ud

    def _norm(t: str) -> str:
        t = t.lower().strip()
        t = _ud.normalize("NFKD", t)
        return "".join(c for c in t if not _ud.combining(c))

    # Priorité 1 : skills_aliases.json (A1 — propre et multi-domaine)
    _path_clean = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(
            _os.path.dirname(_os.path.abspath(__file__)))))),
        "data", "skills", "skills_aliases.json"
    )
    merged: dict = {}
    if _os.path.exists(_path_clean):
        try:
            with open(_path_clean, encoding="utf-8") as _f:
                _data = _json.load(_f)
            for _key, _syns in _data.items():
                _k = _norm(_key)
                if _k not in merged:
                    merged[_k] = set()
                for _s in _syns:
                    _sn = _norm(_s)
                    if _sn and _sn != _k:
                        merged[_k].add(_sn)
            print(f"[SkillAliases] {len(merged)} skills chargées depuis skills_aliases.json")
        except Exception as _e:
            print(f"[SkillAliases] Erreur chargement : {_e}")
    else:
        print("[SkillAliases] skills_aliases.json absent — lancez scripts/build_skills_aliases.py")

    return {k: frozenset(v) for k, v in merged.items() if v}

_TECH_EXPANSION = _load_skill_expansion()

import re as _re

# ─────────────────────────────────────────────────────────────────────────────
# Détection de domaine : remplacé par EscoService (ISCO-08 universel).
# L'ancienne ontologie hardcodée (~20 métiers) est conservée ci-dessous
# uniquement comme fallback si ESCO n'est pas disponible.
# ─────────────────────────────────────────────────────────────────────────────
_PROFESSION_ONTOLOGY_FALLBACK: List[Tuple[str, str, int, List[str]]] = [

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

    # ── DESIGN UX/UI / GRAPHIQUE ──────────────────────────────────────────────
    (r"designer?.+(?:ux|ui)|ux.+designer?|ui.+designer?|designer?.+(?:graphique|web|numérique|digitale?)|web\s+designer?|graphic\s+designer?|motion\s+designer?|créateur?.+visuel", "design", 3,
     ["figma", "ux design", "ui design", "prototypage", "wireframes", "user research", "sketch", "adobe xd"]),
    (r"\bdesigner?\b", "design", 3,
     ["figma", "ux design", "ui design"]),

    # ── TECHNICIEN IT / SUPPORT ───────────────────────────────────────────────
    (r"technicien?.+(?:informatique|it|réseau|système|support|helpdesk|maintenance\s+informatique)|technicien?.+développ|support\s+(?:technique|it|informatique|n[123]|helpdesk)|assistant?\s+(?:technique|informatique)", "it", 2,
     ["maintenance informatique", "support technique", "résolution de problèmes"]),
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

# _ADJACENT_DOMAINS remplacé par EscoService.are_adjacent() / get_score_cap()

# ── Domaines d'études — mots-clés de spécialité ──────────────────────────────
# Chaque domaine = ensemble de mots-clés trouvables dans la spécialité du diplôme
# ET dans les skills/description de l'offre.
_EDU_DOMAINS: Dict[str, frozenset] = {
    "informatique": frozenset({
        "informatique", "génie logiciel", "software", "computer science",
        "développement", "programmation", "systèmes", "réseaux",
        "cybersécurité", "data", "ia", "intelligence artificielle",
        "numérique", "digital", "web", "mobile", "cloud", "devops",
        "python", "java", "algorithme", "base de données", "si",
    }),
    "finance": frozenset({
        "finance", "comptabilité", "accounting", "gestion", "économie",
        "audit", "fiscalité", "banque", "bourse", "trésorerie",
        "contrôle de gestion", "sciences économiques", "management financier",
        "gestion financière", "analyse financière", "microéconomie",
    }),
    "marketing": frozenset({
        "marketing", "communication", "commerce", "vente", "publicité",
        "média", "stratégie commerciale", "brand", "digital marketing",
        "community", "relations publiques",
    }),
    "rh": frozenset({
        "ressources humaines", "rh", "management", "gestion des ressources",
        "psychologie du travail", "relations sociales", "droit social",
        "talent", "recrutement", "formation professionnelle",
    }),
    "droit": frozenset({
        "droit", "juridique", "law", "sciences juridiques", "notariat",
        "droit des affaires", "droit public", "droit privé", "avocat",
    }),
    "medecine": frozenset({
        "médecine", "santé", "soins", "pharmacie", "paramédical",
        "infirmier", "dentaire", "biomédical", "sciences médicales",
        "chirurgie", "pathologie", "biologie médicale", "kiné",
    }),
    "btp": frozenset({
        "génie civil", "architecture", "construction", "btp",
        "topographie", "bâtiment", "travaux publics", "structures",
        "géotechnique", "hydraulique",
    }),
    "logistique": frozenset({
        "logistique", "supply chain", "transport", "achats",
        "génie industriel", "gestion de production", "qualité",
        "lean", "management industriel",
    }),
    "sciences": frozenset({
        "chimie", "physique", "biologie", "mathématiques",
        "sciences", "physique-chimie", "biochimie",
    }),
    "lettres": frozenset({
        "lettres", "langues", "littérature", "traduction",
        "français", "anglais", "linguistique", "fle",
    }),
}

# Groupes adjacents — domaines proches → pénalité réduite
_EDU_ADJACENT: Dict[str, frozenset] = {
    "informatique": frozenset({"sciences", "logistique"}),
    "finance":      frozenset({"marketing", "rh", "logistique"}),
    "marketing":    frozenset({"finance", "rh"}),
    "rh":           frozenset({"droit", "finance", "marketing"}),
    "droit":        frozenset({"rh", "finance"}),
    "medecine":     frozenset({"sciences"}),
    "btp":          frozenset({"sciences", "logistique"}),
    "logistique":   frozenset({"finance", "informatique", "btp"}),
    "sciences":     frozenset({"informatique", "médecine", "btp"}),
    "lettres":      frozenset({"rh", "marketing"}),
}


def _normalize_accents(text: str) -> str:
    """Normalise les accents pour comparaison robuste."""
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _detect_edu_domain(text: str) -> Optional[str]:
    """Détecte le domaine d'études depuis un texte (spécialité, description offre...)."""
    text_norm = _normalize_accents(text.lower())
    best_domain = None
    best_score = 0
    for domain, keywords in _EDU_DOMAINS.items():
        hits = sum(1 for kw in keywords if _normalize_accents(kw) in text_norm)
        if hits > best_score:
            best_score = hits
            best_domain = domain
    return best_domain if best_score >= 1 else None


def _edu_domain_compatibility(cand_domain: Optional[str], offer_domain: Optional[str]) -> float:
    """
    Retourne la compatibilité entre domaine d'études candidat et domaine de l'offre.

    Mêmes domaine       → 1.00
    Domaines adjacents  → 0.75
    Domaines différents → 0.45
    Domaine inconnu     → 0.80 (on ne pénalise pas si on ne sait pas)
    """
    if cand_domain is None or offer_domain is None:
        return 0.80
    if cand_domain == offer_domain:
        return 1.00
    if offer_domain in _EDU_ADJACENT.get(cand_domain, frozenset()):
        return 0.75
    return 0.45


def _isco_role_level(major_group: int) -> int:
    """Convertit un major group ISCO en niveau de rôle 1-5."""
    if major_group == 1: return 5   # managers/directeurs
    if major_group == 2: return 4   # professionnels bac+3/5
    if major_group == 3: return 3   # techniciens
    if major_group in (4, 5): return 2   # employés / services
    if major_group >= 6: return 1   # artisans, ouvriers, élémentaire
    return 3


def _hard_formation_cap(required_edu: int, cand_edu: int) -> Optional[float]:
    """
    Cap dur basé sur l'écart de niveau de formation.
    S'applique INDÉPENDAMMENT de la compatibilité de domaine ESCO :
    même si infirmier et pédiatre sont "adjacents" en ESCO, un gap
    de 5 niveaux de diplôme est rédhibitoire en recrutement réel.

    Mapping niveaux : 0=sans, 1=Bac, 2=Bac+2, 3=Bac+3, 4=Bac+4,
                      5=Bac+5, 8=Bac+8 (médecine/doctorat)
    """
    if required_edu <= 0 or cand_edu <= 0:
        return None   # formation non renseignée → pas de cap dur
    gap = required_edu - cand_edu
    if gap >= 5: return 0.25   # ex: Bac+3 → Bac+8 (infirmier → médecin)
    if gap >= 3: return 0.40   # ex: Bac+2 → Bac+5 (technicien → master)
    if gap >= 2: return 0.52   # ex: Bac+3 → Bac+5 (licence → master)
    if gap == 1: return 0.65   # ex: Bac+4 → Bac+5
    return None                # même niveau ou candidat surqualifié → pas de cap


def _detect_profession_from_cv(
    raw_lower: str, parsed_data: Dict[str, Any]
) -> Tuple[Optional[Dict], int, List[str]]:
    """
    Détecte le domaine ISCO-08 du candidat via EscoService (universel).
    Retourne (domaine_dict, niveau_rôle 1-5, compétences_implicites).
    """
    esco = EscoService.get()

    # Construire les textes candidats par ordre de priorité
    candidate_texts: List[str] = []
    meta = parsed_data.get("metadata") or {}
    for key in ("titre_professionnel", "titre", "poste", "current_title", "intitule"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            candidate_texts.append(val.strip())
    for exp in (parsed_data.get("experiences") or [])[:3]:
        if not isinstance(exp, dict):
            continue
        for key in ("poste", "title", "intitule", "fonction", "position"):
            val = exp.get(key)
            if isinstance(val, str) and val.strip():
                candidate_texts.append(val.strip())
    candidate_texts.append(raw_lower[:300])

    # Trouver le meilleur domaine ESCO
    best: Optional[Dict] = None
    best_score = 0.0
    for text in candidate_texts:
        result = esco.detect_domain(text)
        if result and result["score"] > best_score:
            best_score = result["score"]
            best = result

    if best is None:
        # Fallback : ancienne ontologie hardcodée si ESCO non chargé
        for text in candidate_texts:
            for (pattern, domain, level, skills) in _PROFESSION_ONTOLOGY_FALLBACK:
                if _re.search(pattern, text, _re.IGNORECASE):
                    return {"isco_code": domain, "major_group": 0, "skills_fr": skills}, level, skills
        return None, 0, []

    level = _isco_role_level(best["major_group"])
    return best, level, best.get("skills_fr", [])


def _detect_offer_domain(offer: Any) -> Tuple[Optional[Dict], int]:
    """Détecte le domaine ISCO-08 de l'offre via EscoService (universel)."""
    esco = EscoService.get()
    offer_text = ((offer.titre or "") + " " + ((offer.description or "")[:300])).strip()
    result = esco.detect_domain(offer_text)

    if result is None:
        # Fallback ancienne ontologie
        offer_lower = offer_text.lower()
        for (pattern, domain, level, _skills) in _PROFESSION_ONTOLOGY_FALLBACK:
            if _re.search(pattern, offer_lower, _re.IGNORECASE):
                return {"isco_code": domain, "major_group": 0, "skills_fr": []}, level
        return None, 0

    level = _isco_role_level(result["major_group"])
    return result, level


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


def _extract_title_skill(offer_title: str, offer_skills: List[str], encode_fn=None) -> Optional[str]:
    """
    Détecte la compétence CENTRALE du poste — uniquement si le titre la nomme
    explicitement. C'est un signal FIABLE : on ne pénalise un candidat que si le
    titre désigne clairement une compétence (ex: "Développeur Python") qu'il n'a
    pas. Sur un titre générique ("Stage Web Full Stack", "Développeur"), aucune
    compétence n'est dominante → on retourne None → aucun plafonnement arbitraire.

    Le sémantique (BGE-M3) ne sert qu'à DÉPARTAGER si plusieurs compétences
    requises sont nommées dans le titre — jamais à INVENTER une compétence absente
    du titre.
    """
    from rapidfuzz import fuzz as _rfuzz

    if not offer_title or not offer_skills:
        return None

    title_norm  = _normalize_accents(offer_title.lower())
    title_words = title_norm.split()
    clean_skills = [s for s in offer_skills if s and len(s.strip()) >= 2]
    if not clean_skills:
        return None

    _STOP = {"de", "des", "du", "la", "le", "les", "et", "en", "aux",
             "of", "and", "the", "pour", "sur", "avec"}

    def _word_in_title(sw: str) -> bool:
        """Un mot-compétence est présent dans le titre (exact, racine, ou fuzzy)."""
        for tw in title_words:
            if len(tw) < 3:
                continue
            if tw == sw:
                return True
            # Racine commune : "controle"/"controleur", "compta"/"comptable"
            if len(sw) >= 5 and tw.startswith(sw[:5]):
                return True
            if len(tw) >= 5 and sw.startswith(tw[:5]):
                return True
            if _rfuzz.ratio(tw, sw) >= 82:
                return True
        return False

    # ── Compétences réellement NOMMÉES dans le titre (signal fiable) ──────────
    literal_matches: List[str] = []
    for skill in clean_skills:
        s_norm = _normalize_accents(skill.lower().strip())
        # Correspondance substring directe ("python" dans "developpeur python")
        if len(s_norm) >= 3 and s_norm in title_norm:
            literal_matches.append(skill)
            continue
        # Correspondance par mots significatifs : TOUS les mots distinctifs de la
        # compétence doivent figurer dans le titre (gère "Contrôle de gestion"
        # nommé par "Contrôleur de Gestion", sans inventer "HTML" pour "Web Full Stack").
        sig_words = [w for w in s_norm.split() if len(w) >= 4 and w not in _STOP]
        if sig_words and all(_word_in_title(w) for w in sig_words):
            literal_matches.append(skill)

    # Titre générique : aucune compétence nommée → pas de compétence centrale
    # fiable → on n'invente rien, pas de plafonnement.
    if not literal_matches:
        return None

    if len(literal_matches) == 1:
        return _normalize_accents(literal_matches[0].lower())

    # Plusieurs compétences nommées → départage sémantique (la plus proche du titre)
    if encode_fn is not None:
        try:
            title_emb = encode_fn(offer_title)
            best_skill, best_sim = literal_matches[0], -1.0
            for skill in literal_matches:
                sim = _cosine(title_emb, encode_fn(skill))
                if sim > best_sim:
                    best_sim, best_skill = sim, skill
            return _normalize_accents(best_skill.lower())
        except Exception:
            pass

    return _normalize_accents(literal_matches[0].lower())

def _candidate_has_skill(skill_canonical: str, cv_skills: List[str]) -> bool:
    """
    Vérifie si le candidat possède la compétence centrale.
    Utilise correspondance exacte, fuzzy et expansion de synonymes.
    """
    if not skill_canonical or not cv_skills:
        return False

    from rapidfuzz import fuzz as _rfuzz
    skill_norm = _normalize_accents(skill_canonical.lower())

    for s in cv_skills:
        s_norm = _normalize_accents(s.lower())
        # Match exact ou partiel
        if skill_norm in s_norm or s_norm in skill_norm:
            return True
        # Match fuzzy
        if _rfuzz.token_set_ratio(skill_norm, s_norm) >= 85:
            return True
        # Expansion synonymes
        if skill_norm in _TECH_EXPANSION.get(s_norm, frozenset()):
            return True
        if s_norm in _TECH_EXPANSION.get(skill_norm, frozenset()):
            return True

    return False


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
    _MODELS_ROOT, "fusion_mlp", "fusion_mlp.pt"
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
    """MLP 7 features → score [0,1] — architecture v2."""
    def __init__(self):
        if _TORCH_AVAILABLE:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(7, 64),  nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
                nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
                nn.Linear(32, 1),  nn.Sigmoid(),
            )
            self.n_features = 7

    def forward(self, x):
        return self.net(x).squeeze(-1)


class _ScoringMLPv3(nn.Module if _TORCH_AVAILABLE else object):
    """MLP 9 features → score [0,1] — architecture v3 (domaine exp + formation)."""
    def __init__(self):
        if _TORCH_AVAILABLE:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(9, 64),  nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
                nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
                nn.Linear(32, 1),  nn.Sigmoid(),
            )
            self.n_features = 9

    def forward(self, x):
        return self.net(x).squeeze(-1)


class _ScoringMLPv3b1(nn.Module if _TORCH_AVAILABLE else object):
    """MLP 10 features -> score [0,1] — architecture B1 (titre_skill, crit_ratio, offer_type)."""
    def __init__(self):
        if _TORCH_AVAILABLE:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(10, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
                nn.Linear(64, 32), nn.ReLU(),           nn.Dropout(0.10),
                nn.Linear(32, 1),  nn.Sigmoid(),
            )
            self.n_features = 10

    def forward(self, x):
        return self.net(x).squeeze(-1)


class BERTMatchingScorer:
    def __init__(self, model_name: str = _EMBEDDER_MODEL):
        self._st_model   = None    # SentenceTransformer (bi-encoder)
        self._reranker   = None    # CrossEncoder (joint scorer)
        self._mlp         = None    # FusionMLP (v2=7D, v3=9D)
        self._mlp_version = 0       # 0=absent, 2=7feat, 3=9feat
        self._load_attempted = False
        self._reranker_load_attempted = False
        self.ready       = False
        self.reranker_ready = False
        self.load_error: Optional[str] = None
        self.reranker_load_error: Optional[str] = None
        self._model_path = model_name   # chemin/nom réel pour charger le transformer
        self.model_name  = model_name   # nom d'affichage (peut être surchargé)
        self.model_version = model_name
        self.reranker_model_name = _RERANKER_MODEL

    def _ensure_loaded(self) -> bool:
        if self.ready or self._load_attempted:
            return self.ready
        self._load_attempted = True

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            # Utilise _model_path (chemin réel) et non model_name (qui peut être
            # un nom d'affichage surchargé après la construction).
            self._st_model = SentenceTransformer(self._model_path)
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
            # Priorite : v3b1 (10D) > v3 (9D) > v2 (7D)
            mlp_v3b1_path = mlp_path.replace("fusion_mlp.pt", "fusion_mlp_v3b1.pt")
            mlp_v3_path   = mlp_path.replace("fusion_mlp.pt", "fusion_mlp_v3.pt")
            if os.path.exists(mlp_v3b1_path):
                mlp = _ScoringMLPv3b1()
                mlp.load_state_dict(torch.load(mlp_v3b1_path, map_location="cpu", weights_only=True))
                mlp.eval()
                self._mlp = mlp
                self._mlp_version = 4   # v3b1 = version 4 (10 features)
                print(f"[MLP] v3b1 (10D) charge depuis {mlp_v3b1_path}")
            elif os.path.exists(mlp_v3_path):
                mlp = _ScoringMLPv3()
                mlp.load_state_dict(torch.load(mlp_v3_path, map_location="cpu", weights_only=True))
                mlp.eval()
                self._mlp = mlp
                self._mlp_version = 3
            elif os.path.exists(mlp_path):
                mlp = _ScoringMLP()
                mlp.load_state_dict(torch.load(mlp_path, map_location="cpu", weights_only=True))
                mlp.eval()
                self._mlp = mlp
                self._mlp_version = 2
            else:
                self._mlp = None
                self._mlp_version = 0
        except Exception as _e:
            print(f"[MLP] Chargement echoue : {_e}")
            self._mlp = None
            self._mlp_version = 0

    def _encode(self, texts: List[str]) -> np.ndarray:
        """Encode des textes en vecteurs normalisés via SentenceTransformer."""
        if self._st_model is None:
            return np.zeros((len(texts), _EMBEDDER_DIM))
        return self._st_model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True
        )

    def _calibrated_score(
        self,
        sem_sim: float,
        skill_rate: float,
        exp_score: float,
        formation_score: float,
        domain_compat_key: str = "unknown",
        w_skills: float = 0.40,
        w_sem:    float = 0.25,
        w_exp:    float = 0.20,
        w_form:   float = 0.15,
    ) -> float:
        """Score calibré : formule pondérée × domain_multiplier multiplicatif.

        Poids dynamiques selon type d'offre (Phase 3) :
          Tech spécialisé : skills 55% / sem 20% / exp 15% / form 10%
          Senior 5+ ans   : skills 40% / sem 20% / exp 30% / form 10%
          Stage/Junior    : skills 45% / sem 25% / exp  5% / form 25%
          Management/RH   : skills 35% / sem 25% / exp 25% / form 15%

        domain_multiplier (multiplicatif) :
          same × 1.00 · adjacent × 0.70 · same_major × 0.40 · different × 0.15
        """
        _DOMAIN_MULT = {
            "same":       1.00,
            "adjacent":   0.70,
            "same_major": 0.50,   # domaines du même secteur (RH↔Finance) : moins pénalisé
            "different":  0.15,
            "unknown":    1.00,
        }
        base = (
            w_skills * skill_rate
          + w_sem    * sem_sim
          + w_exp    * exp_score
          + w_form   * formation_score
        )
        mult = _DOMAIN_MULT.get(domain_compat_key, 0.85)
        return round(max(0.04, min(0.95, base * mult)), 4)


    @staticmethod
    def _compute_mlp_features(
        *,
        s_semantique: float,
        s_competences: float,
        s_experience: float,
        s_formation: float,
        sem_v2: float,
        edu_domain_compat: float,
        exp_domain_ratio: float,
        title_skill_match: float,
        crit_skill_ratio: float,
        offer_type_encoded: float,
    ) -> "List[float]":
        """Vecteur 10D pour le MLP.
        Methode unique : inference ET generation dataset (zero train/prod gap).

        1. s_semantique       — similarite BGE-M3
        2. s_competences      — skills ponderees criticite (Phase 2)
        3. s_experience       — score experience
        4. s_formation        — score formation + domaine (A3)
        5. sem_v2             — cross-encoder (ou proxy BGE-M3)
        6. edu_domain_compat  — compatibilite domaine etudes
        7. exp_domain_ratio   — ratio experience dans le domaine
        8. title_skill_match  — 1.0 si skill titre presente, 0.0 sinon (Phase 1)
        9. crit_skill_ratio   — ratio skills critiques matchees (Phase 2)
       10. offer_type_encoded — 0.0=junior / 0.25=mgmt / 0.5=tech / 1.0=senior
        """
        return [
            float(s_semantique),
            float(s_competences),
            float(s_experience),
            float(s_formation),
            float(sem_v2),
            float(edu_domain_compat),
            float(exp_domain_ratio),
            float(title_skill_match),
            float(crit_skill_ratio),
            float(offer_type_encoded),
        ]

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

    def _compute_domain_relevant_years(
        self,
        cv_experiences: List[Dict],
        offer_skills: List[str],
        offer_text: str,
    ) -> Tuple[float, float]:
        """
        Calcule les années d'expérience pertinentes par rapport au domaine de l'offre.

        Pour chaque expérience du CV :
          - Calcule le chevauchement de compétences avec l'offre (via _TECH_EXPANSION)
          - Calcule la similarité sémantique BGE avec le texte de l'offre
          - Si l'expérience est "dans le domaine" → compte ses années à plein poids
          - Si l'expérience est hors-domaine → compte à 20%

        Retourne (domain_relevant_years, total_years).
        """
        if not cv_experiences or not isinstance(cv_experiences, list):
            return 0.0, 0.0

        offer_norms = {_normalize_skill(s) for s in offer_skills}
        offer_expanded: set[str] = set()
        for s in offer_norms:
            offer_expanded.add(s)
            offer_expanded.update(_TECH_EXPANSION.get(s, frozenset()))

        domain_years = 0.0
        total_years  = 0.0

        for exp in cv_experiences:
            if not isinstance(exp, dict):
                continue

            # Durée de cette expérience
            duration = 0.0
            raw_dur  = exp.get("duree_mois") or exp.get("duration_months") or 0
            try:
                duration = float(raw_dur) / 12.0
            except (TypeError, ValueError):
                duration = 0.0
            if duration <= 0:
                duration = 1.0  # durée inconnue : on estime 1 an

            total_years += duration

            # Texte de cette expérience
            exp_parts: List[str] = []
            for key in ("poste", "title", "entreprise", "company", "description"):
                val = exp.get(key)
                if isinstance(val, str) and val.strip():
                    exp_parts.append(val.strip())
            missions = exp.get("missions") or []
            if isinstance(missions, list):
                exp_parts += [m for m in missions if isinstance(m, str) and m.strip()]
            exp_text = " ".join(exp_parts).lower()

            if not exp_text.strip():
                # Pas de texte → expérience neutre, on compte 50%
                domain_years += duration * 0.5
                continue

            # Compétences mentionnées dans cette expérience
            exp_norms = set()
            for word in _re.split(r"[\s,;/]+", exp_text):
                w = _normalize_skill(word)
                if len(w) >= 3:
                    exp_norms.add(w)
                    exp_norms.update(_TECH_EXPANSION.get(w, frozenset()))

            # Chevauchement avec l'offre
            overlap = len(offer_expanded & exp_norms)
            overlap_ratio = overlap / max(len(offer_expanded), 1)

            # Similarité sémantique BGE entre cette expérience et l'offre
            # On utilise le cosinus brut (pas normalisé) : domaines différents → cosine 0.1-0.3
            # La normalisation (sim+1)/2 masquerait la différence de domaine
            bge_raw = 0.0
            if offer_text and exp_text and self._ensure_loaded():
                try:
                    embs = self._encode([
                        _clip_words(offer_text, 128),
                        _clip_words(exp_text, 128),
                    ])
                    bge_raw = float(_cosine(
                        np.asarray(embs[0], dtype=float),
                        np.asarray(embs[1], dtype=float),
                    ))
                    bge_raw = max(0.0, min(1.0, bge_raw))  # cosinus brut clamped [0,1]
                except Exception:
                    bge_raw = 0.0

            # Score de pertinence : skill overlap domine (80%), BGE complète (20%)
            # overlap_ratio est plus fiable pour distinguer les domaines
            relevance = overlap_ratio * 0.80 + bge_raw * 0.20

            # Seuils de pertinence → poids
            if overlap_ratio >= 0.25 or relevance >= 0.40:
                weight = 1.00   # expérience clairement dans le domaine
            elif overlap_ratio >= 0.10 or relevance >= 0.20:
                weight = 0.55   # domaine adjacent / partiellement pertinent
            elif overlap_ratio >= 0.03 or relevance >= 0.10:
                weight = 0.20   # domaine éloigné
            else:
                weight = 0.05   # hors-domaine complet

            domain_years += duration * weight

        return round(domain_years, 2), round(total_years, 2)

    def _skill_credibility(
        self,
        skill: str,
        exp_text_lower: str,
    ) -> float:
        """
        Retourne le facteur de crédibilité d'un skill (0.6 à 1.0).

        1.0 → skill présente dans les descriptions d'expériences (crédible)
        0.6 → skill uniquement déclarée en section compétences, absente des expériences
        0.8 → skill trouvée via expansion/synonyme dans les expériences
        """
        if not exp_text_lower:
            return 0.8  # pas d'expériences → on ne peut pas vérifier, légère précaution

        s_norm = _normalize_skill(skill)
        s_low  = skill.lower()

        # Présence directe
        if s_low in exp_text_lower or s_norm in exp_text_lower:
            return 1.0

        # Présence via expansion (synonymes)
        for equiv in _TECH_EXPANSION.get(s_norm, frozenset()):
            if equiv in exp_text_lower:
                return 0.8

        return 0.6  # skill non trouvée dans les expériences

    def score_experience(
        self,
        cv_years: float,
        required_years: float,
        offer_text: str = "",
        cv_experience_text: str = "",
        cv_experiences: Optional[List[Dict]] = None,
        offer_skills: Optional[List[str]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Dimension 2 — Expérience (20% du score final).

        Formule v2 (semaine 2) :
          40% années pertinentes (dans le bon domaine)
          30% années totales (base)
          30% similarité sémantique BGE

        Exemples :
            Offre finance, CV 3 ans finance                → ~0.95
            Offre finance, CV 3 ans IT                     → ~0.35
            Offre développeur, CV 3 ans dev Python + 2 mktg→ ~0.85
            Requis 0 ans                                   → 1.00
        """
        detail: Dict[str, Any] = {}

        if not required_years or required_years <= 0:
            detail["note"] = "no_experience_required"
            return 1.0, detail

        # ── Composante 1 : années pertinentes dans le domaine ────────────────
        domain_years, total_years_parsed = 0.0, cv_years
        if cv_experiences and offer_skills:
            domain_years, total_years_parsed = self._compute_domain_relevant_years(
                cv_experiences, offer_skills, offer_text
            )
            detail["domain_relevant_years"] = domain_years
            detail["total_years_parsed"]    = total_years_parsed
        else:
            domain_years = cv_years

        domain_ratio = min(1.0, max(0.0, domain_years / required_years))
        total_ratio  = min(1.0, max(0.0, cv_years     / required_years))

        # ── Composante 2 : similarité sémantique (domaine global) ────────────
        if offer_text and cv_experience_text:
            sem_sim, _ = self.score_semantic(offer_text, cv_experience_text)
        else:
            sem_sim = (domain_ratio + total_ratio) / 2.0

        # ── Score final ───────────────────────────────────────────────────────
        score = domain_ratio * 0.40 + total_ratio * 0.30 + sem_sim * 0.30
        detail.update({
            "domain_ratio": round(domain_ratio, 3),
            "total_ratio":  round(total_ratio, 3),
            "sem_sim":      round(sem_sim, 3),
            "required_years": required_years,
        })
        return round(max(0.0, min(1.0, score)), 4), detail

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
        w_comp = 0.50
        w_exp  = 0.20
        w_form = 0.15
        w_sem  = 0.15

        required_years      = profile["required_years"]
        offer_skills_count  = profile["offer_skills_count"]

        # ── 1. Adapter selon le type de poste ────────────────────
        if profile["is_stage"] or profile["is_alternance"]:
            # Étudiant : exp quasi nulle, formation importante, skills + sémantique
            w_exp  = 0.03
            w_comp = 0.50
            w_form = 0.25
            w_sem  = 0.22

        elif profile["is_junior"] or required_years == 0:
            # Junior : peu d'exp attendue
            w_exp  = 0.06
            w_comp = 0.55
            w_form = 0.15
            w_sem  = 0.24

        elif profile["is_senior"] or required_years >= 5:
            # Senior : expérience très importante
            w_exp  = 0.33
            w_comp = 0.42
            w_form = 0.13
            w_sem  = 0.12

        elif required_years >= 3:
            # Confirmé
            w_exp  = 0.25
            w_comp = 0.48
            w_form = 0.14
            w_sem  = 0.13

        else:
            # Débutant / 1-2 ans
            w_exp  = 0.12
            w_comp = 0.53
            w_form = 0.15
            w_sem  = 0.20

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
        desc_blob      = _normalize_offer_text(((offer.description or "") + "\n" + (offer.titre or "")).strip())
        required_years = (
            int(offer.experience_requise)
            if getattr(offer, 'experience_requise', None) is not None
            else (_extract_required_years(desc_blob) or 0)
        )
        _stored_edu    = getattr(offer, 'formation_requise_niveau', None)
        required_edu   = int(_stored_edu) if _stored_edu is not None else (_extract_required_education_level(desc_blob) or 0)
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
        # Si le texte d'expérience est trop pauvre (poste non extrait), on enrichit avec
        # les skills déclarés du candidat — ils reflètent son domaine de compétences réel.
        if len(cv_experience_text.split()) < 8:
            cv_experience_text = (_clip_words(" ".join(cv_skills[:25]), 80) + " " + cv_experience_text).strip()

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

        # ── Phase 2 : Pondération skills par criticité ──────────────────────
        # Critique (titre du poste) × 3 / Requise (métier) × 2 / Générique × 1
        # On calcule _title_skill ici pour réutiliser dans Phase 1 (cap) ET Phase 2 (poids)
        _title_skill_early = _extract_title_skill(
            offer.titre or "", offer_skills, encode_fn=self._encode
        )
        _title_norm_early = _normalize_skill(_title_skill_early) if _title_skill_early else ""

        # Outils universels transversaux — poids 1 car peu discriminants entre candidats
        _GENERIC_TOOLS = frozenset({
            "git", "github", "gitlab", "svn",
            "excel", "word", "powerpoint", "office", "libreoffice", "outlook",
            "teams", "slack", "zoom", "skype",
            "jira", "confluence", "trello", "notion", "asana",
            "windows", "linux", "macos",
        })

        def _skill_weight_and_crit(skill: str):
            s_n = _normalize_skill(skill)
            if _title_norm_early and s_n == _title_norm_early:
                return 3.0, "critique"
            if s_n in _GENERIC_TOOLS or any(s_n.startswith(g) for g in _GENERIC_TOOLS):
                return 1.0, "generique"
            return 2.0, "requise"

        _skills_criticality: Dict[str, str] = {}
        total_weight = sum(_skill_weight_and_crit(s)[0] for s in offer_skills) if offer_skills else 1.0

        skills_matched: List[Dict[str, str]] = []
        skills_missing: List[str] = []
        total_comp = 0.0

        # Texte des expériences pour le calcul de crédibilité des skills
        _exp_text_lower = " ".join(exp_parts).lower() if exp_parts else ""

        for skill in offer_skills:
            norm = _normalize_skill(skill)
            credibility = 1.0   # sera ajusté si skill non backée par expériences
            # 1) Match exact après normalisation alias
            if norm in cv_norms:
                credibility = self._skill_credibility(skill, _exp_text_lower)
                _w2a, _crit2a = _skill_weight_and_crit(skill)
                _skills_criticality[skill] = _crit2a
                skills_matched.append({"skill": skill, "source": "extrait",
                                       "credibility": round(credibility, 2), "criticite": _crit2a})
                total_comp += _w2a * 1.0 * credibility
                continue
            # 2) Fuzzy match sur les skills parsés (filtrés — sans les niés)
            best_fz = max(
                (fuzz.token_set_ratio(norm, _normalize_skill(s)) for s in cv_skills_filtered),
                default=0,
            )
            if best_fz >= 80:
                credibility = self._skill_credibility(skill, _exp_text_lower)
                _w2b, _crit2b = _skill_weight_and_crit(skill)
                _skills_criticality[skill] = _crit2b
                skills_matched.append({"skill": skill, "source": "fuzzy",
                                       "credibility": round(credibility, 2), "criticite": _crit2b})
                total_comp += _w2b * 1.0 * credibility
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
                credibility = self._skill_credibility(skill, _exp_text_lower)
                _w2c, _crit2c = _skill_weight_and_crit(skill)
                _skills_criticality[skill] = _crit2c
                skills_matched.append({"skill": skill, "source": "ecosystem",
                                       "credibility": round(credibility, 2), "criticite": _crit2c})
                total_comp += _w2c * 0.9 * credibility
                continue

            # 3) Fallback texte brut — uniquement si la mention n'est pas niée.
            skill_lower = skill.lower()
            idx = raw_lower.find(norm) if norm in raw_lower else (
                raw_lower.find(skill_lower) if skill_lower in raw_lower else -1
            )
            if idx != -1:
                context_before = raw_lower[max(0, idx - 60):idx]
                if not any(neg in context_before for neg in _NEGATIONS_CTX):
                    credibility = self._skill_credibility(skill, _exp_text_lower)
                    _w2d, _crit2d = _skill_weight_and_crit(skill)
                    _skills_criticality[skill] = _crit2d
                    skills_matched.append({"skill": skill, "source": "texte_brut",
                                           "credibility": round(credibility, 2), "criticite": _crit2d})
                    total_comp += _w2d * 0.7 * credibility
                    continue
            skills_missing.append(skill)

        # B1 feature #9 : ratio skills critiques matchees
        _crit_skills_offer   = [s for s in offer_skills
                                 if _skills_criticality.get(s, "requise") == "critique"]
        _matched_skill_names = {m["skill"] for m in skills_matched if isinstance(m, dict)}
        _crit_matched_count  = sum(1 for s in _crit_skills_offer if s in _matched_skill_names)
        _crit_skill_ratio    = (round(_crit_matched_count / len(_crit_skills_offer), 4)
                                if _crit_skills_offer else 1.0)

        s_fuzzy_v2    = round(min(1.0, total_comp / max(1.0, total_weight)), 4) if offer_skills else 0.5
        s_bert_skills, _ = self.score_skills_bert(offer_skills, cv_skills_filtered)
        _bert_bonus   = max(0.0, s_bert_skills - s_fuzzy_v2) * 0.20
        s_competences = round(min(1.0, s_fuzzy_v2 + _bert_bonus), 4)
        # Expérience : pertinence domaine + ratio années + sémantique
        cv_experiences_list = (parsed_for_exp.get("experiences") or [])
        s_experience, _exp_detail = self.score_experience(
            cand_years, required_years, offer_text, cv_experience_text,
            cv_experiences=cv_experiences_list, offer_skills=offer_skills,
        )
        s_formation   = self.score_formation(cand_edu, required_edu)

        # ── Prestige institution de formation ────────────────────────────────
        _prestige = _institution_prestige_score(parsed_for_exp)
        # 70% niveau diplôme + 30% prestige institution (ajustement modéré)
        s_formation = round(s_formation * (0.70 + 0.30 * _prestige), 4)

        # Formation domaine — Bac+5 Informatique ≠ Bac+5 Droit pour un poste dev
        # Couche 1 : mots-clés domaine (rapide, précis)
        # Couche 2 : BGE cosinus brut (signal sémantique fin)
        if required_edu > 0:
            _edu_texts: List[str] = []
            _specialites: List[str] = []
            _parsed_edu = parsed_for_exp.get("formations") or parsed_for_exp.get("education") or []
            if isinstance(_parsed_edu, list):
                for _edu in _parsed_edu:
                    if isinstance(_edu, dict):
                        _sp = _edu.get("specialite") or _edu.get("domaine") or _edu.get("field")
                        if isinstance(_sp, str) and _sp.strip():
                            _specialites.append(_sp.strip())
                        for _key in ("diplome", "etablissement", "specialite",
                                     "degree", "school", "titre", "field"):
                            _val = _edu.get(_key)
                            if isinstance(_val, str) and _val.strip():
                                _edu_texts.append(_val.strip())

            # Couche 1 : compatibilité via mots-clés domaine
            _cand_domain_text = " ".join(_specialites) if _specialites else " ".join(_edu_texts)
            _offer_domain_text = (offer_text or "") + " " + " ".join(offer_skills)
            _cand_edu_domain  = _detect_edu_domain(_cand_domain_text)
            _offer_edu_domain = _detect_edu_domain(_offer_domain_text)
            _kw_compat = _edu_domain_compatibility(_cand_edu_domain, _offer_edu_domain)

            # Couche 2 : BGE cosinus brut entre spécialité et offre
            _bge_edu_sim = 0.5
            if _edu_texts and offer_text and self._ensure_loaded():
                try:
                    _embs_edu = self._encode([
                        _clip_words(offer_text, 128),
                        _clip_words(" ".join(_edu_texts), 64),
                    ])
                    _raw_cos = float(_cosine(
                        np.asarray(_embs_edu[0], dtype=float),
                        np.asarray(_embs_edu[1], dtype=float),
                    ))
                    _bge_edu_sim = max(0.0, min(1.0, _raw_cos))  # cosinus brut
                except Exception:
                    _bge_edu_sim = 0.5

            # Score domaine formation : 65% mots-clés + 35% BGE brut
            _edu_domain_score = _kw_compat * 0.65 + _bge_edu_sim * 0.35

            # Sauvegarder pour le details dict
            self._last_edu_domain_cand  = _cand_edu_domain
            self._last_edu_domain_offer = _offer_edu_domain
            self._last_edu_kw_compat    = round(_kw_compat, 2)

            # Intégration : 65% niveau diplôme + 35% domaine d'études
            s_formation = round(s_formation * 0.65 + _edu_domain_score * 0.35, 4)

        s_semantique  = self.score_semantique(offer_text, cv_text)

        # ── Poids dynamiques selon le profil de l'offre ─────────
        offer_profile = self._analyze_offer_profile(offer, required_years, required_edu, len(offer_skills))
        W = self._dynamic_weights(offer_profile)

        # Fix 5 — Expérience pénalisée si compétences très faibles.
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
        # La pénalité par inco est inversement proportionnelle à la taille de l'offre :
        # une offre avec 16 skills requis génère naturellement plus d'alertes niv.2
        # qu'une offre simple → on normalise pour éviter de pénaliser tous les candidats.
        n_checked = max(5, len(skills_to_check) if skills_to_check else 5)
        _scale = min(1.0, 5.0 / n_checked)   # 5 skills → ×1.0 / 10 skills → ×0.50 / 16 → ×0.31
        inco_penalty = 0.0
        has_fake_expert = False
        for _inc in inconsistencies:
            _lvl = int(_inc.get("level", 0))
            # niv.2 (absent des expériences) retiré des pénalités : trop de faux positifs
            # car les CVs listent les skills en section dédiée, pas dans chaque expérience.
            if _lvl == 4:
                inco_penalty += 0.08   # BERT contexte trop faible
            elif _lvl == 5:
                inco_penalty += 0.15   # faux expert détecté
                has_fake_expert = True
        inco_penalty = min(inco_penalty, 0.15)   # cap global −15%
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
        # Priorité au champ explicite niveau_seniorite si renseigné dans l'offre
        _niveau_explicite = getattr(offer, "niveau_seniorite", None) or ""
        _SENIORITY_MAP = {
            "stage": 1, "alternance": 1, "junior": 2,
            "confirmé": 3, "confirme": 3, "senior": 4, "expert": 5,
        }
        if _niveau_explicite and _niveau_explicite.lower() in _SENIORITY_MAP:
            _offer_senior_level = _SENIORITY_MAP[_niveau_explicite.lower()]
        else:
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

        # ── Compatibilité de domaine professionnel (ESCO universel) ────────
        _offer_domain, _offer_role_level = _detect_offer_domain(offer)
        _domain_penalty_exp = 0.0
        _compat_key = "unknown"   # "same"|"adjacent"|"same_major"|"different"|"unknown"

        if _offer_domain and _cand_domain:
            _esco = EscoService.get()
            _compat_key = _esco.get_compatibility(
                _cand_domain["isco_code"], _offer_domain["isco_code"]
            )
            # Pénalité expérience si niveau de rôle très inférieur
            if _compat_key in ("same", "adjacent") and _cand_role_level > 0 and _offer_role_level > 0:
                _lvl_diff = _offer_role_level - _cand_role_level
                if _lvl_diff >= 2:
                    _domain_penalty_exp = 0.15
                elif _lvl_diff == 1:
                    _domain_penalty_exp = 0.07

        if _domain_penalty_exp > 0:
            s_experience = round(max(0.0, s_experience - _domain_penalty_exp), 4)

        # B1 features #8 #10 : title_skill_match + offer_type_encoded
        _ote_dom_str = str((_offer_domain or {}).get("label", "") or "").lower()
        _ote_is_mgmt = any(k in _ote_dom_str for k in (
            "management", "ressources humaines", "direction", "rh",
            "finance", "comptabil", "juridique", "droit", "vente",
            "commercial", "marketing", "logistique", "achat",
        )) or any(k in (offer.titre or "").lower() for k in (
            "rh", "ressources humaines", "drh", "people",
            "comptable", "finance", "juriste", "avocat", "commercial",
        ))
        _ote_sen_str = (getattr(offer, "niveau_seniorite", None) or "").lower()
        if _ote_sen_str in ("stage", "alternance", "junior") or _offer_senior_level <= 2:
            _offer_type_encoded = 0.0
        elif _offer_senior_level >= 4 and (required_years or 0) >= 5:
            _offer_type_encoded = 1.0
        elif _ote_is_mgmt:
            _offer_type_encoded = 0.25
        else:
            _offer_type_encoded = 0.5

        _edu_dom_compat_feat = float(getattr(self, "_last_edu_kw_compat", 0.8))

        _dom_yrs_b1, _tot_yrs_b1 = self._compute_domain_relevant_years(
            cv_experiences_list if cv_experiences_list else [],
            offer_skills, offer_text,
        )
        _exp_dom_ratio_b1 = round(_dom_yrs_b1 / max(_tot_yrs_b1, 0.5), 4) if _tot_yrs_b1 > 0 else 0.5

        # ── Phase 1 : compétence centrale obligatoire ───────────────────
        # Réutilise _title_skill_early calculé avant la boucle (Phase 2)
        _title_skill      = _title_skill_early
        _has_title_skill  = _candidate_has_skill(_title_skill, cv_skills) if _title_skill else True
        _title_skill_cap  = not _has_title_skill

        # ── Score MLP (si disponible) ────────────────────────────────────
        # Calcule les features pour le MLP et fusionne avec la formule calibrée
        _mlp_score = None
        if self._mlp is not None and _TORCH_AVAILABLE:
            try:
                import torch as _torch
                # Features communes (v2 et v3)
                _edu_gap_feat = max(-1.0, min(1.0, (required_edu - cand_edu) / 5.0))
                _skills_raw_feat = len(set(
                    _normalize_skill(s) for s in offer_skills
                ) & set(
                    _normalize_skill(s) for s in cv_skills
                )) / max(len(offer_skills), 1)

                if getattr(self, "_mlp_version", 2) in (3, 4):
                    # 9 features v3
                    _cand_edu_dom = _detect_edu_domain(
                        " ".join(f.get("specialite", "") for f in
                                 (parsed_for_exp.get("formations") or []) if isinstance(f, dict))
                    )
                    _offer_edu_dom = _detect_edu_domain(offer_text)
                    _edu_dom_feat = _edu_domain_compatibility(_cand_edu_dom, _offer_edu_dom)
                    _dom_years, _tot_years = self._compute_domain_relevant_years(
                        cv_experiences_list, offer_skills, offer_text
                    )
                    _exp_dom_feat = round(_dom_years / max(_tot_years, 0.5), 4) if _tot_years > 0 else 0.5
                    feat = self._compute_mlp_features(
                        s_semantique       = float(s_semantique),
                        s_competences      = float(s_competences),
                        s_experience       = float(s_experience),
                        s_formation        = float(s_formation),
                        sem_v2             = float(s_semantique),
                        edu_domain_compat  = _edu_dom_compat_feat,
                        exp_domain_ratio   = _exp_dom_ratio_b1,
                        title_skill_match  = 1.0 if _has_title_skill else 0.0,
                        crit_skill_ratio   = _crit_skill_ratio,
                        offer_type_encoded = _offer_type_encoded,
                    )
                else:
                    # 7 features v2
                    feat = self._compute_mlp_features(
                        s_semantique       = float(s_semantique),
                        s_competences      = float(s_competences),
                        s_experience       = float(s_experience),
                        s_formation        = float(s_formation),
                        sem_v2             = float(s_semantique),
                        edu_domain_compat  = _edu_dom_compat_feat,
                        exp_domain_ratio   = _exp_dom_ratio_b1,
                        title_skill_match  = 1.0 if _has_title_skill else 0.0,
                        crit_skill_ratio   = _crit_skill_ratio,
                        offer_type_encoded = _offer_type_encoded,
                    )[:7]

                with _torch.no_grad():
                    x = _torch.tensor([feat], dtype=_torch.float32)
                    self._mlp.eval()
                    _mlp_score = float(self._mlp(x).item())
            except Exception:
                _mlp_score = None

        # ── Phase 3 : Recalibration poids selon type d'offre ─────────────
        _offer_domain_str = str((_offer_domain or {}).get("label", "") or "").lower()
        _is_mgmt = any(k in _offer_domain_str for k in (
            "management", "ressources humaines", "direction", "rh",
            "finance", "comptabil", "juridique", "droit", "vente", "commercial",
            "marketing", "logistique", "achat",
        ))
        _is_mgmt = _is_mgmt or any(k in (offer.titre or "").lower() for k in (
            "rh", "ressources humaines", "drh", "people",
            "comptable", "finance", "juriste", "avocat", "commercial", "logistic",
        ))

        _sen_str = (getattr(offer, "niveau_seniorite", None) or "").lower()
        if _sen_str in ("stage", "alternance", "junior") or _offer_senior_level <= 2:
            _offer_type    = "junior"
            _w_sk, _w_se, _w_ex, _w_fo = 0.45, 0.25, 0.05, 0.25
            _recommend_thr = 65   # seuil décision en %
        elif _offer_senior_level >= 4 and (required_years or 0) >= 5:
            _offer_type    = "senior"
            _w_sk, _w_se, _w_ex, _w_fo = 0.40, 0.20, 0.30, 0.10
            _recommend_thr = 70
        elif _is_mgmt:
            _offer_type    = "management"
            _w_sk, _w_se, _w_ex, _w_fo = 0.35, 0.25, 0.25, 0.15
            _recommend_thr = 68
        else:
            _offer_type    = "tech"
            _w_sk, _w_se, _w_ex, _w_fo = 0.55, 0.20, 0.15, 0.10
            _recommend_thr = 68

        # ── Score final — formule calibrée × domain_multiplier ──────────
        score_final = self._calibrated_score(
            sem_sim           = float(s_semantique),
            skill_rate        = float(s_competences),
            exp_score         = float(s_experience),
            formation_score   = float(s_formation),
            domain_compat_key = _compat_key,
            w_skills          = _w_sk,
            w_sem             = _w_se,
            w_exp             = _w_ex,
            w_form            = _w_fo,
        )

        # MLP influence : 70% si v3b1 (10D valide), 10% sinon
        # On fait davantage confiance au modele appris (v3b1) qu'a la formule fixe :
        # la formule junior (form=25%) gonfle les profils diplomes sans competences,
        # le MLP (entraine skills=55%) corrige ce biais.
        if _mlp_score is not None:
            _mlp_weight = 0.70 if self._mlp_version == 4 else 0.10
            score_final = round(_mlp_score * _mlp_weight + score_final * (1.0 - _mlp_weight), 4)

        # Bonus compétences appréciées (+12% max)
        if appreciated_skills:
            _apr_bonus = apr_rate * 0.12
            score_final = round(min(0.95, score_final + _apr_bonus), 4)

        # ── Phase 1 : cap compétence centrale manquante ─────────────────
        # Appliqué uniquement si domaine identique (same/unknown) :
        # Pour domaines adjacents/différents, le domain_multiplier suffit.
        # Exemple : RH candidat pour Finance → domain_mult réduit déjà le score.
        # Exemple : Java dev pour Python role → même domaine IT → cap sévère.
        if _title_skill_cap and _compat_key in ("same", "unknown"):
            score_final = round(score_final * 0.50, 4)

        # ── Cap "zéro skills + domaine incompatible" ─────────────────────
        # Si le candidat n'a AUCUNE skill requise ET est dans un domaine totalement
        # différent, l'expérience/formation ne doivent pas compenser.
        # Ex: Dev Python 5 ans pour Finance → 0 skills, domaine=different → plafonné.
        if s_competences <= 0.05 and _compat_key == "different":
            score_final = round(min(score_final, 0.12), 4)

        # ── Pénalités incohérences (CV incohérent = signal fraude) ──
        score_final = round(max(0.05, score_final - inco_penalty), 4)
        if has_fake_expert:
            score_final = min(score_final, 0.45)

        # Clip final — le MLP décide du score, pas de règles heuristiques
        score_final = round(max(0.05, min(0.95, score_final)), 4)

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
        # niv.2 retiré de la confiance — faux positif systématique :
        # les CVs listent les skills en section dédiée, pas dans chaque poste.
        if _has_l5:
            _confidence = {"niveau": "BASSE",   "message": "Vérification humaine fortement recommandée"}
        elif _has_l4:
            _confidence = {"niveau": "MOYENNE", "message": "Quelques incohérences détectées"}
        else:
            _confidence = {"niveau": "HAUTE",   "message": "Profil cohérent — modèle confiant"}

        # ── Décision automatique ─────────────────────────────────
        _pct = score_final * 100
        _decision = (
            "Excellent candidat"                if _pct >= 75 else
            "Bon profil - Entretien recommandé" if _pct >= _recommend_thr else
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
                "competences": "40% (BGE-M3 skills)",
                "semantique":  "25% (BGE-M3 global)",
                "experience":  "20% (années expérience)",
                "formation":   "15% (niveau diplôme)",
            },
            "domain_compat": {
                "key":        _compat_key,
                "multiplier": {"same": 1.0, "adjacent": 0.70,
                               "same_major": 0.40, "different": 0.15,
                               "unknown": 0.85}.get(_compat_key, 0.85),
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
            "offer_type":         _offer_type,
            "weights_used":       {"skills": _w_sk, "semantique": _w_se, "experience": _w_ex, "formation": _w_fo},
            "institution_prestige": round(_prestige, 2),
            "implied_skills_added": _implied_skills,
            # ── Phase 1 & 2 : compétence centrale + criticité ─────
            "title_skill":         _title_skill,
            "title_skill_missing": _title_skill_cap,
            "skills_criticality":  _skills_criticality,
            # B1 : vecteur 10D pour dataset generation
            "mlp_features_10d": self._compute_mlp_features(
                s_semantique       = float(s_semantique),
                s_competences      = float(s_competences),
                s_experience       = float(s_experience),
                s_formation        = float(s_formation),
                sem_v2             = float(s_semantique),
                edu_domain_compat  = _edu_dom_compat_feat,
                exp_domain_ratio   = _exp_dom_ratio_b1,
                title_skill_match  = 1.0 if _has_title_skill else 0.0,
                crit_skill_ratio   = _crit_skill_ratio,
                offer_type_encoded = _offer_type_encoded,
            ),
            # ── Nouveaux signaux S2/S3 ─────────────────────────────
            # Expérience domaine (S2)
            "exp_domain_relevant_years": _exp_detail.get("domain_relevant_years"),
            "exp_total_years_parsed":    _exp_detail.get("total_years_parsed"),
            "exp_domain_ratio":          round(_exp_detail.get("domain_ratio", 0), 3)
                                         if _exp_detail.get("domain_ratio") is not None else None,
            # Formation domaine (S3)
            "edu_domain_cand":           getattr(self, "_last_edu_domain_cand", None),
            "edu_domain_offer":          getattr(self, "_last_edu_domain_offer", None),
            "edu_kw_compat":             getattr(self, "_last_edu_kw_compat", None),
            # MLP version utilisée
            "mlp_version":               self._mlp_version,
            # Compat backend/frontend
            "ready":               bool(self.ready),
            "model":               self.model_name,
            "scoring_method":      "calibrated_formula_v5",
            "bert_semantic":       round(s_semantique, 4),
            "bert_skills":         round(s_competences, 4),
        }

        return score_final, details