"""
show_ranking.py — Affiche l'ordre actuel du modèle pour 3 offres.
Sert à définir manuellement les ordres attendus dans test_ranking.py.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer

class Offer:
    def __init__(self, titre, desc, skills, exp=3, edu=5, niveau=""):
        self.titre=titre; self.description=desc; self.competences_requises=skills
        self.competences_appreciees=[]; self.experience_requise=exp
        self.formation_requise_niveau=edu; self.domaine_metier=""
        self.niveau_seniorite=niveau; self.type_contrat="CDI"
        self.localisation=None; self.status="active"
        self.raw_text=desc+" "+" ".join(skills)

class Cand:
    def __init__(self, nom, cv, skills, exp=3, edu=5, exps=None, fmts=None):
        self.nom=nom; self.email=nom+"@x.com"; self.raw_text=cv; self.cv_id=None
        self.parsed_data={
            "competences": skills,
            "experiences": exps or [{"poste":nom,"description":cv,"duree_mois":int(exp*12)}],
            "formations":  fmts or [],
            "metadata":    {"annees_experience_totales":exp,"niveau_formation_max":edu},
        }

scorer = BERTMatchingScorer()
scorer._ensure_loaded()

# ── OFFRE 1 : Développeur Python Senior ──────────────────────────────────────
O1 = Offer("Développeur Python Senior",
           "CDI Python FastAPI PostgreSQL Docker Redis CI/CD Bac+5 5 ans expérience",
           ["Python","FastAPI","PostgreSQL","Docker","Redis","CI/CD","Git"], exp=5, edu=5, niveau="Senior")
CANDS_O1 = [
    Cand("Dev Python 5ans",   "Python 5 ans FastAPI Django PostgreSQL Docker Redis Kubernetes CI/CD Bac+5", ["Python","FastAPI","Django","PostgreSQL","Docker","Redis","Git","CI/CD"], exp=5, edu=5),
    Cand("Dev Python 2ans",   "Python 2 ans FastAPI PostgreSQL Docker Git REST Bac+5",                     ["Python","FastAPI","PostgreSQL","Docker","Git"],                         exp=2, edu=5),
    Cand("Stage Python",      "Etudiant Python Django REST stage Bac+4",                                   ["Python","Django","REST API","Git"],                                     exp=0, edu=4),
    Cand("Dev Java 4ans",     "Java Spring Boot Hibernate PostgreSQL Docker Maven 4 ans Bac+5",            ["Java","Spring Boot","PostgreSQL","Docker","Maven","Git"],               exp=4, edu=5),
    Cand("Comptable 5ans",    "Comptabilité SAP IFRS audit bilan trésorerie 5 ans Bac+5",                  ["Comptabilité générale","SAP","IFRS","Audit interne","Excel"],            exp=5, edu=5),
]

# ── OFFRE 2 : Contrôleur de Gestion ─────────────────────────────────────────
O2 = Offer("Contrôleur de Gestion Senior",
           "CDI contrôle de gestion Excel SAP IFRS reporting bilan 5 ans Bac+5",
           ["Contrôle de gestion","Excel","SAP","IFRS","Reporting financier","Analyse financière"], exp=5, edu=5, niveau="Senior")
CANDS_O2 = [
    Cand("Contrôleur GS 5ans",  "Contrôle gestion SAP IFRS Excel reporting analyse financière 5 ans Bac+5",  ["Contrôle de gestion","SAP","IFRS","Excel","Reporting financier","Analyse financière"], exp=5, edu=5),
    Cand("Comptable 4ans",      "Comptabilité SAP IFRS audit bilan fiscalité trésorerie 4 ans Bac+5",        ["Comptabilité générale","SAP","IFRS","Audit interne","Fiscalité","Excel"],             exp=4, edu=5),
    Cand("Auditeur 2ans",       "Audit interne comptabilité Excel reporting 2 ans Bac+3",                    ["Audit interne","Comptabilité","Excel","Reporting financier"],                         exp=2, edu=3),
    Cand("Chargée RH 3ans",     "RH recrutement GPEC paie droit travail SIRH 3 ans Bac+3",                  ["RH","Recrutement","Paie","GPEC","Droit du travail"],                                 exp=3, edu=3),
    Cand("Dev Python 5ans",     "Python 5 ans FastAPI PostgreSQL Docker Redis CI/CD Bac+5",                  ["Python","FastAPI","PostgreSQL","Docker","Redis","CI/CD"],                            exp=5, edu=5),
]

# ── OFFRE 3 : Chargé RH Recrutement ─────────────────────────────────────────
O3 = Offer("Chargé RH Recrutement",
           "CDI recrutement sourcing LinkedIn RH paie GPEC droit travail SIRH Bac+3 2 ans",
           ["Recrutement","RH","LinkedIn","Paie","GPEC","Droit du travail","SIRH"], exp=2, edu=3, niveau="Junior")
CANDS_O3 = [
    Cand("Chargée RH Expert 4ans", "RH recrutement sourcing LinkedIn paie GPEC droit travail SIRH 4 ans Bac+3",  ["RH","Recrutement","LinkedIn","Paie","GPEC","Droit du travail","SIRH"], exp=4, edu=3),
    Cand("Recruteur Junior",       "Recrutement sourcing LinkedIn ATS débutant 1 an Bac+3",                       ["Recrutement","LinkedIn","Sourcing","ATS"],                                exp=1, edu=3),
    Cand("HR Manager EN",          "HR Manager talent management recruiting human resources payroll 4 ans Bac+5", ["talent management","recruiting","human resources","payroll","HRIS"],  exp=4, edu=5),
    Cand("Comptable 4ans",         "Comptabilité SAP IFRS audit bilan fiscalité 4 ans Bac+5",                     ["Comptabilité générale","SAP","IFRS","Audit interne"],                    exp=4, edu=5),
    Cand("Dev Python 5ans",        "Python 5 ans FastAPI PostgreSQL Docker CI/CD Bac+5",                          ["Python","FastAPI","PostgreSQL","Docker","CI/CD"],                        exp=5, edu=5),
]

SCENARIOS = [
    ("Développeur Python Senior", O1, CANDS_O1),
    ("Contrôleur de Gestion Senior", O2, CANDS_O2),
    ("Chargé RH Recrutement", O3, CANDS_O3),
]

print("=" * 70)
print("  Classements actuels du modèle (à valider pour test_ranking.py)")
print("=" * 70)
for titre, offer, cands in SCENARIOS:
    results = []
    for cand in cands:
        score, _ = scorer.score(offer, cand)
        results.append((cand.nom, score))
    results.sort(key=lambda x: -x[1])
    print(f"\nOFFRE : {titre}")
    for i, (nom, s) in enumerate(results, 1):
        print(f"  #{i}  {nom:35s}  {s*100:.1f}%")
    print(f"  Ordre : {[r[0] for r in results]}")
