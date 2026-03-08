"""
╔═══════════════════════════════════════════════════════════════════╗
║           3S TalentMatch — Validation Sprint 2 NLP               ║
║                    Script de test combiné                         ║
╚═══════════════════════════════════════════════════════════════════╝

Lance ce script pour valider les 3 extracteurs NLP :
  1. SkillsExtractor   (US-207)
  2. FormationExtractor (US-209)
  3. ExperienceExtractor (US-210)

Usage :
  cd C:\\Users\\youssef\\Desktop\\3s-talentmatch
  .venv\\Scripts\\python.exe backend\\tests\\validate_sprint2_nlp.py
"""

import sys
import os

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import spacy
from app.services.nlp.skills_extractor import SkillsExtractor
from app.services.nlp.formation_extractor import FormationExtractor
from app.services.nlp.experience_extractor import ExperienceExtractor


# ══════════════════════════════════════════════════════════════════
# CV de test réaliste (FR/EN mixte — comme un vrai CV tunisien)
# ══════════════════════════════════════════════════════════════════

CV_TEST = """
Youssef Gara
Email: youssef.gara@esprit.tn
Téléphone: +216 22 333 444

Profil
Ingénieur logiciel passionné par l'intelligence artificielle et le développement
web. 3 ans d'expérience en Python, React et DevOps.

Expériences professionnelles

Développeur Full Stack chez Sofrecom — Tunis
Janvier 2023 - Présent
- Développement d'APIs REST avec FastAPI et PostgreSQL
- Mise en place CI/CD avec GitHub Actions et Docker
- Conception de microservices avec RabbitMQ
- Tests unitaires avec Pytest (couverture >85%)

Stagiaire Data Engineer chez Orange — Paris
Février 2022 - Juillet 2022
- Pipeline ETL avec Apache Spark et Airflow
- Dashboards Power BI pour l'équipe marketing
- Optimisation des requêtes SQL (gain de 60%)

Stagiaire Développeur Web chez Vermeg — Tunis
Juin 2021 - Août 2021
- Développement front-end React avec TypeScript
- Intégration API REST et tests Cypress

Formation

Diplôme d'Ingénieur en Génie Logiciel
ESPRIT, 2023 — Mention Très Bien

Cycle Préparatoire Intégré (CPI)
ESPRIT, 2020

Baccalauréat Sciences Expérimentales
Lycée Pilote de Sousse, 2018

Compétences
Langages : Python, JavaScript, TypeScript, Java, SQL, C++
Frameworks : FastAPI, React, Django, Spring Boot, Express.js
Bases de données : PostgreSQL, MongoDB, Redis, Elasticsearch
DevOps : Docker, Kubernetes, Jenkins, GitHub Actions, Terraform
Cloud : AWS (EC2, S3, Lambda), GCP
Data : Apache Spark, Airflow, Power BI, Pandas, NumPy
IA/ML : TensorFlow, PyTorch, Scikit-learn, spaCy, OpenCV
Outils : Git, Jira, Figma, Postman, Swagger

Langues
Français — Courant
Anglais — Professionnel (TOEIC 890)
Arabe — Langue maternelle
"""


def print_separator(title: str):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


