"""
generate_mlp_dataset_v3.py
==========================
Dataset MLP Fusion v3 — 9 features + labels intelligents multi-domaine.

Nouveautés vs v2 :
  - Candidats enrichis : experiences avec duree_mois + domaine, formations avec specialite
  - 2 nouvelles features : edu_domain_compat + exp_domain_ratio
  - Plus de candidats hors-domaine pour forcer la discrimination
  - Couvre : IT, Finance, RH, Marketing, Médical, Logistique, Droit, BTP

Architecture MLP cible : 9 -> 64 -> 32 -> 1
"""
from __future__ import annotations
import sys, os, csv
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",   "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from app.services.matching_sandbox.bert_scorer import (
    BERTMatchingScorer, _detect_edu_domain, _edu_domain_compatibility
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR   = REPO_ROOT / "data" / "mlp_training_fusion"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV   = OUT_DIR / "dataset_fusion_v3.csv"


# ── Mock objects ──────────────────────────────────────────────────────────────
class _MockOffer:
    def __init__(self, d: dict):
        self.titre                  = d["titre"]
        self.description            = d["description"]
        self.competences_requises   = d["skills"]
        self.competences_appreciees = d.get("skills_apr", [])
        self.experience_requise     = d["exp_requise"]
        self.formation_requise_niveau = d.get("edu_requise", 0)
        self.domaine_metier         = d.get("domaine", "")
        self.raw_text               = d["description"] + " " + " ".join(d["skills"])
        self.localisation           = d.get("localisation", None)
        self.type_contrat           = d.get("type_contrat", "CDI")
        self.status                 = "active"


class _MockCandidate:
    def __init__(self, d: dict):
        self.nom      = d["nom"]
        self.email    = d["nom"].lower().replace(" ", "_") + "@test.com"
        self.raw_text = d["cv_text"]
        self.cv_id    = None
        self.parsed_data = {
            "competences": d["skills"],
            "experiences": d.get("experiences", [
                {"poste": d["nom"], "description": d["cv_text"], "duree_mois": int(d.get("exp_years", 1) * 12)}
            ]),
            "formations":  d.get("formations", []),
            "metadata":    {"annees_experience_totales": d.get("exp_years", 0)},
        }


def skill_overlap(offer_skills, cand_skills):
    if not offer_skills or not cand_skills:
        return 0.0
    o = {s.lower() for s in offer_skills}
    c = {s.lower() for s in cand_skills}
    return round(len(o & c) / max(len(o), 1), 4)


def compute_label(offre: dict, cand: dict) -> float:
    """Label intelligent avec pénalités domaine et formation."""
    s_skills = skill_overlap(offre["skills"], cand["skills"])
    req_exp  = offre["exp_requise"]
    s_exp    = 1.0 if req_exp <= 0 else min(1.0, cand.get("exp_years", 0) / max(req_exp, 1))
    req_edu  = offre.get("edu_requise", 0)
    cand_edu = cand.get("edu_level", 0)
    s_edu    = 1.0 if req_edu <= 0 else min(1.0, cand_edu / max(req_edu, 1))

    base = s_skills * 0.50 + s_exp * 0.28 + s_edu * 0.22

    # Pénalité domaine skills
    if s_skills < 0.10:   base *= 0.10
    elif s_skills < 0.20: base *= 0.28
    elif s_skills < 0.35: base *= 0.58

    # Pénalité formation manquante
    edu_gap = req_edu - cand_edu
    if edu_gap >= 3:   base *= 0.55
    elif edu_gap >= 2: base *= 0.72
    elif edu_gap >= 1: base *= 0.88

    # Pénalité domaine d'expérience (nouveauté v3)
    offer_domain = offre.get("domaine", "")
    cand_domain  = cand.get("domaine", "")
    if offer_domain and cand_domain and offer_domain != cand_domain:
        cand_edu_domain = _detect_edu_domain(cand_domain)
        offer_edu_domain = _detect_edu_domain(offer_domain)
        compat = _edu_domain_compatibility(cand_edu_domain, offer_edu_domain)
        base *= compat  # 0.45 si complètement hors-domaine

    return round(max(0.02, min(0.95, base)), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# OFFRES — multi-domaine
# ═══════════════════════════════════════════════════════════════════════════════
OFFRES = [
    # ── IT / Développement ──────────────────────────────────────────────────
    {"titre": "Développeur Python FastAPI", "domaine": "informatique",
     "description": "CDI Python FastAPI PostgreSQL Docker Git REST API Bac+5 3 ans",
     "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "REST API"],
     "exp_requise": 3, "edu_requise": 5},
    {"titre": "Développeur React Frontend", "domaine": "informatique",
     "description": "CDI React JavaScript TypeScript HTML CSS Git REST API Bac+3 2 ans",
     "skills": ["React", "JavaScript", "TypeScript", "HTML", "CSS", "Git"],
     "exp_requise": 2, "edu_requise": 3},
    {"titre": "Data Scientist Python ML", "domaine": "informatique",
     "description": "CDI Python Machine Learning scikit-learn TensorFlow SQL Docker Bac+5 3 ans",
     "skills": ["Python", "Machine Learning", "scikit-learn", "TensorFlow", "SQL", "Docker"],
     "exp_requise": 3, "edu_requise": 5},
    {"titre": "DevOps Engineer Cloud", "domaine": "informatique",
     "description": "CDI Docker Kubernetes AWS Terraform CI/CD Linux Ansible Bac+5 4 ans",
     "skills": ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD", "Linux", "Git"],
     "exp_requise": 4, "edu_requise": 5},
    {"titre": "Développeur Java Spring Boot", "domaine": "informatique",
     "description": "CDI Java Spring Boot MySQL Maven REST API Docker Git Bac+5 3 ans",
     "skills": ["Java", "Spring Boot", "MySQL", "Docker", "Git", "REST API", "Maven"],
     "exp_requise": 3, "edu_requise": 5},
    {"titre": "Cybersécurité Analyste", "domaine": "informatique",
     "description": "CDI cybersécurité SIEM pentest réseau Linux Python Bac+5 3 ans",
     "skills": ["Cybersécurité", "Linux", "Python", "SIEM", "Réseau", "Git"],
     "exp_requise": 3, "edu_requise": 5},
    # ── Finance / Comptabilité ───────────────────────────────────────────────
    {"titre": "Comptable Contrôleur de Gestion", "domaine": "finance",
     "description": "CDI comptabilité contrôle de gestion Excel SAP reporting bilan Bac+5 3 ans",
     "skills": ["Comptabilité", "Excel", "SAP", "Contrôle de gestion", "Reporting", "Budget"],
     "exp_requise": 3, "edu_requise": 5},
    {"titre": "Auditeur Financier", "domaine": "finance",
     "description": "CDI audit financier comptabilité Excel normes IFRS analyse financière Bac+5 2 ans",
     "skills": ["Audit", "Comptabilité", "Excel", "IFRS", "Analyse financière"],
     "exp_requise": 2, "edu_requise": 5},
    {"titre": "Analyste Financier Junior", "domaine": "finance",
     "description": "CDI finance reporting Excel Power BI budget prévisions Bac+3 1 an",
     "skills": ["Finance", "Excel", "Power BI", "Reporting", "Budget"],
     "exp_requise": 1, "edu_requise": 3},
    {"titre": "Responsable Trésorerie", "domaine": "finance",
     "description": "CDI trésorerie gestion liquidités SWIFT Excel SAP banque 5 ans Bac+5",
     "skills": ["Trésorerie", "Excel", "SAP", "Finance", "Comptabilité"],
     "exp_requise": 5, "edu_requise": 5},
    # ── RH / Recrutement ────────────────────────────────────────────────────
    {"titre": "Chargé RH Recrutement", "domaine": "rh",
     "description": "CDI recrutement sourcing LinkedIn RH entretiens ATS paie Bac+3 2 ans",
     "skills": ["Recrutement", "RH", "LinkedIn", "Sourcing", "Excel", "Communication"],
     "exp_requise": 2, "edu_requise": 3},
    {"titre": "DRH Responsable RH", "domaine": "rh",
     "description": "CDI gestion RH droit du travail paie formation GPEC management Bac+5 5 ans",
     "skills": ["RH", "Droit du travail", "Paie", "Formation", "GPEC", "Management"],
     "exp_requise": 5, "edu_requise": 5},
    # ── Marketing / Communication ────────────────────────────────────────────
    {"titre": "Responsable Marketing Digital", "domaine": "marketing",
     "description": "CDI SEO Google Ads Facebook réseaux sociaux analytics email marketing Bac+3 2 ans",
     "skills": ["SEO", "Google Ads", "Facebook Ads", "Google Analytics", "Community Management"],
     "exp_requise": 2, "edu_requise": 3},
    {"titre": "Chef de Projet Communication", "domaine": "marketing",
     "description": "CDI communication branding événementiel relations presse rédaction Bac+5 3 ans",
     "skills": ["Communication", "Branding", "Relations presse", "Rédaction", "Excel"],
     "exp_requise": 3, "edu_requise": 5},
    # ── Logistique / Supply Chain ────────────────────────────────────────────
    {"titre": "Responsable Logistique Supply Chain", "domaine": "logistique",
     "description": "CDI logistique supply chain achats WMS transport Excel SAP Bac+5 4 ans",
     "skills": ["Logistique", "Supply Chain", "Achats", "WMS", "Excel", "SAP"],
     "exp_requise": 4, "edu_requise": 5},
    {"titre": "Acheteur Approvisionneur", "domaine": "logistique",
     "description": "CDI achats approvisionnement fournisseurs négociation SAP Excel Bac+3 2 ans",
     "skills": ["Achats", "Approvisionnement", "Négociation", "SAP", "Excel"],
     "exp_requise": 2, "edu_requise": 3},
    # ── Médical / Santé ──────────────────────────────────────────────────────
    {"titre": "Infirmier Soins Intensifs", "domaine": "medecine",
     "description": "CDI soins infirmiers IDE bloc opératoire urgences réanimation Bac+3",
     "skills": ["Soins infirmiers", "IDE", "Urgences", "Réanimation", "Bloc opératoire"],
     "exp_requise": 2, "edu_requise": 3},
    {"titre": "Pharmacien Officine", "domaine": "medecine",
     "description": "CDI pharmacologie médicaments conseils patients gestion stock ordonnances Bac+5",
     "skills": ["Pharmacologie", "Médicaments", "Conseil patient", "Gestion stock"],
     "exp_requise": 1, "edu_requise": 5},
    # ── Droit / Juridique ────────────────────────────────────────────────────
    {"titre": "Juriste Droit des Affaires", "domaine": "droit",
     "description": "CDI droit des contrats droit commercial propriété intellectuelle RGPD Bac+5 3 ans",
     "skills": ["Droit des contrats", "Droit commercial", "RGPD", "Contrats", "Négociation"],
     "exp_requise": 3, "edu_requise": 5},
    # ── BTP / Génie Civil ────────────────────────────────────────────────────
    {"titre": "Ingénieur Génie Civil BTP", "domaine": "btp",
     "description": "CDI génie civil béton structures AutoCAD chantier topographie Bac+5 3 ans",
     "skills": ["Génie civil", "Béton", "AutoCAD", "Gestion chantier", "Topographie"],
     "exp_requise": 3, "edu_requise": 5},
]

# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATS — enrichis avec expériences structurées + formations + domaine
# ═══════════════════════════════════════════════════════════════════════════════
CANDIDATS = [
    # ── IT ───────────────────────────────────────────────────────────────────
    {"nom": "Dev Python Senior", "domaine": "informatique",
     "cv_text": "Développeur Python FastAPI Django PostgreSQL Docker Git REST API 4 ans Bac+5",
     "skills": ["Python", "FastAPI", "Django", "PostgreSQL", "Docker", "Git", "REST API"],
     "exp_years": 4, "edu_level": 5,
     "experiences": [{"poste": "Développeur Python", "description": "Python FastAPI PostgreSQL Docker REST API CI/CD", "duree_mois": 36},
                     {"poste": "Dev Junior Python", "description": "Python Django MySQL Git", "duree_mois": 12}],
     "formations": [{"diplome": "Master", "specialite": "Génie Logiciel", "niveau_bac_plus": 5}]},

    {"nom": "Dev React Junior", "domaine": "informatique",
     "cv_text": "Développeur React JavaScript TypeScript HTML CSS Git REST API 1 an Bac+3",
     "skills": ["React", "JavaScript", "TypeScript", "HTML", "CSS", "Git"],
     "exp_years": 1, "edu_level": 3,
     "experiences": [{"poste": "Dev Frontend React", "description": "React TypeScript JavaScript HTML CSS REST API", "duree_mois": 12}],
     "formations": [{"diplome": "Licence", "specialite": "Informatique", "niveau_bac_plus": 3}]},

    {"nom": "Data Scientist ML", "domaine": "informatique",
     "cv_text": "Data scientist Python TensorFlow scikit-learn Pandas SQL Docker 3 ans Bac+5",
     "skills": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "SQL", "Docker"],
     "exp_years": 3, "edu_level": 5,
     "experiences": [{"poste": "Data Scientist", "description": "Python machine learning scikit-learn TensorFlow SQL Docker Pandas", "duree_mois": 36}],
     "formations": [{"diplome": "Master", "specialite": "Intelligence Artificielle", "niveau_bac_plus": 5}]},

    {"nom": "DevOps AWS Senior", "domaine": "informatique",
     "cv_text": "DevOps AWS Docker Kubernetes Terraform CI/CD Linux 5 ans Bac+5",
     "skills": ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux", "Git"],
     "exp_years": 5, "edu_level": 5,
     "experiences": [{"poste": "DevOps Engineer", "description": "AWS Docker Kubernetes Terraform CI/CD Linux Ansible monitoring", "duree_mois": 60}],
     "formations": [{"diplome": "Master", "specialite": "Systèmes et Réseaux", "niveau_bac_plus": 5}]},

    {"nom": "Dev Java Spring", "domaine": "informatique",
     "cv_text": "Développeur Java Spring Boot MySQL Docker REST API Maven 4 ans Bac+5",
     "skills": ["Java", "Spring Boot", "MySQL", "Docker", "REST API", "Maven", "Git"],
     "exp_years": 4, "edu_level": 5,
     "experiences": [{"poste": "Développeur Java", "description": "Java Spring Boot MySQL Docker REST API Maven microservices", "duree_mois": 48}],
     "formations": [{"diplome": "Ingénieur", "specialite": "Informatique", "niveau_bac_plus": 5}]},

    # ── Finance ──────────────────────────────────────────────────────────────
    {"nom": "Comptable Senior", "domaine": "finance",
     "cv_text": "Comptable SAP Excel reporting financier bilan contrôle gestion 4 ans Bac+5",
     "skills": ["Comptabilité", "SAP", "Excel", "Reporting", "Contrôle de gestion", "Budget"],
     "exp_years": 4, "edu_level": 5,
     "experiences": [{"poste": "Comptable senior", "description": "comptabilité SAP Excel reporting financier bilan budget contrôle de gestion", "duree_mois": 48}],
     "formations": [{"diplome": "Master", "specialite": "Finance Comptabilité", "niveau_bac_plus": 5}]},

    {"nom": "Auditeur Junior", "domaine": "finance",
     "cv_text": "Auditeur audit financier Excel IFRS comptabilité analyse 2 ans Bac+5",
     "skills": ["Audit", "Excel", "IFRS", "Comptabilité", "Analyse financière"],
     "exp_years": 2, "edu_level": 5,
     "experiences": [{"poste": "Auditeur", "description": "audit financier IFRS comptabilité Excel analyse financière", "duree_mois": 24}],
     "formations": [{"diplome": "Master", "specialite": "Audit Finance", "niveau_bac_plus": 5}]},

    {"nom": "Analyste Financier", "domaine": "finance",
     "cv_text": "Analyste financier Excel Power BI reporting budget prévisions 2 ans Bac+3",
     "skills": ["Finance", "Excel", "Power BI", "Reporting", "Budget"],
     "exp_years": 2, "edu_level": 3,
     "experiences": [{"poste": "Analyste financier", "description": "finance Excel Power BI reporting budget trésorerie", "duree_mois": 24}],
     "formations": [{"diplome": "Licence", "specialite": "Gestion Finance", "niveau_bac_plus": 3}]},

    # ── RH ───────────────────────────────────────────────────────────────────
    {"nom": "Chargée RH", "domaine": "rh",
     "cv_text": "RH recrutement sourcing LinkedIn entretiens paie ATS Excel 3 ans Bac+3",
     "skills": ["RH", "Recrutement", "Sourcing", "LinkedIn", "Paie", "Excel", "Communication"],
     "exp_years": 3, "edu_level": 3,
     "experiences": [{"poste": "Chargée RH", "description": "recrutement sourcing LinkedIn entretiens paie gestion administrative RH ATS", "duree_mois": 36}],
     "formations": [{"diplome": "Licence", "specialite": "Ressources Humaines", "niveau_bac_plus": 3}]},

    {"nom": "DRH Expérimenté", "domaine": "rh",
     "cv_text": "DRH gestion RH droit du travail paie GPEC formation management 7 ans Bac+5",
     "skills": ["RH", "Droit du travail", "Paie", "GPEC", "Formation", "Management"],
     "exp_years": 7, "edu_level": 5,
     "experiences": [{"poste": "DRH", "description": "gestion ressources humaines droit du travail paie GPEC formation management", "duree_mois": 84}],
     "formations": [{"diplome": "Master", "specialite": "Ressources Humaines Management", "niveau_bac_plus": 5}]},

    # ── Marketing ────────────────────────────────────────────────────────────
    {"nom": "Marketing Digital Manager", "domaine": "marketing",
     "cv_text": "Marketing digital SEO Google Ads Facebook réseaux sociaux analytics 3 ans Bac+3",
     "skills": ["SEO", "Google Ads", "Facebook Ads", "Google Analytics", "Community Management", "Excel"],
     "exp_years": 3, "edu_level": 3,
     "experiences": [{"poste": "Manager Marketing Digital", "description": "SEO Google Ads Facebook réseaux sociaux analytics email marketing", "duree_mois": 36}],
     "formations": [{"diplome": "Licence", "specialite": "Marketing Communication", "niveau_bac_plus": 3}]},

    # ── Logistique ───────────────────────────────────────────────────────────
    {"nom": "Responsable Logistique", "domaine": "logistique",
     "cv_text": "Logistique supply chain WMS SAP Excel transport achats 5 ans Bac+5",
     "skills": ["Logistique", "Supply Chain", "WMS", "SAP", "Excel", "Achats"],
     "exp_years": 5, "edu_level": 5,
     "experiences": [{"poste": "Responsable logistique", "description": "logistique supply chain WMS SAP Excel transport achats approvisionnement", "duree_mois": 60}],
     "formations": [{"diplome": "Master", "specialite": "Logistique Supply Chain", "niveau_bac_plus": 5}]},

    {"nom": "Acheteur Junior", "domaine": "logistique",
     "cv_text": "Acheteur achats approvisionnement SAP Excel négociation fournisseurs 2 ans Bac+3",
     "skills": ["Achats", "Approvisionnement", "SAP", "Excel", "Négociation"],
     "exp_years": 2, "edu_level": 3,
     "experiences": [{"poste": "Acheteur", "description": "achats approvisionnement fournisseurs négociation SAP Excel", "duree_mois": 24}],
     "formations": [{"diplome": "Licence", "specialite": "Gestion Logistique", "niveau_bac_plus": 3}]},

    # ── Médical ──────────────────────────────────────────────────────────────
    {"nom": "Infirmier IDE", "domaine": "medecine",
     "cv_text": "Infirmier IDE soins intensifs urgences réanimation bloc opératoire 3 ans Bac+3",
     "skills": ["Soins infirmiers", "IDE", "Urgences", "Réanimation", "Bloc opératoire"],
     "exp_years": 3, "edu_level": 3,
     "experiences": [{"poste": "Infirmier IDE", "description": "soins infirmiers urgences réanimation bloc opératoire patients", "duree_mois": 36}],
     "formations": [{"diplome": "BTS", "specialite": "Soins Infirmiers", "niveau_bac_plus": 3}]},

    {"nom": "Pharmacien", "domaine": "medecine",
     "cv_text": "Pharmacien pharmacologie médicaments conseil patients ordonnances gestion stock 2 ans Bac+5",
     "skills": ["Pharmacologie", "Médicaments", "Conseil patient", "Gestion stock"],
     "exp_years": 2, "edu_level": 5,
     "experiences": [{"poste": "Pharmacien", "description": "pharmacologie médicaments conseil patients ordonnances gestion stock", "duree_mois": 24}],
     "formations": [{"diplome": "Doctorat", "specialite": "Pharmacie", "niveau_bac_plus": 5}]},

    # ── Droit ────────────────────────────────────────────────────────────────
    {"nom": "Juriste Droit", "domaine": "droit",
     "cv_text": "Juriste droit des contrats droit commercial RGPD négociation contrats 3 ans Bac+5",
     "skills": ["Droit des contrats", "Droit commercial", "RGPD", "Contrats", "Négociation"],
     "exp_years": 3, "edu_level": 5,
     "experiences": [{"poste": "Juriste", "description": "droit des contrats droit commercial RGPD propriété intellectuelle négociation", "duree_mois": 36}],
     "formations": [{"diplome": "Master", "specialite": "Droit des Affaires", "niveau_bac_plus": 5}]},

    # ── BTP ──────────────────────────────────────────────────────────────────
    {"nom": "Ingénieur Génie Civil", "domaine": "btp",
     "cv_text": "Ingénieur génie civil béton structures AutoCAD topographie chantier 4 ans Bac+5",
     "skills": ["Génie civil", "Béton", "AutoCAD", "Topographie", "Gestion chantier"],
     "exp_years": 4, "edu_level": 5,
     "experiences": [{"poste": "Ingénieur GC", "description": "génie civil béton armé structures AutoCAD topographie gestion chantier", "duree_mois": 48}],
     "formations": [{"diplome": "Ingénieur", "specialite": "Génie Civil BTP", "niveau_bac_plus": 5}]},

    # ── Profils hors-domaine (cas discriminants) ──────────────────────────────
    {"nom": "Dev Python (pour poste Finance)", "domaine": "informatique",
     "cv_text": "Développeur Python Django Docker REST API PostgreSQL 3 ans Bac+5",
     "skills": ["Python", "Django", "Docker", "Git", "REST API", "PostgreSQL"],
     "exp_years": 3, "edu_level": 5,
     "experiences": [{"poste": "Développeur Python", "description": "Python Django PostgreSQL Docker REST API", "duree_mois": 36}],
     "formations": [{"diplome": "Master", "specialite": "Informatique", "niveau_bac_plus": 5}]},

    {"nom": "Comptable (pour poste IT)", "domaine": "finance",
     "cv_text": "Comptable Excel SAP bilan comptabilité analytique 4 ans Bac+5",
     "skills": ["Comptabilité", "Excel", "SAP", "Reporting", "Budget"],
     "exp_years": 4, "edu_level": 5,
     "experiences": [{"poste": "Comptable", "description": "comptabilité SAP Excel bilan reporting budget", "duree_mois": 48}],
     "formations": [{"diplome": "Master", "specialite": "Finance Comptabilité", "niveau_bac_plus": 5}]},

    {"nom": "Infirmier (pour poste Dev)", "domaine": "medecine",
     "cv_text": "Infirmier soins intensifs urgences bloc opératoire IDE 3 ans Bac+3",
     "skills": ["Soins infirmiers", "IDE", "Urgences", "Réanimation"],
     "exp_years": 3, "edu_level": 3,
     "experiences": [{"poste": "Infirmier", "description": "soins infirmiers urgences réanimation patients", "duree_mois": 36}],
     "formations": [{"diplome": "BTS", "specialite": "Soins Infirmiers", "niveau_bac_plus": 3}]},

    {"nom": "Stage Informatique", "domaine": "informatique",
     "cv_text": "Étudiant Python React JavaScript SQL Git stage fin études",
     "skills": ["Python", "React", "JavaScript", "SQL", "Git"],
     "exp_years": 0, "edu_level": 4,
     "experiences": [],
     "formations": [{"diplome": "Master 1", "specialite": "Informatique", "niveau_bac_plus": 4}]},

    {"nom": "Juriste (pour poste RH)", "domaine": "droit",
     "cv_text": "Juriste droit social droit du travail contrats contentieux 3 ans Bac+5",
     "skills": ["Droit social", "Droit du travail", "Contrats", "Contentieux"],
     "exp_years": 3, "edu_level": 5,
     "experiences": [{"poste": "Juriste", "description": "droit social droit du travail contrats contentieux", "duree_mois": 36}],
     "formations": [{"diplome": "Master", "specialite": "Droit Social", "niveau_bac_plus": 5}]},
]


def main():
    print("=" * 65)
    print("  Generation dataset MLP Fusion v3  [9 features + multi-domaine]")
    print(f"  {len(OFFRES)} offres x {len(CANDIDATS)} candidats = {len(OFFRES)*len(CANDIDATS)} paires")
    print("=" * 65)

    print("\n[1/2] Chargement BGE-M3...")
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    scorer._ensure_reranker_loaded()
    if not scorer.ready:
        print("[ERREUR] BGE-M3 non disponible.")
        import sys; sys.exit(1)
    print("      BGE-M3 OK\n")

    rows = []
    done = 0
    total = len(OFFRES) * len(CANDIDATS)

    print(f"[2/2] Generation de {total} paires...")
    for offre in OFFRES:
        offer_mock = _MockOffer(offre)
        for cand in CANDIDATS:
            cand_mock = _MockCandidate(cand)

            _, details = scorer.score(offer_mock, cand_mock)

            # 7 features existantes
            sem_bge  = details.get("semantique",  50) / 100
            comp_bge = details.get("competences", 50) / 100
            exp_bge  = details.get("experience",  50) / 100
            form_bge = details.get("formation",   50) / 100
            sem_v2   = sem_bge  # cross-encoder via score_semantique
            skills_raw   = skill_overlap(offre["skills"], cand["skills"])
            req_edu  = offre.get("edu_requise", 0)
            cand_edu = cand.get("edu_level", 0)
            edu_gap_norm = round(max(-1.0, min(1.0, (req_edu - cand_edu) / 5.0)), 4)

            # 2 nouvelles features (semaine 3)
            # edu_domain_compat : compatibilité domaine formation candidat vs offre
            cand_edu_domain  = _detect_edu_domain(cand.get("domaine", "") + " " + " ".join(
                [f.get("specialite", "") for f in cand.get("formations", [])]))
            offer_edu_domain = _detect_edu_domain(offre.get("domaine", "") + " " + offre["description"])
            edu_domain_compat = _edu_domain_compatibility(cand_edu_domain, offer_edu_domain)

            # exp_domain_ratio : ratio années pertinentes / années totales
            domain_years, total_years = scorer._compute_domain_relevant_years(
                cand.get("experiences", []), offre["skills"], offre["description"]
            )
            exp_domain_ratio = round(domain_years / max(total_years, 0.5), 4) if total_years > 0 else 0.5

            label = compute_label(offre, cand)

            rows.append({
                "offre":            offre["titre"],
                "candidat":         cand["nom"],
                "sem_bge":          round(sem_bge,          6),
                "comp_bge":         round(comp_bge,         6),
                "exp_bge":          round(exp_bge,          6),
                "form_bge":         round(form_bge,         6),
                "sem_v2":           round(sem_v2,           6),
                "skills_raw":       round(skills_raw,       4),
                "edu_gap":          edu_gap_norm,
                "edu_domain_compat":round(edu_domain_compat,4),
                "exp_domain_ratio": round(exp_domain_ratio, 4),
                "label":            label,
            })

            done += 1
            if done % 50 == 0 or done <= 5:
                print(f"  [{done:4d}/{total}] {offre['titre'][:20]:<20}"
                      f" + {cand['nom'][:20]:<20}"
                      f"  sk={skills_raw:.2f} edu_d={edu_domain_compat:.2f}"
                      f" exp_d={exp_domain_ratio:.2f} lbl={label:.2f}")

    fieldnames = ["offre", "candidat", "sem_bge", "comp_bge", "exp_bge", "form_bge",
                  "sem_v2", "skills_raw", "edu_gap", "edu_domain_compat", "exp_domain_ratio", "label"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[OK] {len(rows)} paires -> {OUT_CSV}")
    print("Lancez maintenant : train_mlp_v3.py")


if __name__ == "__main__":
    main()
