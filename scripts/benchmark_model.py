# -*- coding: utf-8 -*-
"""
benchmark_model.py — Évaluation systématique du moteur de matching.
Teste le modèle par CATÉGORIE pour cartographier forces et faiblesses.

Chaque catégorie regroupe des cas avec un comportement ATTENDU.
Le script mesure le taux de réussite par catégorie et produit
une synthèse forces / faiblesses.

Usage : python scripts/benchmark_model.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "backend"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer


# ── Mock objects ──────────────────────────────────────────────────────────────
class Offer:
    def __init__(self, titre, desc, skills, exp=3, edu=5, niveau="", domaine=""):
        self.titre = titre; self.description = desc
        self.competences_requises = skills; self.competences_appreciees = []
        self.experience_requise = exp; self.formation_requise_niveau = edu
        self.domaine_metier = domaine; self.niveau_seniorite = niveau
        self.type_contrat = "CDI"; self.localisation = None; self.status = "active"
        self.nb_postes = 1
        self.raw_text = desc + " " + " ".join(skills)

class Cand:
    def __init__(self, nom, cv, skills, exp=3, edu=5, spec=""):
        self.nom = nom; self.email = "x@x.com"; self.raw_text = cv; self.cv_id = None
        self.parsed_data = {
            "competences": skills,
            "experiences": [{"poste": nom, "description": cv, "duree_mois": int(exp * 12)}],
            "formations": [{"diplome": "Master" if edu >= 5 else "Licence",
                            "specialite": spec, "niveau_bac_plus": edu}] if spec else [],
            "metadata": {"annees_experience_totales": exp, "niveau_formation_max": edu},
        }


# ── Catégories de test ────────────────────────────────────────────────────────
# Chaque cas : (offre, candidat, min_attendu, max_attendu, description)

def build_categories():
    cats = {}

    # ════════════ CATÉGORIE 1 : Match parfait même domaine ════════════
    cats["1. Match parfait (même domaine)"] = [
        (Offer("Développeur Python Senior", "Python FastAPI PostgreSQL Docker 5 ans Bac+5",
               ["Python","FastAPI","PostgreSQL","Docker","Redis"], exp=5, edu=5, niveau="Senior"),
         Cand("Dev Python Expert", "Python 6 ans FastAPI Django PostgreSQL Docker Redis Kubernetes Bac+5",
              ["Python","FastAPI","Django","PostgreSQL","Docker","Redis"], exp=6, edu=5, spec="Génie Logiciel"),
         0.75, 1.00, "Dev Python expert → poste Python Senior"),

        (Offer("Comptable Senior", "Comptabilité SAP IFRS audit 5 ans Bac+5",
               ["Comptabilité générale","SAP","IFRS","Audit interne","Fiscalité"], exp=5, edu=5, niveau="Senior"),
         Cand("Comptable Confirmé", "Comptabilité 6 ans SAP IFRS audit interne fiscalité bilan Bac+5",
              ["Comptabilité générale","SAP","IFRS","Audit interne","Fiscalité","Excel"], exp=6, edu=5, spec="Finance"),
         0.70, 1.00, "Comptable confirmé → poste Comptable Senior"),

        (Offer("Infirmier IDE", "Soins infirmiers réanimation urgences ECG Bac+3 2 ans",
               ["Soins infirmiers","IDE","Réanimation","Urgences","ECG"], exp=2, edu=3),
         Cand("Infirmier Exp", "Infirmier IDE 4 ans soins intensifs réanimation urgences ECG Bac+3",
              ["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences","ECG"], exp=4, edu=3, spec="Soins Infirmiers"),
         0.70, 1.00, "Infirmier expérimenté → poste Infirmier"),
    ]

    # ════════════ CATÉGORIE 2 : Rejet hors-domaine ════════════
    cats["2. Rejet hors-domaine total"] = [
        (Offer("Développeur Python", "Python FastAPI Docker Bac+5 3 ans",
               ["Python","FastAPI","PostgreSQL","Docker"], exp=3, edu=5),
         Cand("Infirmier", "Infirmier IDE soins réanimation urgences Bac+3",
              ["Soins infirmiers","IDE","Réanimation"], exp=3, edu=3, spec="Soins Infirmiers"),
         0.00, 0.20, "Infirmier → poste Dev Python"),

        (Offer("Comptable", "Comptabilité SAP IFRS Bac+5",
               ["Comptabilité générale","SAP","IFRS","Audit interne"], exp=3, edu=5),
         Cand("Dev Python", "Python FastAPI Docker PostgreSQL Bac+5",
              ["Python","FastAPI","Docker","PostgreSQL"], exp=4, edu=5, spec="Informatique"),
         0.00, 0.25, "Dev Python → poste Comptable"),

        (Offer("Juriste Droit Affaires", "Droit affaires contrats RGPD Bac+5",
               ["Droit des affaires","Contrats","RGPD","Conformité"], exp=3, edu=5),
         Cand("Ingénieur BTP", "Génie civil BIM AutoCAD chantier Bac+5",
              ["Génie civil","BIM","AutoCAD","Suivi de chantier"], exp=4, edu=5, spec="Génie Civil"),
         0.00, 0.20, "Ingénieur BTP → poste Juriste"),
    ]

    # ════════════ CATÉGORIE 3 : Domaines adjacents ════════════
    cats["3. Domaines adjacents (zone grise)"] = [
        (Offer("Contrôleur de Gestion", "Contrôle gestion SAP IFRS reporting Bac+5",
               ["Contrôle de gestion","SAP","IFRS","Reporting financier","Excel"], exp=3, edu=5),
         Cand("Chargé RH", "RH recrutement paie GPEC droit travail Bac+3",
              ["RH","Recrutement","Paie","GPEC","Droit du travail"], exp=3, edu=3, spec="Ressources Humaines"),
         0.10, 0.45, "RH → poste Finance (adjacent)"),

        (Offer("Data Scientist", "Machine learning Python TensorFlow Bac+5 3 ans",
               ["Machine Learning","Python","TensorFlow","scikit-learn","Pandas"], exp=3, edu=5),
         Cand("Dev Fullstack", "Python React Node PostgreSQL Docker 4 ans Bac+5",
              ["Python","React","Node.js","PostgreSQL","Docker"], exp=4, edu=5, spec="Informatique"),
         0.20, 0.55, "Dev Fullstack → poste Data Scientist (IT adjacent)"),
    ]

    # ════════════ CATÉGORIE 4 : Synonymes multilingues (A1) ════════════
    cats["4. Synonymes EN/FR (skills_aliases)"] = [
        (Offer("Chargé RH Recrutement", "Recrutement sourcing GPEC paie Bac+3 2 ans",
               ["Recrutement","RH","GPEC","Paie","Droit du travail"], exp=2, edu=3),
         Cand("HR Manager", "HR Manager talent management recruiting payroll labour law 4 ans Bac+5",
              ["talent management","recruiting","human resources","payroll","labour law"], exp=4, edu=5, spec="Human Resources"),
         0.45, 1.00, "HR Manager (EN) → poste RH (FR)"),

        (Offer("Développeur React", "React TypeScript JavaScript Bac+3 2 ans",
               ["React","TypeScript","JavaScript","CSS"], exp=2, edu=3),
         Cand("Frontend Dev", "ReactJS React.js TypeScript ES6 frontend 3 ans Bac+5",
              ["reactjs","react.js","typescript","javascript"], exp=3, edu=5, spec="Informatique"),
         0.55, 1.00, "Dev (reactjs/react.js) → poste React"),
    ]

    # ════════════ CATÉGORIE 5 : Cap compétence titre (Phase 1) ════════════
    cats["5. Cap compétence titre (Phase 1)"] = [
        (Offer("Développeur Python", "Python FastAPI Docker Bac+5 3 ans",
               ["Python","FastAPI","Docker","Git"], exp=3, edu=5),
         Cand("Dev Java", "Java Spring Boot PostgreSQL Docker Maven 4 ans Bac+5",
              ["Java","Spring Boot","PostgreSQL","Docker","Maven"], exp=4, edu=5, spec="Informatique"),
         0.00, 0.50, "Dev Java (pas Python) → poste Python : doit être capé"),

        (Offer("Développeur React", "React TypeScript Bac+3 2 ans",
               ["React","TypeScript","JavaScript","CSS"], exp=2, edu=3),
         Cand("Dev Angular", "Angular TypeScript RxJS HTML CSS 3 ans Bac+5",
              ["Angular","TypeScript","RxJS","HTML","CSS"], exp=3, edu=5, spec="Informatique"),
         0.00, 0.55, "Dev Angular (pas React) → poste React : doit être capé"),
    ]

    # ════════════ CATÉGORIE 6 : Surqualification ════════════
    cats["6. Surqualification (point sensible)"] = [
        (Offer("Stage Développeur Python", "Stage Python Django débutant Bac+4",
               ["Python","Django","Git"], exp=0, edu=4, niveau="Stage"),
         Cand("Dev Python Senior 8ans", "Python 8 ans architecte FastAPI Django Kubernetes Bac+5",
              ["Python","FastAPI","Django","Kubernetes","Docker"], exp=8, edu=5, spec="Génie Logiciel"),
         0.40, 0.85, "Senior 8 ans → poste Stage : surqualifié (idéalement score modéré)"),
    ]

    # ════════════ CATÉGORIE 7 : Sous-qualification expérience ════════════
    cats["7. Sous-qualification expérience"] = [
        (Offer("Contrôleur de Gestion Senior", "Contrôle gestion SAP IFRS 8 ans Bac+5",
               ["Contrôle de gestion","SAP","IFRS","Reporting financier"], exp=8, edu=5, niveau="Senior"),
         Cand("Comptable Junior 1an", "Comptabilité SAP Excel IFRS débutant 1 an Bac+5",
              ["Comptabilité","SAP","Excel","IFRS"], exp=1, edu=5, spec="Finance"),
         0.15, 0.60, "Junior 1 an → poste Senior 8 ans : skills OK, exp faible"),

        (Offer("Développeur React Senior", "React TypeScript Redux 5 ans Bac+5",
               ["React","TypeScript","JavaScript","Redux"], exp=5, edu=5, niveau="Senior"),
         Cand("Dev React Débutant", "React JavaScript HTML CSS stage 1 an Bac+3",
              ["React","JavaScript","HTML","CSS"], exp=1, edu=3, spec="Informatique"),
         0.20, 0.65, "Débutant 1 an → poste Senior 5 ans"),
    ]

    # ════════════ CATÉGORIE 8 : Discrimination junior/stage ════════════
    # Point faible identifié : exp=5% rend les juniors indiscernables
    cats["8. Discrimination junior (exp faible)"] = [
        (Offer("Stage Web Full Stack", "Stage Python React Node Git Bac+4",
               ["Python","React","Node.js","Git","HTML"], exp=0, edu=4, niveau="Stage"),
         Cand("Stagiaire Fort", "Python React Node.js Git HTML CSS Express projets Bac+4",
              ["Python","React","Node.js","Git","HTML","CSS","Express.js"], exp=0, edu=4, spec="Informatique"),
         0.65, 1.00, "Stagiaire 7/5 skills → poste Stage : doit ressortir haut"),

        (Offer("Stage Web Full Stack", "Stage Python React Node Git Bac+4",
               ["Python","React","Node.js","Git","HTML"], exp=0, edu=4, niveau="Stage"),
         Cand("Stagiaire Faible", "Python HTML CSS débutant Bac+4",
              ["Python","HTML","CSS"], exp=0, edu=4, spec="Informatique"),
         0.20, 0.60, "Stagiaire 2/5 skills → poste Stage : doit ressortir plus bas"),
    ]

    return cats


# ── Exécution ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 78)
    print("  BENCHMARK MODÈLE — Cartographie forces / faiblesses")
    print("=" * 78)

    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()

    cats = build_categories()
    cat_results = {}
    all_rows = []

    for cat_name, cases in cats.items():
        passed = 0
        details = []
        for offer, cand, mn, mx, desc in cases:
            score, det = scorer.score(offer, cand)
            ok = mn <= score <= mx
            if ok:
                passed += 1
            details.append((desc, score, mn, mx, ok, det))
            all_rows.append((cat_name, desc, score, mn, mx, ok))
        cat_results[cat_name] = (passed, len(cases), details)

    # ── Affichage détaillé ────────────────────────────────────────────────────
    for cat_name, (passed, total, details) in cat_results.items():
        rate = passed / total * 100
        status = "FORT" if rate == 100 else ("MOYEN" if rate >= 50 else "FAIBLE")
        print(f"\n{'─'*78}")
        print(f"  {cat_name}   [{passed}/{total} — {status}]")
        print(f"{'─'*78}")
        for desc, score, mn, mx, ok, det in details:
            icon = "OK " if ok else "XXX"
            ts = det.get("title_skill", "")
            ts_ko = det.get("title_skill_missing", False)
            extra = f"  (titre '{ts}' manquant)" if ts_ko and ts else ""
            print(f"    [{icon}] {score*100:5.1f}%  (cible {mn*100:.0f}-{mx*100:.0f}%)  {desc[:48]}{extra}")

    # ── Synthèse forces / faiblesses ──────────────────────────────────────────
    print(f"\n{'='*78}")
    print(f"  SYNTHÈSE — FORCES & FAIBLESSES")
    print(f"{'='*78}")

    forces, moyens, faibles = [], [], []
    total_pass = total_cases = 0
    for cat_name, (passed, total, _) in cat_results.items():
        total_pass += passed; total_cases += total
        rate = passed / total * 100
        if rate == 100:    forces.append((cat_name, passed, total))
        elif rate >= 50:   moyens.append((cat_name, passed, total))
        else:              faibles.append((cat_name, passed, total))

    print(f"\n  POINTS FORTS ({len(forces)} catégories) :")
    for name, p, t in forces:
        print(f"    + {name}  ({p}/{t})")

    if moyens:
        print(f"\n  POINTS MOYENS ({len(moyens)} catégories) :")
        for name, p, t in moyens:
            print(f"    ~ {name}  ({p}/{t})")

    if faibles:
        print(f"\n  POINTS FAIBLES ({len(faibles)} catégories) :")
        for name, p, t in faibles:
            print(f"    - {name}  ({p}/{t})")

    print(f"\n  SCORE GLOBAL : {total_pass}/{total_cases} = {total_pass/total_cases*100:.0f}%")
    print("=" * 78)


if __name__ == "__main__":
    main()
