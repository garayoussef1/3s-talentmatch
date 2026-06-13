#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A1 — Construit data/skills/skills_aliases.json
Sources :
  1. data/esco/esco_skills_api.json  — labels FR → alias multilingues
  2. Dictionnaire IT curé inline      — React, Python, etc.
  3. Dictionnaire non-IT curé inline  — Finance, RH, Santé, Droit...

Format de sortie :
  { "skill_normalisee": ["alias1", "alias2", ...], ... }
  Bidirectionnel : alias → skill + skill → alias

Utilisation :
  python scripts/build_skills_aliases.py
"""

import json, os, re, unicodedata
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESCO_PATH   = os.path.join(BASE, "data", "esco", "esco_skills_api.json")
OUTPUT_PATH = os.path.join(BASE, "data", "skills", "skills_aliases.json")


# ─────────────────────────────────────────────────────────────────────────────
def normalize(text: str) -> str:
    """Minuscules + supprime accents + trim."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_plausible_alias(s: str) -> bool:
    """Garde les alias courts et sans caractères spéciaux non-latins."""
    if len(s) < 2 or len(s) > 60:
        return False
    # Exclure les alias qui semblent être ES/PT/IT (heuristique : trop de voyelles accentuées non-FR)
    non_fr_chars = re.findall(r"[ãõüöñàèìòùâêîôûäëïöü]", s.lower())
    if len(non_fr_chars) >= 3:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Dictionnaire IT curé — frameworks, langages, outils tech
# (bidirectionnel : chaque groupe = cluster de synonymes)
IT_CLUSTERS = [
    {"python", "python3", "python 3", "py"},
    {"javascript", "js", "ecmascript", "es6", "es2015"},
    {"typescript", "ts"},
    {"react", "reactjs", "react.js", "react js"},
    {"angular", "angularjs", "angular.js"},
    {"vue", "vuejs", "vue.js"},
    {"node", "nodejs", "node.js", "node js"},
    {"django", "django rest framework", "drf"},
    {"fastapi", "fast api"},
    {"spring", "spring boot", "spring framework"},
    {"laravel", "php laravel"},
    {"dotnet", ".net", "asp.net", "dot net", "c#"},
    {"flutter", "dart flutter"},
    {"android", "android studio", "android sdk"},
    {"ios", "swift", "swiftui", "xcode"},
    {"java", "java se", "java ee", "jakarta ee"},
    {"php", "php7", "php8"},
    {"ruby", "ruby on rails", "ror"},
    {"golang", "go", "go lang"},
    {"rust", "rust lang"},
    {"scala", "scala lang"},
    {"kotlin", "kotlin android"},
    {"machine learning", "ml", "apprentissage automatique", "deep learning", "dl"},
    {"data science", "data scientist", "science des donnees"},
    {"deep learning", "neural network", "reseau de neurones", "ia", "intelligence artificielle"},
    {"tensorflow", "tf", "keras"},
    {"pytorch", "torch"},
    {"scikit-learn", "sklearn", "scikit learn"},
    {"nlp", "natural language processing", "traitement langage naturel", "tal"},
    {"devops", "dev ops", "devsecops"},
    {"docker", "docker compose", "dockerize"},
    {"kubernetes", "k8s", "kube"},
    {"terraform", "terraform iac"},
    {"ansible", "ansible automation"},
    {"jenkins", "jenkins ci", "jenkins pipeline"},
    {"git", "github", "gitlab", "git versioning", "controle version"},
    {"sql", "sql server", "transact-sql", "t-sql"},
    {"postgresql", "postgres", "pg"},
    {"mysql", "mariadb"},
    {"mongodb", "mongo", "nosql mongodb"},
    {"redis", "cache redis"},
    {"elasticsearch", "elastic search", "elk"},
    {"rest api", "api rest", "restful", "restful api", "api restful"},
    {"graphql", "graph ql"},
    {"microservices", "micro services", "microservice architecture"},
    {"aws", "amazon web services", "amazon aws"},
    {"azure", "microsoft azure", "ms azure"},
    {"gcp", "google cloud", "google cloud platform"},
    {"ci/cd", "ci cd", "integration continue", "continuous integration", "continuous deployment"},
    {"linux", "unix", "debian", "ubuntu", "centos"},
    {"agile", "agilite", "methode agile"},
    {"scrum", "methode scrum", "scrum master"},
    {"jira", "jira software"},
    {"figma", "figma design"},
    {"cybersecurity", "cybersecurite", "securite informatique", "information security"},
    {"fullstack", "full stack", "full-stack", "developpeur fullstack"},
    {"backend", "back-end", "back end", "developpeur backend"},
    {"frontend", "front-end", "front end", "developpeur frontend"},
    {"data engineer", "ingenieur donnees", "ingenieur data"},
    {"data analyst", "analyste donnees", "analyste data"},
    {"business intelligence", "bi", "tableau", "power bi", "qlik"},
    {"spark", "apache spark", "pyspark"},
    {"hadoop", "hdfs", "hive"},
    {"etl", "pipeline donnees", "data pipeline"},
]

