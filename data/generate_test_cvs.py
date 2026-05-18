"""
Génère 5 CVs PDF de test avec des profils variés
pour démontrer le scoring TalentMatch.

Offre cible : Ingénieur Backend Python / FastAPI
Skills requises : Python, FastAPI, PostgreSQL, Docker, Git, REST API, Redis, SQLAlchemy
Expérience : 3 ans | Formation : Bac+5 | Localisation : Tunis
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUT_DIR = os.path.join(os.path.dirname(__file__), "CVtest")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Palette couleurs par profil ───────────────────────────────────────────────
BLUE   = colors.HexColor("#1e40af")
GRAY   = colors.HexColor("#374151")
LIGHT  = colors.HexColor("#f3f4f6")
GREEN  = colors.HexColor("#15803d")
RED    = colors.HexColor("#b91c1c")
ORANGE = colors.HexColor("#c2410c")

def make_styles():
    base = getSampleStyleSheet()
    return {
        "name":    ParagraphStyle("name",    fontName="Helvetica-Bold",  fontSize=18, textColor=BLUE,  spaceAfter=2),
        "title":   ParagraphStyle("title",   fontName="Helvetica",       fontSize=11, textColor=GRAY,  spaceAfter=6),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold",  fontSize=10, textColor=BLUE,  spaceBefore=10, spaceAfter=4),
        "body":    ParagraphStyle("body",    fontName="Helvetica",       fontSize=9,  textColor=GRAY,  spaceAfter=3, leading=13),
        "small":   ParagraphStyle("small",   fontName="Helvetica",       fontSize=8,  textColor=colors.HexColor("#6b7280"), spaceAfter=2),
        "bold":    ParagraphStyle("bold",    fontName="Helvetica-Bold",  fontSize=9,  textColor=GRAY,  spaceAfter=3),
    }

def hr(color=BLUE, thickness=1):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=4, spaceBefore=2)

def section(title, styles):
    return [Paragraph(title.upper(), styles["section"]), hr(BLUE, 0.8)]

def build_cv(filename, data):
    path = os.path.join(OUT_DIR, filename)
    doc  = SimpleDocTemplate(path, pagesize=A4,
                             leftMargin=2*cm, rightMargin=2*cm,
                             topMargin=2*cm,  bottomMargin=2*cm)
    S = make_styles()
    story = []

    # En-tête
    story.append(Paragraph(data["nom"], S["name"]))
    story.append(Paragraph(data["poste"], S["title"]))
    contact = f"{data['email']}  |  {data['tel']}  |  {data['ville']}"
    story.append(Paragraph(contact, S["small"]))
    story.append(hr(BLUE, 1.5))

    # Résumé
    story += section("Profil", S)
    story.append(Paragraph(data["resume"], S["body"]))

    # Expérience
    story += section("Expérience Professionnelle", S)
    for exp in data["experiences"]:
        story.append(Paragraph(f"<b>{exp['poste']}</b> — {exp['entreprise']} ({exp['dates']})", S["bold"]))
        story.append(Paragraph(exp["desc"], S["body"]))
        story.append(Spacer(1, 3))

    # Formation
    story += section("Formation", S)
    for f in data["formations"]:
        story.append(Paragraph(f"<b>{f['diplome']}</b> — {f['ecole']} ({f['annee']})", S["bold"]))

    # Compétences
    story += section("Compétences Techniques", S)
    for cat, skills in data["competences"].items():
        story.append(Paragraph(f"<b>{cat} :</b>  {skills}", S["body"]))

    # Langues
    story += section("Langues", S)
    story.append(Paragraph(data["langues"], S["body"]))

    doc.build(story)
    print(f"  Généré : {filename}")
    return path


# ════════════════════════════════════════════════════════════════════
# CV 1 — EXCELLENT MATCH (~85-90%)
# Profil : tous les skills requis, 4 ans exp, Bac+5, Tunis
# ════════════════════════════════════════════════════════════════════
cv1 = {
    "nom":    "Aymen Belhaj",
    "poste":  "Ingénieur Backend Python / FastAPI",
    "email":  "aymen.belhaj@email.tn",
    "tel":    "+216 55 123 456",
    "ville":  "Tunis, Tunisie",
    "resume": (
        "Ingénieur backend avec 4 ans d'expérience spécialisé en Python et FastAPI. "
        "Maîtrise complète du stack moderne : FastAPI, PostgreSQL, Redis, Docker, SQLAlchemy. "
        "Passionné par les architectures REST API et le déploiement continu. "
        "Expérience sur des projets à fort trafic en environnement Agile."
    ),
    "experiences": [
        {
            "poste":     "Ingénieur Backend Senior",
            "entreprise": "DataFlow Solutions",
            "dates":     "2022 – 2026",
            "desc": (
                "Développement d'APIs REST avec FastAPI et Python. Gestion de la base de données "
                "PostgreSQL via SQLAlchemy. Mise en place de cache Redis pour les endpoints à fort trafic. "
                "Containerisation Docker et pipeline CI/CD GitLab. Revue de code et mentorat junior."
            )
        },
        {
            "poste":     "Développeur Python",
            "entreprise": "TechStartup TN",
            "dates":     "2020 – 2022",
            "desc": (
                "Développement backend Python/FastAPI. Intégration PostgreSQL, utilisation de Git "
                "pour la gestion de version. Participation aux sprints Agile/Scrum."
            )
        }
    ],
    "formations": [
        {"diplome": "Diplôme d'Ingénieur en Informatique (Bac+5)", "ecole": "École Polytechnique de Tunis", "annee": "2020"}
    ],
    "competences": {
        "Langages":     "Python, SQL",
        "Frameworks":   "FastAPI, SQLAlchemy, Pydantic",
        "Bases données": "PostgreSQL, Redis, MySQL",
        "DevOps":       "Docker, Git, GitLab CI/CD, Linux",
        "APIs":         "REST API, OpenAPI/Swagger",
        "Méthodes":     "Agile, Scrum, Tests unitaires (pytest)"
    },
    "langues": "Arabe (natif), Français (courant), Anglais (professionnel)"
}

# ════════════════════════════════════════════════════════════════════
# CV 2 — BON MATCH (~65-70%)
# Profil : Python/Django (pas FastAPI), PostgreSQL, Docker, Git — 2 ans, Bac+5, Tunis
# ════════════════════════════════════════════════════════════════════
cv2 = {
    "nom":    "Sonia Trabelsi",
    "poste":  "Développeuse Web Python / Django",
    "email":  "sonia.trabelsi@gmail.com",
    "tel":    "+216 22 987 654",
    "ville":  "Tunis, Tunisie",
    "resume": (
        "Développeuse web backend avec 2 ans d'expérience en Python et Django. "
        "Bonne maîtrise de PostgreSQL, Git et Docker. Habituée aux environnements REST API. "
        "En cours d'apprentissage de FastAPI et SQLAlchemy pour évoluer vers une architecture plus moderne."
    ),
    "experiences": [
        {
            "poste":     "Développeuse Backend",
            "entreprise": "WebAgency Tunis",
            "dates":     "2024 – 2026",
            "desc": (
                "Développement d'applications web avec Python Django et Django REST Framework. "
                "Base de données PostgreSQL. Déploiement via Docker. Versioning avec Git/GitHub."
            )
        },
        {
            "poste":     "Stagiaire Développeur",
            "entreprise": "StartupTN",
            "dates":     "2023 – 2024",
            "desc": (
                "Développement d'une API REST en Python. Intégration PostgreSQL. Tests avec pytest."
            )
        }
    ],
    "formations": [
        {"diplome": "Master en Génie Logiciel (Bac+5)", "ecole": "ENSI Tunis", "annee": "2023"}
    ],
    "competences": {
        "Langages":     "Python, JavaScript, SQL",
        "Frameworks":   "Django, Django REST Framework, Flask",
        "Bases données": "PostgreSQL, SQLite",
        "DevOps":       "Docker, Git, GitHub",
        "APIs":         "REST API, JSON",
        "Méthodes":     "Agile, Tests unitaires"
    },
    "langues": "Arabe (natif), Français (courant), Anglais (intermédiaire)"
}

# ════════════════════════════════════════════════════════════════════
# CV 3 — MATCH PARTIEL (~45-55%)
# Profil : Python junior (1 an), MySQL pas PostgreSQL, pas Docker — Bac+3, Sfax
# ════════════════════════════════════════════════════════════════════
cv3 = {
    "nom":    "Omar Hamdi",
    "poste":  "Développeur Junior Python",
    "email":  "omar.hamdi@yahoo.fr",
    "tel":    "+216 98 456 123",
    "ville":  "Sfax, Tunisie",
    "resume": (
        "Jeune développeur avec 1 an d'expérience en Python. "
        "J'ai travaillé sur des petits projets web avec Flask et MySQL. "
        "Je maîtrise Git et les bases du développement REST. "
        "Motivé pour apprendre Docker, PostgreSQL et les frameworks modernes."
    ),
    "experiences": [
        {
            "poste":     "Développeur Python Junior",
            "entreprise": "WebDev Sfax",
            "dates":     "2025 – 2026",
            "desc": (
                "Développement de petites APIs REST avec Python et Flask. "
                "Base de données MySQL. Gestion de version avec Git."
            )
        }
    ],
    "formations": [
        {"diplome": "Licence en Informatique (Bac+3)", "ecole": "Université de Sfax", "annee": "2024"}
    ],
    "competences": {
        "Langages":     "Python, HTML, CSS, JavaScript",
        "Frameworks":   "Flask, Bootstrap",
        "Bases données": "MySQL, SQLite",
        "DevOps":       "Git",
        "APIs":         "REST API (basique)",
        "Méthodes":     "Développement itératif"
    },
    "langues": "Arabe (natif), Français (intermédiaire), Anglais (débutant)"
}

# ════════════════════════════════════════════════════════════════════
# CV 4 — MAUVAIS MATCH (~25-35%)
# Profil : Java/Spring Boot — stack complètement différent — 3 ans, Bac+5, Tunis
# ════════════════════════════════════════════════════════════════════
cv4 = {
    "nom":    "Karim Mansouri",
    "poste":  "Ingénieur Backend Java / Spring Boot",
    "email":  "karim.mansouri@outlook.com",
    "tel":    "+216 25 741 852",
    "ville":  "Tunis, Tunisie",
    "resume": (
        "Ingénieur backend avec 3 ans d'expérience en Java et Spring Boot. "
        "Maîtrise des architectures microservices, JPA/Hibernate, MySQL et MongoDB. "
        "Déploiement sur AWS et utilisation de Docker Kubernetes. "
        "Expérience en développement d'APIs REST avec Spring Framework."
    ),
    "experiences": [
        {
            "poste":     "Développeur Backend Java",
            "entreprise": "Banque de Tunisie — DSI",
            "dates":     "2023 – 2026",
            "desc": (
                "Développement de microservices Java Spring Boot. ORM avec JPA/Hibernate. "
                "Base de données Oracle et MySQL. Déploiement Docker sur AWS. Git/Jenkins CI/CD."
            )
        },
        {
            "poste":     "Développeur Java Junior",
            "entreprise": "IT Consulting TN",
            "dates":     "2021 – 2023",
            "desc": (
                "Applications Java EE, Spring MVC. Base de données MySQL. Expositions REST avec JAX-RS."
            )
        }
    ],
    "formations": [
        {"diplome": "Ingénieur en Informatique (Bac+5)", "ecole": "INSAT Tunis", "annee": "2021"}
    ],
    "competences": {
        "Langages":     "Java, SQL, TypeScript",
        "Frameworks":   "Spring Boot, Spring MVC, JPA/Hibernate, Angular",
        "Bases données": "MySQL, Oracle, MongoDB",
        "DevOps":       "Docker, Kubernetes, Jenkins, Git, AWS",
        "APIs":         "REST API, SOAP, Microservices",
        "Méthodes":     "Agile/Scrum, TDD"
    },
    "langues": "Arabe (natif), Français (courant), Anglais (courant)"
}

# ════════════════════════════════════════════════════════════════════
# CV 5 — HORS DOMAINE (~20-25%)
# Profil : Marketing digital — aucune compétence technique backend
# ════════════════════════════════════════════════════════════════════
cv5 = {
    "nom":    "Rania Jebali",
    "poste":  "Chargée de Marketing Digital",
    "email":  "rania.jebali@gmail.com",
    "tel":    "+216 50 963 741",
    "ville":  "Sousse, Tunisie",
    "resume": (
        "Spécialiste marketing digital avec 3 ans d'expérience en gestion de campagnes "
        "Google Ads, Facebook Ads et SEO. Maîtrise des outils d'analyse web : Google Analytics, "
        "SEMrush, Hotjar. Expérience en création de contenu et community management. "
        "Bonne maîtrise d'Excel et PowerPoint pour le reporting."
    ),
    "experiences": [
        {
            "poste":     "Responsable Marketing Digital",
            "entreprise": "E-commerce Tunisie",
            "dates":     "2023 – 2026",
            "desc": (
                "Gestion des campagnes publicitaires Google Ads et Facebook Ads. "
                "Analyse des performances via Google Analytics. Optimisation SEO. "
                "Création de contenu pour les réseaux sociaux. Reporting Excel hebdomadaire."
            )
        },
        {
            "poste":     "Community Manager",
            "entreprise": "Agence Digital Sousse",
            "dates":     "2022 – 2023",
            "desc": (
                "Animation des réseaux sociaux (Instagram, Facebook, LinkedIn). "
                "Création de visuels Canva. Analyse statistiques de performance."
            )
        }
    ],
    "formations": [
        {"diplome": "Licence en Marketing (Bac+3)", "ecole": "Université de Sousse", "annee": "2022"}
    ],
    "competences": {
        "Marketing":     "Google Ads, Facebook Ads, SEO, SEM, Email marketing",
        "Analyse":       "Google Analytics, SEMrush, Hotjar, Data Studio",
        "Création":      "Canva, Adobe Photoshop (bases), Capcut",
        "Bureautique":   "Excel, PowerPoint, Word",
        "Réseaux":       "Instagram, Facebook, LinkedIn, TikTok",
        "Langues":       "Rédaction FR/AR/EN"
    },
    "langues": "Arabe (natif), Français (courant), Anglais (intermédiaire)"
}

print("Génération des CVs PDF...")
build_cv("CV1_AymenBelhaj_ExcellentMatch.pdf",  cv1)
build_cv("CV2_SoniaTrabelsi_BonMatch.pdf",       cv2)
build_cv("CV3_OmarHamdi_MatchPartiel.pdf",        cv3)
build_cv("CV4_KarimMansouri_MauvaisMatch.pdf",    cv4)
build_cv("CV5_RaniaJebali_HorsDomaine.pdf",       cv5)

print(f"\nTous les CVs sont dans : {OUT_DIR}")
print("""
SCENARIO DE TEST :
==================
Offre : Ingénieur Backend Python / FastAPI — 3S Informatique, Tunis
Skills requises : Python, FastAPI, PostgreSQL, Docker, Git, REST API, Redis, SQLAlchemy
Experience : 3 ans | Formation : Bac+5

Résultats attendus :
  CV1 — Aymen Belhaj   : ~85-90%  (excellent — tous les skills, 4 ans, Bac+5, Tunis)
  CV2 — Sonia Trabelsi : ~60-70%  (bon — Python/PostgreSQL/Docker mais Django pas FastAPI)
  CV3 — Omar Hamdi     : ~35-45%  (partiel — junior, MySQL pas PostgreSQL, pas Docker)
  CV4 — Karim Mansouri : ~25-35%  (mauvais — Java/Spring Boot, stack différent)
  CV5 — Rania Jebali   : ~20-25%  (hors domaine — Marketing, aucune compétence backend)
""")
