#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test end-to-end du matching sur des profils réalistes.
Vérifie que le système donne des scores logiques :
  - Bon profil pour la bonne offre  → score élevé
  - Profil hors-domaine             → score faible
  - Profil partiel                  → score moyen
"""
import os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "backend"))

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer

scorer = BERTMatchingScorer()
scorer._ensure_loaded()

# ── Mock objects ──────────────────────────────────────────────────────────────
class Offer:
    def __init__(self, titre, desc, skills, exp=2, edu=3, domaine=""):
        self.titre = titre; self.description = desc
        self.competences_requises = skills; self.competences_appreciees = []
        self.experience_requise = exp; self.formation_requise_niveau = edu
        self.domaine_metier = domaine; self.niveau_seniorite = ""
        self.type_contrat = "CDI"; self.localisation = None; self.status = "active"
        self.raw_text = desc + " " + " ".join(skills)

class Cand:
    def __init__(self, nom, raw, skills, exp=2, edu=3, exps=None, fmts=None):
        self.nom = nom; self.raw_text = raw; self.email = "x@x.com"; self.cv_id = None
        self.parsed_data = {
            "competences": skills,
            "experiences": exps or [{"poste": nom, "description": raw,
                                      "duree_mois": int(exp*12)}],
            "formations":  fmts or [],
            # niveau_formation_max requis par _candidate_education_level()
            "metadata":    {"annees_experience_totales": exp,
                            "niveau_formation_max": edu},
        }

# ═══════════════════════════════════════════════════════════════════════════════
# OFFRES
# ═══════════════════════════════════════════════════════════════════════════════
O_DEV = Offer(
    "Développeur Python FastAPI",
    "CDI développeur Python FastAPI PostgreSQL Docker REST API microservices Bac+5 3 ans",
    ["Python","FastAPI","PostgreSQL","Docker","Git","REST API"], exp=3, edu=5
)
O_FINANCE = Offer(
    "Contrôleur de Gestion",
    "CDI contrôle de gestion comptabilité Excel SAP reporting financier bilan IFRS Bac+5 3 ans",
    ["Comptabilité","Excel","SAP","Contrôle de gestion","Reporting financier","IFRS"], exp=3, edu=5
)
O_RH = Offer(
    "Chargé RH Recrutement",
    "CDI recrutement sourcing LinkedIn RH paie droit du travail GPEC entretien Bac+3 2 ans",
    ["Recrutement","RH","LinkedIn","Paie","GPEC","Droit du travail"], exp=2, edu=3
)
O_INFIRMIER = Offer(
    "Infirmier IDE Soins Intensifs",
    "CDI infirmier IDE soins intensifs réanimation urgences bloc opératoire Bac+3 2 ans",
    ["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences"], exp=2, edu=3
)

# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATS
# ═══════════════════════════════════════════════════════════════════════════════
C_DEV = Cand(
    "Développeur Python Senior",
    "Développeur Python 4 ans FastAPI Django PostgreSQL Docker Redis Git REST API microservices CI/CD Bac+5",
    ["Python","FastAPI","Django","PostgreSQL","Docker","Git","REST API","Redis"], exp=4, edu=5,
    exps=[{"poste":"Dev Python","description":"Python FastAPI PostgreSQL Docker REST API CI/CD","duree_mois":48}],
    fmts=[{"diplome":"Master","specialite":"Génie Logiciel","niveau_bac_plus":5}]
)
C_COMPTABLE = Cand(
    "Comptable Contrôleur de Gestion",
    "Comptable 4 ans SAP FI/CO Excel IFRS reporting financier bilan contrôle gestion audit trésorerie Bac+5",
    ["Comptabilité","SAP","Excel","IFRS","Reporting financier","Contrôle de gestion","Audit","Trésorerie"], exp=4, edu=5,
    exps=[{"poste":"Comptable","description":"comptabilité SAP Excel IFRS reporting bilan contrôle gestion","duree_mois":48}],
    fmts=[{"diplome":"Master","specialite":"Finance Comptabilité","niveau_bac_plus":5}]
)
C_RH = Cand(
    "Chargée RH",
    "RH 3 ans recrutement sourcing LinkedIn paie GPEC droit travail entretien SIRH ATS Bac+3",
    ["RH","Recrutement","LinkedIn","Paie","GPEC","Droit du travail","Entretien annuel","SIRH"], exp=3, edu=3,
    exps=[{"poste":"Chargée RH","description":"recrutement sourcing paie GPEC droit travail RH","duree_mois":36}],
    fmts=[{"diplome":"Licence","specialite":"Ressources Humaines","niveau_bac_plus":3}]
)
C_INFIRMIER = Cand(
    "Infirmier IDE",
    "Infirmier IDE 3 ans soins intensifs réanimation urgences bloc opératoire ECG monitoring Bac+3",
    ["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences","ECG","Bloc opératoire"], exp=3, edu=3,
    exps=[{"poste":"Infirmier IDE","description":"soins infirmiers réanimation urgences bloc opératoire","duree_mois":36}],
    fmts=[{"diplome":"BTS","specialite":"Soins Infirmiers","niveau_bac_plus":3}]
)
# ── D2 — 6 cas multi-domaine ─────────────────────────────────────────────────

# D2-1 : Finance expert vs Finance (bon match, valide A2 non-IT)
C_FINANCE_EXPERT = Cand(
    "Expert Finance IFRS",
    "Expert finance 6 ans IFRS SAP FICO reporting financier contrôle gestion analyse financière trésorerie bilan fiscalité Bac+5",
    ["IFRS","SAP FI","Reporting financier","Contrôle de gestion","Analyse financière","Trésorerie","Fiscalité"], exp=6, edu=5,
    exps=[{"poste":"Analyste Finance Senior","description":"IFRS SAP FICO reporting contrôle gestion analyse financière trésorerie","duree_mois":72}],
    fmts=[{"diplome":"Master","specialite":"Finance","niveau_bac_plus":5}]
)

# D2-2 : Médecin vs offre Dev Python (cap ISCO, domaine totalement différent)
C_MEDECIN_POUR_DEV = Cand(
    "Médecin Généraliste (postule Dev)",
    "Médecin généraliste 5 ans consultation diagnostic pharmacologie soins urgences Bac+8",
    ["Médecine","Pharmacologie","Soins d'urgence","Réanimation","Diagnostic"], exp=5, edu=8,
    exps=[{"poste":"Médecin","description":"médecine générale consultation pharmacologie soins urgences","duree_mois":60}],
    fmts=[{"diplome":"Doctorat","specialite":"Médecine","niveau_bac_plus":8}]
)

# D2-3 : RH avec synonymes EN (valide skills_aliases.json A1)
C_RH_SYNONYMES = Cand(
    "HR Manager (profil EN)",
    "HR Manager 4 years talent management recruiting human resources payroll workforce planning labour law HRIS Bac+5",
    ["talent management","recruiting","human resources","payroll","workforce planning","labour law","HRIS"], exp=4, edu=5,
    exps=[{"poste":"HR Manager","description":"talent management recruiting payroll workforce planning HRIS","duree_mois":48}],
    fmts=[{"diplome":"Master","specialite":"Human Resources","niveau_bac_plus":5}]
)

# D2-4 : Comptable junior vs offre Finance Senior (skills OK, exp insuffisante)
O_FINANCE_SENIOR = Offer(
    "Contrôleur de Gestion Senior",
    "Senior contrôle de gestion 8 ans comptabilité SAP IFRS reporting financier management équipe Bac+5",
    ["Contrôle de gestion","Comptabilité","SAP","IFRS","Reporting financier","Analyse financière"], exp=8, edu=5
)
C_COMPTABLE_JUNIOR = Cand(
    "Comptable Junior 1an",
    "Comptable débutant 1 an SAP comptabilité générale Excel IFRS reporting Bac+5",
    ["Comptabilité","SAP","Excel","IFRS","Reporting financier"], exp=1, edu=5,
    exps=[{"poste":"Comptable Junior","description":"comptabilité SAP Excel IFRS reporting","duree_mois":12}],
    fmts=[{"diplome":"Master","specialite":"Finance Comptabilité","niveau_bac_plus":5}]
)

# D2-5 : Dev Fullstack vs offre Data Scientist (IT adjacent, spécialisation différente)
O_DATA_SCIENTIST = Offer(
    "Data Scientist Machine Learning",
    "CDI data scientist machine learning Python TensorFlow scikit-learn NLP Pandas SQL Bac+5 3 ans",
    ["Machine Learning","Python","TensorFlow","scikit-learn","Pandas","SQL","NLP"], exp=3, edu=5
)
C_DEV_FULLSTACK = Cand(
    "Dev Fullstack Python/React",
    "Développeur fullstack 4 ans Python React Node.js PostgreSQL Docker REST API JavaScript Bac+5",
    ["Python","React","Node.js","PostgreSQL","Docker","REST API","JavaScript","Git"], exp=4, edu=5,
    exps=[{"poste":"Dev Fullstack","description":"Python React Node.js PostgreSQL Docker REST API fullstack","duree_mois":48}],
    fmts=[{"diplome":"Master","specialite":"Informatique","niveau_bac_plus":5}]
)

# D2-6 : CV multilingue FR+EN vs offre FR (valide robustesse)
C_DEV_MULTILINGUE = Cand(
    "Dev Python (CV FR+EN)",
    "Python developer 4 years experience en FastAPI développement web REST APIs databases PostgreSQL Docker microservices CI/CD Git Bac+5",
    ["Python","FastAPI","PostgreSQL","Docker","REST API","Git","CI/CD"], exp=4, edu=5,
    exps=[{"poste":"Python developer","description":"Python FastAPI REST APIs PostgreSQL Docker microservices","duree_mois":48}],
    fmts=[{"diplome":"Master","specialite":"Software Engineering","niveau_bac_plus":5}]
)

# Profils hors-domaine
C_DEV_POUR_FINANCE = Cand(
    "Dev Python (postule Finance)",
    "Développeur Python 4 ans FastAPI PostgreSQL Docker Git REST API Bac+5",
    ["Python","FastAPI","PostgreSQL","Docker","Git","REST API"], exp=4, edu=5,
    exps=[{"poste":"Dev Python","description":"Python FastAPI PostgreSQL Docker REST API","duree_mois":48}],
    fmts=[{"diplome":"Master","specialite":"Informatique","niveau_bac_plus":5}]
)
C_COMPTABLE_POUR_DEV = Cand(
    "Comptable (postule Dev Python)",
    "Comptable 4 ans SAP Excel comptabilité IFRS bilan audit reporting Bac+5",
    ["Comptabilité","SAP","Excel","IFRS","Audit","Reporting financier"], exp=4, edu=5,
    exps=[{"poste":"Comptable","description":"comptabilité SAP Excel IFRS bilan audit","duree_mois":48}],
    fmts=[{"diplome":"Master","specialite":"Finance Comptabilité","niveau_bac_plus":5}]
)
C_INFIRMIER_POUR_DEV = Cand(
    "Infirmier (postule Dev Python)",
    "Infirmier IDE 3 ans soins intensifs réanimation urgences Bac+3",
    ["Soins infirmiers","IDE","Réanimation","Urgences"], exp=3, edu=3,
    exps=[{"poste":"Infirmier","description":"soins infirmiers réanimation urgences","duree_mois":36}],
    fmts=[{"diplome":"BTS","specialite":"Soins Infirmiers","niveau_bac_plus":3}]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════
TESTS = [
    # (offre, candidat, score_attendu_min, score_attendu_max, label)
    (O_DEV,       C_DEV,                0.70, 1.00, "BON MATCH    — Dev→Dev"),
    (O_FINANCE,   C_COMPTABLE,          0.70, 1.00, "BON MATCH    — Finance→Finance"),
    (O_RH,        C_RH,                 0.65, 1.00, "BON MATCH    — RH→RH"),
    (O_INFIRMIER, C_INFIRMIER,          0.65, 1.00, "BON MATCH    — Infirmier→Infirmier"),
    (O_DEV,       C_COMPTABLE_POUR_DEV, 0.00, 0.35, "MAUVAIS MATCH— Comptable→Dev"),
    (O_FINANCE,   C_DEV_POUR_FINANCE,   0.00, 0.35, "MAUVAIS MATCH— Dev→Finance"),
    (O_DEV,       C_INFIRMIER_POUR_DEV, 0.00, 0.25, "MAUVAIS MATCH— Infirmier→Dev"),
    (O_FINANCE,   C_RH,                 0.15, 0.50, "PARTIEL      — RH→Finance (adjacent)"),
    (O_RH,        C_COMPTABLE,          0.10, 0.50, "PARTIEL      — Finance→RH (adjacent)"),
    # ── D2 — 6 cas multi-domaine ────────────────────────────────────────────
    (O_FINANCE,        C_FINANCE_EXPERT,   0.65, 1.00, "D2-1 BON     — Finance expert vs Finance"),
    (O_DEV,            C_MEDECIN_POUR_DEV, 0.00, 0.20, "D2-2 MAUVAIS — Médecin vs Dev (cap ISCO)"),
    (O_RH,             C_RH_SYNONYMES,     0.50, 1.00, "D2-3 BON     — RH synonymes EN (skills_aliases)"),
    (O_FINANCE_SENIOR, C_COMPTABLE_JUNIOR, 0.15, 0.55, "D2-4 PARTIEL — Comptable junior vs Senior"),
    (O_DATA_SCIENTIST, C_DEV_FULLSTACK,    0.20, 0.55, "D2-5 PARTIEL — Dev Fullstack vs Data Scientist"),
    (O_DEV,            C_DEV_MULTILINGUE,  0.55, 1.00, "D2-6 BON     — CV multilingue FR+EN vs offre FR"),
]

print("=" * 72)
print("  Test matching end-to-end — profils réalistes")
print("=" * 72)

passed = failed = 0
for offer, cand, min_s, max_s, label in TESTS:
    score, details = scorer.score(offer, cand)
    pct = score * 100
    in_range = min_s <= score <= max_s
    icon = "✓" if in_range else "✗"
    status = "OK" if in_range else "FAIL"

    comp = details.get("competences", 0)
    exp  = details.get("experience",  0)
    form = details.get("formation",   0)
    sem  = details.get("semantique",  0)

    print(f"\n  [{icon}] {label}")
    print(f"       Score: {pct:.1f}%  (attendu {min_s*100:.0f}–{max_s*100:.0f}%)  [{status}]")
    print(f"       Skills:{comp:.0f}%  Exp:{exp:.0f}%  Form:{form:.0f}%  Sem:{sem:.0f}%")

    if in_range: passed += 1
    else:        failed += 1

print(f"\n{'='*72}")
pct_pass = passed / len(TESTS) * 100
print(f"  RÉSULTAT : {passed}/{len(TESTS)} tests OK ({pct_pass:.0f}%)")
n_orig = 9; n_d2 = 6
print(f"  (dont {n_orig} cas originaux + {n_d2} cas D2 multi-domaine)")
if failed == 0:
    print("  Le modele donne des scores logiques sur tous les cas !")
else:
    print(f"  {failed} cas ont un score hors de la plage attendue.")
print("=" * 72)