# ─────────────────────────────────────────────────────────────────────────────
# Dictionnaire non-IT curé — domaines Finance, RH, Santé, Droit, BTP...
NON_IT_CLUSTERS = [
    # Finance / Comptabilité
    {"comptabilite", "accounting", "bookkeeping", "comptabilite generale", "comptabilite financiere"},
    {"controle de gestion", "controlling", "management control", "gestion budgetaire", "budget control"},
    {"audit", "audit interne", "audit externe", "internal audit", "external audit"},
    {"tresorerie", "treasury", "cash management", "gestion tresorerie"},
    {"fiscalite", "tax", "taxation", "droit fiscal", "impots"},
    {"ifrs", "normes ifrs", "ias", "normes ias", "normes comptables"},
    {"sap fi", "sap fico", "sap finance", "sap co"},
    {"reporting financier", "financial reporting", "reporting", "tableaux de bord financiers"},
    {"analyse financiere", "financial analysis", "analyse financiere"},
    {"budget", "gestion budgetaire", "budgeting", "previsions budgetaires"},

    # RH / Recrutement
    {"recrutement", "recruitment", "recruiting", "recruiter", "hiring", "talent acquisition", "sourcing"},
    {"gestion ressources humaines", "rh", "human resources", "hr", "grh", "people management"},
    {"paie", "paies", "payroll", "gestion paie", "fiche paie", "compensation"},
    {"gpec", "gestion previsionnelle emplois competences", "workforce planning", "talent management", "gestion des talents"},
    {"droit du travail", "labour law", "labor law", "droit social", "relations sociales", "employment law"},
    {"formation professionnelle", "professional training", "gestion formation"},
    {"sirh", "hris", "logiciel rh", "workday", "successfactors"},
    {"evaluation performance", "performance management", "entretien annuel"},

    # Santé / Médical
    {"soins infirmiers", "nursing", "soins", "ide", "infirmier diplome etat"},
    {"pharmacologie", "pharmacy", "pharmacie", "medicaments"},
    {"medecine", "medicine", "medical", "clinique"},
    {"chirurgie", "surgery", "bloc operatoire"},
    {"kinesitherapie", "physiotherapy", "kine", "reeducation"},
    {"radiologie", "radiology", "imagerie medicale"},
    {"urgences", "emergency medicine", "soins urgence"},
    {"soins intensifs", "intensive care", "reanimation"},

    # Droit / Juridique
    {"droit", "law", "legal", "juridique"},
    {"droit des affaires", "business law", "droit commercial"},
    {"droit social", "labour law", "droit du travail"},
    {"contentieux", "litigation", "contentieux commercial"},
    {"contrats", "contracts", "droit des contrats"},
    {"conformite", "compliance", "rgpd", "gdpr"},
    {"propriete intellectuelle", "intellectual property", "ip law"},

    # Marketing / Communication
    {"marketing", "marketing strategy", "marketing strategique"},
    {"marketing digital", "digital marketing", "marketing en ligne"},
    {"seo", "referencement naturel", "search engine optimization"},
    {"sea", "referencement payant", "google ads", "sem"},
    {"community management", "community manager", "reseaux sociaux"},
    {"content marketing", "marketing contenu", "creation contenu"},
    {"crm", "salesforce", "hubspot", "gestion relation client"},
    {"communication", "communication corporate", "relations presse"},

    # Logistique / Supply Chain
    {"logistique", "logistics", "supply chain"},
    {"supply chain management", "scm", "gestion chaine approvisionnement"},
    {"achats", "procurement", "purchasing", "approvisionement"},
    {"transport", "gestion transport", "freight", "expeditions"},
    {"gestion stocks", "stock management", "inventory management", "entrepot"},
    {"lean", "lean management", "lean manufacturing", "amelioration continue"},

    # Genie Civil / BTP
    {"genie civil", "civil engineering", "travaux publics"},
    {"bim", "building information modeling", "maquette numerique"},
    {"conducteur travaux", "construction management", "supervision chantier"},
    {"architecture", "architectural design", "conception architecturale"},
    {"structure", "calcul structure", "structural engineering"},

    # Commerce / Vente
    {"vente", "sales", "commercial", "force de vente"},
    {"negociation", "negotiation", "techniques vente"},
    {"developpement commercial", "business development", "biz dev", "bizdev"},
    {"key account management", "gestion grands comptes", "kam", "grands comptes"},

    # Design
    {"ux design", "user experience", "ux", "experience utilisateur"},
    {"ui design", "user interface", "interface utilisateur"},
    {"figma", "sketch", "adobe xd", "prototypage"},
    {"photoshop", "adobe photoshop", "retouche photo"},
    {"illustrator", "adobe illustrator", "design graphique"},
]


