"""
seed_candidates.py
==================
Insère directement des candidats fictifs en base PostgreSQL
sans upload de fichier — visible instantanément dans le frontend.

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10/Scripts/python data/seed_candidates.py
  .venv-10/Scripts/python data/seed_candidates.py --reset   # supprime les seedés avant
"""

import sys
import uuid
import argparse
from datetime import datetime, timezone

sys.path.insert(0, "backend")

from app.database import SessionLocal
from app.models.candidate import Candidate

SEED_TAG = "SEED_TEST"   # marqueur dans cv_id pour pouvoir les supprimer proprement

# ── Profils candidats ─────────────────────────────────────────────────────────
# parsed_data suit exactement le format produit par le pipeline NLP
CANDIDATES = [

    # ── Backend Python ────────────────────────────────────────────────────────
    {
        "nom": "Aymen Belhaj",
        "email": "aymen.belhaj@email.tn",
        "telephone": "+216 55 123 456",
        "parsed_data": {
            "competences": [
                {"name": "Python"}, {"name": "FastAPI"}, {"name": "PostgreSQL"},
                {"name": "Docker"}, {"name": "Redis"}, {"name": "SQLAlchemy"},
                {"name": "Git"}, {"name": "REST API"}, {"name": "pytest"},
            ],
            "formations": [{"diplome": "Ingénieur Informatique", "niveau": 5, "etablissement": "EPT Tunis", "annee": 2020}],
            "experiences": [
                {"poste": "Ingénieur Backend Senior", "entreprise": "DataFlow", "duree_mois": 48},
                {"poste": "Développeur Python", "entreprise": "TechStartup TN", "duree_mois": 24},
            ],
            "annees_experience": 6,
            "niveau_formation": 5,
            "langues": ["Arabe", "Français", "Anglais"],
            "localisation": "Tunis",
            "metadata": {"source": "seed_test"},
        },
    },
    {
        "nom": "Sonia Trabelsi",
        "email": "sonia.trabelsi@gmail.com",
        "telephone": "+216 22 987 654",
        "parsed_data": {
            "competences": [
                {"name": "Python"}, {"name": "Django"}, {"name": "PostgreSQL"},
                {"name": "Docker"}, {"name": "Git"}, {"name": "REST API"},
                {"name": "JavaScript"}, {"name": "pytest"},
            ],
            "formations": [{"diplome": "Master Génie Logiciel", "niveau": 5, "etablissement": "ENSI Tunis", "annee": 2023}],
            "experiences": [
                {"poste": "Développeuse Backend", "entreprise": "WebAgency Tunis", "duree_mois": 24},
                {"poste": "Stagiaire Développeur", "entreprise": "StartupTN", "duree_mois": 6},
            ],
            "annees_experience": 2,
            "niveau_formation": 5,
            "langues": ["Arabe", "Français", "Anglais"],
            "localisation": "Tunis",
            "metadata": {"source": "seed_test"},
        },
    },
    {
        "nom": "Omar Hamdi",
        "email": "omar.hamdi@yahoo.fr",
        "telephone": "+216 98 456 123",
        "parsed_data": {
            "competences": [
                {"name": "Python"}, {"name": "Flask"}, {"name": "MySQL"},
                {"name": "Git"}, {"name": "HTML"}, {"name": "CSS"},
            ],
            "formations": [{"diplome": "Licence Informatique", "niveau": 3, "etablissement": "Université Sfax", "annee": 2024}],
            "experiences": [
                {"poste": "Développeur Python Junior", "entreprise": "WebDev Sfax", "duree_mois": 12},
            ],
            "annees_experience": 1,
            "niveau_formation": 3,
            "langues": ["Arabe", "Français"],
            "localisation": "Sfax",
            "metadata": {"source": "seed_test"},
        },
    },
    {
        "nom": "Karim Mansouri",
        "email": "karim.mansouri@outlook.com",
        "telephone": "+216 25 741 852",
        "parsed_data": {
            "competences": [
                {"name": "Java"}, {"name": "Spring Boot"}, {"name": "MySQL"},
                {"name": "Docker"}, {"name": "Git"}, {"name": "REST API"},
                {"name": "Angular"}, {"name": "TypeScript"}, {"name": "Kubernetes"},
            ],
            "formations": [{"diplome": "Ingénieur Informatique", "niveau": 5, "etablissement": "INSAT Tunis", "annee": 2021}],
            "experiences": [
                {"poste": "Développeur Backend Java", "entreprise": "Banque de Tunisie", "duree_mois": 36},
                {"poste": "Développeur Java Junior", "entreprise": "IT Consulting TN", "duree_mois": 24},
            ],
            "annees_experience": 5,
            "niveau_formation": 5,
            "langues": ["Arabe", "Français", "Anglais"],
            "localisation": "Tunis",
            "metadata": {"source": "seed_test"},
        },
    },

    # ── Data Science ──────────────────────────────────────────────────────────
    {
        "nom": "Nour Ben Salem",
        "email": "nour.bensalem@datascience.tn",
        "telephone": "+216 54 321 987",
        "parsed_data": {
            "competences": [
                {"name": "Python"}, {"name": "Machine Learning"}, {"name": "TensorFlow"},
                {"name": "scikit-learn"}, {"name": "Pandas"}, {"name": "NumPy"},
                {"name": "SQL"}, {"name": "Git"}, {"name": "Docker"}, {"name": "MLflow"},
            ],
            "formations": [{"diplome": "Master Data Science", "niveau": 5, "etablissement": "ESPRIT Tunis", "annee": 2022}],
            "experiences": [
                {"poste": "Data Scientist", "entreprise": "DataLab TN", "duree_mois": 30},
                {"poste": "ML Engineer Stagiaire", "entreprise": "Orange Tunisie", "duree_mois": 6},
            ],
            "annees_experience": 3,
            "niveau_formation": 5,
            "langues": ["Arabe", "Français", "Anglais"],
            "localisation": "Tunis",
            "metadata": {"source": "seed_test"},
        },
    },
    {
        "nom": "Mehdi Karray",
        "email": "mehdi.karray@gmail.com",
        "telephone": "+216 26 654 321",
        "parsed_data": {
            "competences": [
                {"name": "Python"}, {"name": "scikit-learn"}, {"name": "Pandas"},
                {"name": "NumPy"}, {"name": "SQL"}, {"name": "Tableau"},
                {"name": "Power BI"}, {"name": "Git"},
            ],
            "formations": [{"diplome": "Licence Data Analytics", "niveau": 3, "etablissement": "ISI Ariana", "annee": 2023}],
            "experiences": [
                {"poste": "Data Analyst", "entreprise": "Telnet Consulting", "duree_mois": 18},
            ],
            "annees_experience": 1.5,
            "niveau_formation": 3,
            "langues": ["Arabe", "Français"],
            "localisation": "Ariana",
            "metadata": {"source": "seed_test"},
        },
    },

    # ── Frontend ──────────────────────────────────────────────────────────────
    {
        "nom": "Ines Chaabane",
        "email": "ines.chaabane@webdev.tn",
        "telephone": "+216 52 147 963",
        "parsed_data": {
            "competences": [
                {"name": "React"}, {"name": "TypeScript"}, {"name": "JavaScript"},
                {"name": "HTML"}, {"name": "CSS"}, {"name": "Tailwind"},
                {"name": "Git"}, {"name": "REST API"}, {"name": "Next.js"}, {"name": "Figma"},
            ],
            "formations": [{"diplome": "Licence Génie Logiciel", "niveau": 3, "etablissement": "FST Tunis", "annee": 2022}],
            "experiences": [
                {"poste": "Développeuse Frontend React", "entreprise": "AgenceWeb TN", "duree_mois": 30},
                {"poste": "Stagiaire UI Developer", "entreprise": "Vermeg", "duree_mois": 6},
            ],
            "annees_experience": 3,
            "niveau_formation": 3,
            "langues": ["Arabe", "Français", "Anglais"],
            "localisation": "Tunis",
            "metadata": {"source": "seed_test"},
        },
    },
    {
        "nom": "Yassine Ben Ali",
        "email": "yassine.benali@frontend.tn",
        "telephone": "+216 53 963 741",
        "parsed_data": {
            "competences": [
                {"name": "JavaScript"}, {"name": "HTML"}, {"name": "CSS"},
                {"name": "Vue.js"}, {"name": "Bootstrap"}, {"name": "Git"},
            ],
            "formations": [{"diplome": "BTS Développement Web", "niveau": 2, "etablissement": "ISET Sfax", "annee": 2023}],
            "experiences": [
                {"poste": "Développeur Web Junior", "entreprise": "Freelance", "duree_mois": 12},
            ],
            "annees_experience": 1,
            "niveau_formation": 2,
            "langues": ["Arabe", "Français"],
            "localisation": "Sfax",
            "metadata": {"source": "seed_test"},
        },
    },

    # ── DevOps ────────────────────────────────────────────────────────────────
    {
        "nom": "Bilel Gharbi",
        "email": "bilel.gharbi@devops.tn",
        "telephone": "+216 58 852 741",
        "parsed_data": {
            "competences": [
                {"name": "AWS"}, {"name": "Docker"}, {"name": "Kubernetes"},
                {"name": "Terraform"}, {"name": "Ansible"}, {"name": "Git"},
                {"name": "Linux"}, {"name": "CI/CD"}, {"name": "Prometheus"}, {"name": "Grafana"},
            ],
            "formations": [{"diplome": "Ingénieur Réseaux & Systèmes", "niveau": 5, "etablissement": "SUP'COM Tunis", "annee": 2019}],
            "experiences": [
                {"poste": "Ingénieur DevOps", "entreprise": "Telnet Cloud", "duree_mois": 48},
                {"poste": "Administrateur Systèmes", "entreprise": "Orange TN", "duree_mois": 24},
            ],
            "annees_experience": 6,
            "niveau_formation": 5,
            "langues": ["Arabe", "Français", "Anglais"],
            "localisation": "Tunis",
            "metadata": {"source": "seed_test"},
        },
    },

    # ── Hors domaine (test fiabilité) ─────────────────────────────────────────
    {
        "nom": "Rania Jebali",
        "email": "rania.jebali@marketing.tn",
        "telephone": "+216 50 963 741",
        "parsed_data": {
            "competences": [
                {"name": "Google Ads"}, {"name": "Facebook Ads"}, {"name": "SEO"},
                {"name": "Excel"}, {"name": "PowerPoint"}, {"name": "Canva"},
                {"name": "Community Management"}, {"name": "Google Analytics"},
            ],
            "formations": [{"diplome": "Licence Marketing", "niveau": 3, "etablissement": "Université Sousse", "annee": 2022}],
            "experiences": [
                {"poste": "Responsable Marketing Digital", "entreprise": "E-commerce TN", "duree_mois": 36},
            ],
            "annees_experience": 3,
            "niveau_formation": 3,
            "langues": ["Arabe", "Français", "Anglais"],
            "localisation": "Sousse",
            "metadata": {"source": "seed_test"},
        },
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Supprimer les candidats seedés avant d'insérer")
    args = parser.parse_args()

    db = SessionLocal()
    print("=" * 55)
    print("  3S TalentMatch — Seed Candidats")
    print("=" * 55)

    try:
        if args.reset:
            deleted = db.query(Candidate).filter(Candidate.cv_id.like(f"{SEED_TAG}%")).delete(synchronize_session=False)
            db.commit()
            print(f"[RESET] {deleted} candidat(s) seedés supprimés.\n")

        inserted = 0
        skipped  = 0

        for c in CANDIDATES:
            cv_id = f"{SEED_TAG}_{c['nom'].replace(' ', '_').lower()}"

            if db.query(Candidate).filter(Candidate.cv_id == cv_id).first():
                print(f"  ⏭  {c['nom']:<28} déjà en base")
                skipped += 1
                continue

            candidate = Candidate(
                id          = uuid.uuid4(),
                cv_id       = cv_id,
                nom         = c["nom"],
                email       = c["email"],
                telephone   = c["telephone"],
                parsed_data = c["parsed_data"],
                created_at  = datetime.now(timezone.utc),
            )
            db.add(candidate)
            print(f"  ✓  {c['nom']:<28} inséré")
            inserted += 1

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"\n[ERREUR] {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

    print()
    print("=" * 55)
    print(f"  {inserted} inséré(s)  |  {skipped} ignoré(s) (déjà en base)")
    print(f"  → Frontend : http://localhost:3000/candidates")
    print("=" * 55)


if __name__ == "__main__":
    main()
