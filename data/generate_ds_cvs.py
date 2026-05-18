"""
Scénario 2 — Offre Data Scientist / ML Engineer
Skills requises : Python, Machine Learning, TensorFlow, Scikit-learn, Pandas, SQL, Git, Docker
Expérience : 2 ans | Formation : Bac+5 | Localisation : Tunis

CV1 — Nour Bensalem     : Parfait Data Scientist  → attendu ~88-93%
CV2 — Mehdi Karray      : Bon match (pas TF/PyTorch, ML stats) → attendu ~65-72%
CV3 — Sara Mejri        : Backend Python (pas ML) → attendu ~38-48%
CV4 — Yassine Ben Ali   : Java Developer          → attendu ~20-30%
CV5 — Amira Chebbi      : Data Analyst BI/Excel   → attendu ~28-38%
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

OUT_DIR = os.path.join(os.path.dirname(__file__), "CVtest")
os.makedirs(OUT_DIR, exist_ok=True)

BLUE   = colors.HexColor("#1e40af")
GRAY   = colors.HexColor("#374151")
GREEN  = colors.HexColor("#15803d")
ORANGE = colors.HexColor("#c2410c")
PURPLE = colors.HexColor("#6d28d9")
TEAL   = colors.HexColor("#0f766e")

def make_styles():
    return {
        "name":    ParagraphStyle("name",    fontName="Helvetica-Bold", fontSize=17, textColor=BLUE, spaceAfter=2),
        "title":   ParagraphStyle("title",   fontName="Helvetica",      fontSize=11, textColor=GRAY, spaceAfter=5),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=10, textColor=BLUE, spaceBefore=10, spaceAfter=3),
        "body":    ParagraphStyle("body",    fontName="Helvetica",      fontSize=9,  textColor=GRAY, spaceAfter=3, leading=13),
        "bold":    ParagraphStyle("bold",    fontName="Helvetica-Bold", fontSize=9,  textColor=GRAY, spaceAfter=3),
    }

def hr():
    return HRFlowable(width="100%", thickness=0.8, color=BLUE, spaceAfter=4, spaceBefore=2)

def sec(title, S):
    return [Paragraph(title.upper(), S["section"]), hr()]

def build(filename, content):
    path = os.path.join(OUT_DIR, filename)
    S = make_styles()
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    doc.build(content(S))
    print(f"  Généré : {filename}")


# ─── CV1 — Nour Bensalem — Parfait Data Scientist ───────────────────────────
def cv1(S):
    return [
        Paragraph("Nour Bensalem", S["name"]),
        Paragraph("Data Scientist / ML Engineer", S["title"]),
        Paragraph("nour.bensalem@email.tn | +216 22 111 222 | Tunis, Tunisie", S["body"]),
        Spacer(1, 6),
        *sec("Profil", S),
        Paragraph("Data Scientist avec 3 ans d'expérience en machine learning et deep learning. "
                  "Maîtrise complète du stack : Python, TensorFlow, PyTorch, Scikit-learn, Pandas, SQL. "
                  "Spécialisée dans les modèles de classification, régression et NLP. "
                  "Déploiement de modèles ML en production via Docker et API REST.", S["body"]),
        *sec("Expérience Professionnelle", S),
        Paragraph("Data Scientist — InnoData Analytics, Tunis (2022 – 2025)", S["bold"]),
        Paragraph("Développement de modèles de machine learning avec Scikit-learn et TensorFlow. "
                  "Pipeline de données avec Pandas et NumPy. Entraînement de réseaux de neurones "
                  "pour la classification d'images. Déploiement Docker des modèles via API Flask/FastAPI. "
                  "Versioning des expériences avec MLflow et Git.", S["body"]),
        Paragraph("Data Scientist Junior — TechLab TN (2021 – 2022)", S["bold"]),
        Paragraph("Analyse exploratoire de données SQL et Python/Pandas. "
                  "Modèles de régression et clustering avec Scikit-learn. "
                  "Visualisation avec Matplotlib et Seaborn.", S["body"]),
        *sec("Formation", S),
        Paragraph("Master en Data Science et Intelligence Artificielle (Bac+5) — "
                  "École Nationale d'Ingénieurs de Tunis (2021)", S["body"]),
        *sec("Compétences Techniques", S),
        Paragraph("Langages : Python, SQL, R", S["body"]),
        Paragraph("ML / DL : Machine Learning, TensorFlow, PyTorch, Scikit-learn, Keras", S["body"]),
        Paragraph("Data : Pandas, NumPy, Matplotlib, Seaborn, Jupyter", S["body"]),
        Paragraph("MLOps : Docker, Git, MLflow, DVC, FastAPI", S["body"]),
        Paragraph("Bases de données : PostgreSQL, MySQL, MongoDB", S["body"]),
        Paragraph("Méthodes : Feature Engineering, Cross-validation, NLP, Computer Vision", S["body"]),
        *sec("Langues", S),
        Paragraph("Arabe (natif), Français (courant), Anglais (professionnel)", S["body"]),
    ]


# ─── CV2 — Mehdi Karray — Bon match (stats ML, pas TF/PyTorch) ──────────────
def cv2(S):
    return [
        Paragraph("Mehdi Karray", S["name"]),
        Paragraph("Data Scientist / Analyste Machine Learning", S["title"]),
        Paragraph("mehdi.karray@email.tn | +216 50 333 444 | Sfax, Tunisie", S["body"]),
        Spacer(1, 6),
        *sec("Profil", S),
        Paragraph("Data Scientist spécialisé en machine learning statistique. "
                  "2 ans d'expérience avec Python, Scikit-learn et Pandas. "
                  "Expertise en modèles de régression, arbres de décision et Random Forest. "
                  "Pas d'expérience avec TensorFlow ou PyTorch (deep learning peu utilisé dans mes projets). "
                  "Utilise SQL pour les requêtes et Git pour la gestion de version.", S["body"]),
        *sec("Expérience Professionnelle", S),
        Paragraph("Data Scientist — DataMinds, Sfax (2023 – 2025)", S["bold"]),
        Paragraph("Analyse de données clients avec Python et Pandas. "
                  "Modèles prédictifs avec Scikit-learn (Random Forest, XGBoost, SVM). "
                  "Requêtes SQL sur bases PostgreSQL. Reporting avec Matplotlib. "
                  "Gestion de code source avec Git.", S["body"]),
        Paragraph("Analyste Data — BankTech TN (2022 – 2023)", S["bold"]),
        Paragraph("Extraction et nettoyage de données SQL. "
                  "Modèles de scoring client avec Scikit-learn. "
                  "Visualisation des résultats avec Seaborn.", S["body"]),
        *sec("Formation", S),
        Paragraph("Diplôme d'Ingénieur en Statistiques et Informatique Décisionnelle (Bac+5) — "
                  "Institut National de Statistiques de Tunis (2022)", S["body"]),
        *sec("Compétences Techniques", S),
        Paragraph("Langages : Python, SQL, R", S["body"]),
        Paragraph("ML : Machine Learning, Scikit-learn, XGBoost, Random Forest, SVM", S["body"]),
        Paragraph("Data : Pandas, NumPy, Matplotlib, Seaborn", S["body"]),
        Paragraph("Outils : Git, Jupyter, Excel avancé", S["body"]),
        Paragraph("Bases de données : PostgreSQL, MySQL", S["body"]),
        *sec("Langues", S),
        Paragraph("Arabe (natif), Français (courant), Anglais (intermédiaire)", S["body"]),
    ]


# ─── CV3 — Sara Mejri — Backend Python (pas ML) ─────────────────────────────
def cv3(S):
    return [
        Paragraph("Sara Mejri", S["name"]),
        Paragraph("Développeuse Backend Python / API REST", S["title"]),
        Paragraph("sara.mejri@email.tn | +216 98 555 666 | Tunis, Tunisie", S["body"]),
        Spacer(1, 6),
        *sec("Profil", S),
        Paragraph("Développeuse backend Python avec 4 ans d'expérience sur FastAPI et Django. "
                  "Spécialiste des API REST, bases de données PostgreSQL et déploiement Docker. "
                  "Aucune expérience en machine learning ou data science. "
                  "Profil orienté développement logiciel et infrastructure.", S["body"]),
        *sec("Expérience Professionnelle", S),
        Paragraph("Développeuse Backend — WebAgency TN, Tunis (2021 – 2025)", S["bold"]),
        Paragraph("Développement d'APIs REST avec FastAPI et Python. "
                  "Gestion de bases de données PostgreSQL, ORM SQLAlchemy. "
                  "Containerisation Docker, pipeline CI/CD avec GitHub Actions. "
                  "Tests unitaires pytest, documentation OpenAPI/Swagger. Git.", S["body"]),
        *sec("Formation", S),
        Paragraph("Licence en Informatique (Bac+3) — Université de Tunis (2021)", S["body"]),
        *sec("Compétences Techniques", S),
        Paragraph("Langages : Python, SQL, JavaScript", S["body"]),
        Paragraph("Frameworks : FastAPI, Django, Flask", S["body"]),
        Paragraph("Bases de données : PostgreSQL, Redis, MySQL", S["body"]),
        Paragraph("DevOps : Docker, Git, GitHub Actions, Linux", S["body"]),
        Paragraph("Pas de compétences ML/Data Science", S["body"]),
        *sec("Langues", S),
        Paragraph("Arabe (natif), Français (courant), Anglais (professionnel)", S["body"]),
    ]


# ─── CV4 — Yassine Ben Ali — Java Developer ──────────────────────────────────
def cv4(S):
    return [
        Paragraph("Yassine Ben Ali", S["name"]),
        Paragraph("Développeur Java / Spring Boot", S["title"]),
        Paragraph("yassine.benali@email.tn | +216 55 777 888 | Tunis, Tunisie", S["body"]),
        Spacer(1, 6),
        *sec("Profil", S),
        Paragraph("Développeur Java senior avec 6 ans d'expérience sur Spring Boot et microservices. "
                  "Aucune compétence en Python, machine learning ou data science. "
                  "Expert en architecture Java enterprise, JPA, Hibernate, Oracle Database. "
                  "Profil backend Java pur.", S["body"]),
        *sec("Expérience Professionnelle", S),
        Paragraph("Développeur Java Senior — EnterpriseTech, Tunis (2019 – 2025)", S["bold"]),
        Paragraph("Développement microservices Spring Boot. JPA/Hibernate avec Oracle DB. "
                  "API REST Java. Maven, Jenkins CI/CD. Tests JUnit/Mockito. Git.", S["body"]),
        *sec("Formation", S),
        Paragraph("Diplôme d'Ingénieur en Génie Logiciel (Bac+5) — ESPRIT Tunis (2019)", S["body"]),
        *sec("Compétences Techniques", S),
        Paragraph("Langages : Java, SQL, XML", S["body"]),
        Paragraph("Frameworks : Spring Boot, Spring MVC, Hibernate, JPA", S["body"]),
        Paragraph("Bases de données : Oracle, MySQL, SQL Server", S["body"]),
        Paragraph("Outils : Maven, Jenkins, Git, Docker (basique)", S["body"]),
        *sec("Langues", S),
        Paragraph("Arabe (natif), Français (courant), Anglais (professionnel)", S["body"]),
    ]


# ─── CV5 — Amira Chebbi — Data Analyst BI/Excel ──────────────────────────────
def cv5(S):
    return [
        Paragraph("Amira Chebbi", S["name"]),
        Paragraph("Data Analyst / Business Intelligence", S["title"]),
        Paragraph("amira.chebbi@email.tn | +216 20 999 000 | Tunis, Tunisie", S["body"]),
        Spacer(1, 6),
        *sec("Profil", S),
        Paragraph("Data Analyst avec 3 ans d'expérience en Business Intelligence. "
                  "Spécialiste Power BI, Tableau et Excel avancé. "
                  "Maîtrise SQL pour l'extraction de données. Pas de compétences en machine learning "
                  "ou programmation Python avancée. Profil analytique et reporting.", S["body"]),
        *sec("Expérience Professionnelle", S),
        Paragraph("Data Analyst — BankFinance TN, Tunis (2022 – 2025)", S["bold"]),
        Paragraph("Création de tableaux de bord Power BI et Tableau. "
                  "Requêtes SQL complexes pour extraction KPI. "
                  "Reporting Excel avancé avec macros VBA. "
                  "Analyse statistique descriptive. Présentation résultats.", S["body"]),
        *sec("Formation", S),
        Paragraph("Licence en Gestion et Systèmes d'Information (Bac+3) — "
                  "Institut des Hautes Études Commerciales, Tunis (2022)", S["body"]),
        *sec("Compétences Techniques", S),
        Paragraph("BI : Power BI, Tableau, Qlik Sense", S["body"]),
        Paragraph("Data : Excel avancé, VBA, SQL, Access", S["body"]),
        Paragraph("Langages : SQL, un peu Python (pandas basique)", S["body"]),
        Paragraph("Outils : SAP, Microsoft Office 365", S["body"]),
        *sec("Langues", S),
        Paragraph("Arabe (natif), Français (courant), Anglais (intermédiaire)", S["body"]),
    ]


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Génération des CVs Data Science...")
    build("DS_CV1_NourBensalem_Parfait.pdf",    cv1)
    build("DS_CV2_MehdiKarray_BonMatch.pdf",    cv2)
    build("DS_CV3_SaraMejri_BackendPython.pdf", cv3)
    build("DS_CV4_YassineBenAli_Java.pdf",      cv4)
    build("DS_CV5_AmiraChebbi_DataAnalyst.pdf", cv5)
    print(f"\nTous les CVs sont dans : {OUT_DIR}")
    print("\nSCENARIO DE TEST :")
    print("=" * 55)
    print("Offre : Data Scientist / ML Engineer — 3S Analytics")
    print("Skills : Python, Machine Learning, TensorFlow,")
    print("         Scikit-learn, Pandas, SQL, Git, Docker")
    print("Experience : 2 ans | Formation : Bac+5")
    print()
    print("Resultats attendus :")
    print("  CV1 — Nour Bensalem   : ~88-93% (parfait : tous les skills ML)")
    print("  CV2 — Mehdi Karray    : ~62-72% (bon : ML stats mais pas TF/PyTorch)")
    print("  CV3 — Sara Mejri      : ~35-45% (partiel : Python/Docker mais pas ML)")
    print("  CV4 — Yassine Ben Ali : ~18-28% (mauvais : Java, zero ML)")
    print("  CV5 — Amira Chebbi    : ~28-38% (partiel : SQL/data mais pas code ML)")