# ─────────────────────────────────────────────────────────────────────────────
def build_aliases():
    aliases: dict[str, set] = defaultdict(set)

    def add_cluster(cluster: set):
        norms = {normalize(s) for s in cluster if s}
        for skill in norms:
            for alias in norms:
                if alias != skill:
                    aliases[skill].add(alias)

    # 1. Clusters IT
    for cluster in IT_CLUSTERS:
        add_cluster(cluster)

    # 2. Clusters non-IT
    for cluster in NON_IT_CLUSTERS:
        add_cluster(cluster)

    # 3. ESCO data — FR labels → EN aliases (bidirectionnel)
    if os.path.exists(ESCO_PATH):
        with open(ESCO_PATH, encoding="utf-8") as f:
            esco = json.load(f)

        for fr_label, alias_list in esco.items():
            fr_norm = normalize(fr_label)
            if len(fr_norm) < 3 or len(fr_norm) > 60:
                continue
            for alias in alias_list:
                a_norm = normalize(alias)
                if not is_plausible_alias(a_norm):
                    continue
                if len(a_norm) < 3:
                    continue
                # Filtre : éviter les faux positifs (alias trop différent du label FR)
                # Heuristique : si les deux ont ≥ 1 mot en commun → plausible
                fr_words = set(fr_norm.split())
                a_words  = set(a_norm.split())
                shared   = fr_words & a_words
                # Accepter si mot commun OU si alias court (≤ 2 mots = terme technique)
                if shared or len(a_words) <= 2:
                    aliases[fr_norm].add(a_norm)
                    aliases[a_norm].add(fr_norm)
        print(f"  ESCO : {len(esco)} entrées traitées")
    else:
        print(f"  ESCO introuvable : {ESCO_PATH}")

    # Sérialiser (set → list, trier)
    result = {k: sorted(v) for k, v in aliases.items() if v}
    return result


def main():
    print("Construction de skills_aliases.json...")
    result = build_aliases()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nFichier créé : {OUTPUT_PATH}")
    print(f"Total skills : {len(result)}")

    # Validation rapide
    checks = [
        ("python",           ["py", "python3"]),
        ("react",            ["reactjs", "react.js"]),
        ("comptabilite",     ["accounting"]),
        ("recrutement",      ["recruitment", "hiring"]),
        ("soins infirmiers", ["nursing", "ide"]),
        ("droit",            ["law", "legal"]),
        ("marketing",        ["marketing strategy"]),
        ("controle de gestion", ["controlling", "management control"]),
    ]
    print("\n=== Validation ===")
    ok = 0
    for skill, expected_aliases in checks:
        found = result.get(skill, [])
        hits = [e for e in expected_aliases if e in found]
        status = "OK" if hits else "FAIL"
        if status == "OK":
            ok += 1
        print(f"  [{status}] {skill:30s} -> {found[:4]}")
    print(f"\n{ok}/{len(checks)} validations OK")


if __name__ == "__main__":
    main()