def main():
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║           3S TalentMatch — Validation Sprint 2 NLP               ║
╚═══════════════════════════════════════════════════════════════════╝
    """)

    # Charger spaCy
    print("Chargement du modèle spaCy fr_core_news_md...")
    nlp = spacy.load("fr_core_news_md")
    print("OK\n")

    errors = []

    # ══════════════════════════════════════════════════════════════
    # 1. SKILLS EXTRACTOR (US-207)
    # ══════════════════════════════════════════════════════════════
    print_separator("1. COMPÉTENCES (US-207 — skills_extractor.py)")

    skills_ext = SkillsExtractor()
    skills_result = skills_ext.extract(CV_TEST)
    skills = skills_result.get("skills", [])

    print(f"\n  Total compétences détectées : {len(skills)}\n")

    # Grouper par catégorie
    by_cat = skills_result.get("by_category", {})

    for cat, items in sorted(by_cat.items()):
        print(f"  📂 {cat} ({len(items)})")
        for name in items:
            # Trouver le détail dans skills list
            detail = next((s for s in skills if s["name"] == name), {})
            level = detail.get("level", "?")
            years = detail.get("years")
            years_str = f" — {years} ans" if years else ""
            print(f"     • {name:25s}  [{level}]{years_str}")
        print()

    # Vérifications
    skill_names = {s["name"].lower() for s in skills}
    expected_skills = {"python", "react", "docker", "postgresql", "fastapi", "tensorflow"}
    missing = expected_skills - skill_names
    if missing:
        errors.append(f"Skills manquantes: {missing}")
        print(f"  ⚠️  Skills attendues mais non détectées : {missing}")
    else:
        print(f"  ✅ Toutes les skills clés détectées ({len(expected_skills)}/{len(expected_skills)})")

    if len(skills) < 15:
        errors.append(f"Seulement {len(skills)} skills (attendu ≥15)")
        print(f"  ⚠️  Seulement {len(skills)} skills (attendu ≥15)")
    else:
        print(f"  ✅ {len(skills)} compétences au total (seuil ≥15 OK)")

    # ══════════════════════════════════════════════════════════════
    # 2. FORMATION EXTRACTOR (US-209)
    # ══════════════════════════════════════════════════════════════
    print_separator("2. FORMATIONS (US-209 — formation_extractor.py)")

    formation_ext = FormationExtractor(nlp_model=nlp)
    formation_result = formation_ext.extract(CV_TEST)
    formations = formation_result.get("formations", [])
    niveau_max = formation_result.get("niveau_max", 0)

    print(f"\n  Total formations : {len(formations)}")
    print(f"  Niveau max       : Bac+{niveau_max}\n")

    for f in formations:
        diplome = f.get("diplome", "?")
        spec = f.get("specialite") or "-"
        etab = f.get("etablissement") or "-"
        annee = f.get("annee") or "-"
        mention = f.get("mention")
        en_cours = " 📚 en cours" if f.get("en_cours") else ""
        mention_str = f" — 🏅 {mention}" if mention else ""
        level = f.get("niveau_bac_plus", "?")

        print(f"  🎓 {diplome} (Bac+{level})")
        print(f"     Spécialité    : {spec}")
        print(f"     Établissement : {etab}")
        print(f"     Année         : {annee}{mention_str}{en_cours}")
        print()

    # Vérifications
    if len(formations) < 2:
        errors.append(f"Seulement {len(formations)} formations (attendu ≥2)")
        print(f"  ⚠️  Seulement {len(formations)} formations (attendu ≥2)")
    else:
        print(f"  ✅ {len(formations)} formations détectées")

    etabs = [f.get("etablissement") for f in formations if f.get("etablissement")]
    if "ESPRIT" in str(etabs):
        print(f"  ✅ ESPRIT détecté comme établissement")
    else:
        errors.append("ESPRIT non détecté")
        print(f"  ⚠️  ESPRIT non détecté dans les établissements")

    if niveau_max >= 5:
        print(f"  ✅ Niveau max Bac+{niveau_max} (ingénieur = Bac+5)")
    else:
        errors.append(f"Niveau max Bac+{niveau_max} (attendu ≥5)")

    # ══════════════════════════════════════════════════════════════
    # 3. EXPERIENCE EXTRACTOR (US-210)
    # ══════════════════════════════════════════════════════════════
    print_separator("3. EXPÉRIENCES (US-210 — experience_extractor.py)")

    exp_ext = ExperienceExtractor(nlp_model=nlp)
    exp_result = exp_ext.extract(CV_TEST)
    experiences = exp_result.get("experiences", [])
    total_years = exp_result.get("annees_experience_totales", 0)

    print(f"\n  Total expériences    : {len(experiences)}")
    print(f"  Expérience totale    : {total_years} années\n")

    for exp in experiences:
        poste = exp.get("poste") or "?"
        entreprise = exp.get("entreprise") or "-"
        d_debut = exp.get("date_debut") or "?"
        d_fin = exp.get("date_fin") or "en cours"
        en_cours = " 📌 en cours" if exp.get("en_cours") else ""
        duree = exp.get("duree_mois")
        loc = exp.get("localisation") or "-"
        missions = exp.get("missions", [])

        print(f"  💼 {poste}")
        print(f"     Entreprise  : {entreprise}")
        print(f"     Période     : {d_debut} → {d_fin}{en_cours}")
        if duree:
            print(f"     Durée       : {duree} mois")
        print(f"     Lieu        : {loc}")
        if missions:
            print(f"     Missions    : {len(missions)} détectées")
            for m in missions[:3]:
                print(f"       • {m[:75]}")
        print()

    # Vérifications
    if len(experiences) < 2:
        errors.append(f"Seulement {len(experiences)} expériences (attendu ≥2)")
        print(f"  ⚠️  Seulement {len(experiences)} expériences (attendu ≥2)")
    else:
        print(f"  ✅ {len(experiences)} expériences détectées")

    companies = [e.get("entreprise") for e in experiences if e.get("entreprise")]
    if companies:
        print(f"  ✅ Entreprises détectées : {', '.join(companies)}")
    else:
        errors.append("Aucune entreprise détectée")
        print(f"  ⚠️  Aucune entreprise détectée")

    en_cours_count = sum(1 for e in experiences if e.get("en_cours"))
    if en_cours_count >= 1:
        print(f"  ✅ {en_cours_count} expérience(s) « en cours » détectée(s)")
    else:
        print(f"  ⚠️  Aucune expérience « en cours » (Sofrecom devrait l'être)")

    missions_total = sum(len(e.get("missions", [])) for e in experiences)
    if missions_total >= 5:
        print(f"  ✅ {missions_total} missions extraites au total")
    else:
        errors.append(f"Seulement {missions_total} missions")

    # ══════════════════════════════════════════════════════════════
    # BILAN FINAL
    # ══════════════════════════════════════════════════════════════
    print_separator("BILAN FINAL")

    if errors:
        print(f"\n  ⚠️  {len(errors)} problème(s) détecté(s) :")
        for e in errors:
            print(f"     ❌ {e}")
    else:
        print("""
  ✅ TOUS LES EXTRACTEURS SONT OPÉRATIONNELS

  Résumé :
  ┌─────────────────────┬───────────────────────────────────┐
  │ Extracteur          │ Résultat                          │
  ├─────────────────────┼───────────────────────────────────┤""")
        print(f"  │ Skills  (US-207)    │ {len(skills):3d} compétences détectées        │")
        print(f"  │ Formation (US-209)  │ {len(formations):3d} formations, max Bac+{niveau_max}       │")
        print(f"  │ Expérience (US-210) │ {len(experiences):3d} postes, {total_years} ans total       │")
        print(f"  └─────────────────────┴───────────────────────────────────┘")

    print(f"\n  Prochaine étape : US-208 (schéma Pydantic cv_data.py)")
    print(f"                    puis intégration dans nlp_parser.py\n")


if __name__ == "__main__":
    main()
