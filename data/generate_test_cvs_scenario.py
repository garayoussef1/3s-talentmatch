"""
Génère 8 CVs PDF pour tester le matching sur la plateforme TalentMatch.

Scénario : Offre "Développeur React Senior" à Paris
  - CV1  Ahmed Benali       : Dev React parfait               → score attendu ~0.75
  - CV2  Sophie Leclerc     : Dev React junior                → score attendu ~0.60
  - CV3  Thomas Nguyen      : Dev Vue.js / Angular            → score attendu ~0.52
  - CV4  Maria Garcia       : Fullstack React+Node 6 ans      → score attendu ~0.70
  - CV5  Karim Osman        : Dev Python Backend              → score attendu ~0.38
  - CV6  Lucie Fontaine     : UX/UI Designer                  → score attendu ~0.32
  - CV7  Jean Dupont        : Comptable Senior                → score attendu ~0.10
  - CV8  Amina Diallo       : Infirmière                      → score attendu ~0.08

Usage :
    cd c:/Users/youssef/Desktop/3s-talentmatch
    .venv-10/Scripts/python data/generate_test_cvs_scenario.py
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from pathlib import Path
import os

OUT_DIR = Path(__file__).parent / "test_cvs_scenario"
OUT_DIR.mkdir(exist_ok=True)

W, H = A4

# ── Palette couleurs ──────────────────────────────────────────────────────────
BLUE      = colors.HexColor("#1A56DB")
DARK      = colors.HexColor("#1F2A37")
GRAY      = colors.HexColor("#6B7280")
LGRAY     = colors.HexColor("#F3F4F6")
WHITE     = colors.white
ACCENT    = colors.HexColor("#3B82F6")


def make_cv(filename, data):
    """Génère un CV PDF depuis un dict de données."""
    path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("name", fontSize=22, textColor=WHITE,
                                 fontName="Helvetica-Bold", leading=26)
    title_style = ParagraphStyle("title", fontSize=13, textColor=colors.HexColor("#BFDBFE"),
                                  fontName="Helvetica", leading=16)
    section_style = ParagraphStyle("section", fontSize=11, textColor=BLUE,
                                    fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle("body", fontSize=9.5, textColor=DARK,
                                 fontName="Helvetica", leading=14, spaceAfter=3)
    bullet_style = ParagraphStyle("bullet", fontSize=9.5, textColor=DARK,
                                   fontName="Helvetica", leading=14,
                                   leftIndent=12, bulletIndent=0, spaceAfter=2)
    label_style = ParagraphStyle("label", fontSize=8.5, textColor=GRAY,
                                  fontName="Helvetica", leading=12)
    tag_style = ParagraphStyle("tag", fontSize=9, textColor=BLUE,
                                fontName="Helvetica-Bold", leading=12)

    story = []

    # ── HEADER ─────────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(data["nom"], name_style),
        ""
    ]]
    header_table = Table(header_data, colWidths=[14*cm, 4*cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE),
        ("PADDING", (0, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(header_table)

    # Titre + contact sous le header
    info_data = [[
        Paragraph(data["titre"], ParagraphStyle("t", fontSize=12, textColor=BLUE,
                                                  fontName="Helvetica-Bold")),
        Paragraph(data.get("email","") + " · " + data.get("tel","") + " · " + data.get("ville",""),
                  ParagraphStyle("c", fontSize=8.5, textColor=GRAY, fontName="Helvetica"))
    ]]
    info_table = Table(info_data, colWidths=[10*cm, 8*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LGRAY),
        ("PADDING", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))

    # ── RÉSUMÉ ──────────────────────────────────────────────────────────────────
    if data.get("resume"):
        story.append(Paragraph("Profil", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))
        story.append(Paragraph(data["resume"], body_style))
        story.append(Spacer(1, 0.3*cm))

    # ── EXPÉRIENCES ─────────────────────────────────────────────────────────────
    if data.get("experiences"):
        story.append(Paragraph("Expériences professionnelles", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))
        for exp in data["experiences"]:
            story.append(Paragraph(
                f"<b>{exp['poste']}</b> — {exp['entreprise']}",
                ParagraphStyle("ep", fontSize=10, textColor=DARK,
                                fontName="Helvetica-Bold", leading=14)
            ))
            story.append(Paragraph(
                f"{exp['periode']} · {exp.get('lieu','')}",
                label_style
            ))
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"• {bullet}", bullet_style))
            story.append(Spacer(1, 0.2*cm))

    # ── FORMATION ───────────────────────────────────────────────────────────────
    if data.get("formations"):
        story.append(Paragraph("Formation", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))
        for f in data["formations"]:
            story.append(Paragraph(
                f"<b>{f['diplome']}</b> — {f['ecole']}",
                ParagraphStyle("fp", fontSize=10, textColor=DARK,
                                fontName="Helvetica-Bold", leading=14)
            ))
            story.append(Paragraph(f['annee'], label_style))
            story.append(Spacer(1, 0.15*cm))

    # ── COMPÉTENCES ─────────────────────────────────────────────────────────────
    if data.get("competences"):
        story.append(Paragraph("Compétences techniques", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))
        # Grouper par catégorie
        for cat, skills in data["competences"].items():
            row = [[
                Paragraph(f"<b>{cat}</b>", label_style),
                Paragraph(" · ".join(skills), body_style)
            ]]
            t = Table(row, colWidths=[3.5*cm, 14*cm])
            t.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("PADDING", (0,0), (-1,-1), 3),
            ]))
            story.append(t)

    # ── LANGUES ─────────────────────────────────────────────────────────────────
    if data.get("langues"):
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("Langues", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))
        story.append(Paragraph(" · ".join(data["langues"]), body_style))

    doc.build(story)
    print(f"  OK  {path.name}")
    return path


# ── DONNÉES DES 8 CVS ─────────────────────────────────────────────────────────

CVS = [

    # ── CV1 : Dev React parfait ────────────────────────────────────────────────
    ("cv1_ahmed_benali_react_senior.pdf", {
        "nom": "Ahmed Benali",
        "titre": "Développeur React Senior",
        "email": "ahmed.benali@email.com", "tel": "06 12 34 56 78", "ville": "Paris",
        "resume": (
            "Développeur frontend passionné avec 5 ans d'expérience sur React et l'écosystème "
            "JavaScript. Spécialisé dans les architectures de grande échelle avec TypeScript, "
            "Redux et Jest. Habitué aux méthodologies Agile et aux revues de code rigoureuses."
        ),
        "experiences": [
            {"poste": "Développeur React Senior", "entreprise": "Fintech Startup",
             "periode": "2021 – Présent", "lieu": "Paris",
             "bullets": [
                 "Développement d'interfaces React/TypeScript pour une app de paiement (500k users)",
                 "Mise en place de Redux Toolkit et optimisation des performances (+40% LCP)",
                 "Tests unitaires et E2E avec Jest et Cypress, couverture 85%",
                 "Code review hebdomadaire, mentoring de 2 développeurs juniors",
             ]},
            {"poste": "Développeur Frontend React", "entreprise": "Agence Web Digitale",
             "periode": "2019 – 2021", "lieu": "Lyon",
             "bullets": [
                 "Intégration de maquettes Figma en composants React réutilisables",
                 "Développement d'APIs REST avec Node.js / Express",
                 "Migration d'une app jQuery vers React 17",
             ]},
        ],
        "formations": [
            {"diplome": "Master Informatique — Génie Logiciel", "ecole": "INSA Lyon", "annee": "2019"},
            {"diplome": "Licence Informatique", "ecole": "Université Paris-Saclay", "annee": "2017"},
        ],
        "competences": {
            "Frontend":    ["React 18", "TypeScript", "Redux Toolkit", "Next.js", "Tailwind CSS"],
            "Tests":       ["Jest", "React Testing Library", "Cypress", "Playwright"],
            "Backend":     ["Node.js", "Express", "REST API", "GraphQL"],
            "DevOps":      ["Git", "Docker", "CI/CD GitHub Actions", "Webpack", "Vite"],
        },
        "langues": ["Français (natif)", "Anglais (C1)", "Arabe (natif)"],
    }),

    # ── CV2 : Dev React junior ─────────────────────────────────────────────────
    ("cv2_sophie_leclerc_react_junior.pdf", {
        "nom": "Sophie Leclerc",
        "titre": "Développeuse React — 2 ans d'expérience",
        "email": "sophie.leclerc@email.com", "tel": "06 23 45 67 89", "ville": "Paris",
        "resume": (
            "Développeuse frontend motivée avec 2 ans d'expérience sur React et JavaScript. "
            "Maîtrise des bases de TypeScript et des hooks React. Curieuse et force de proposition."
        ),
        "experiences": [
            {"poste": "Développeuse Frontend React", "entreprise": "StartupTech",
             "periode": "2022 – Présent", "lieu": "Paris",
             "bullets": [
                 "Développement de composants React pour un dashboard SaaS",
                 "Intégration d'APIs REST, gestion de l'état avec useState/useContext",
                 "Participation aux sprints Agile, daily standup",
             ]},
            {"poste": "Stage Développement Web", "entreprise": "Agence Créative",
             "periode": "2022 (6 mois)", "lieu": "Bordeaux",
             "bullets": [
                 "Création de landing pages en HTML/CSS/JavaScript",
                 "Premiers projets React avec Create React App",
             ]},
        ],
        "formations": [
            {"diplome": "Licence Pro Développement Web", "ecole": "IUT Paris Rives de Seine", "annee": "2022"},
        ],
        "competences": {
            "Frontend":    ["React", "JavaScript", "TypeScript (notions)", "HTML5", "CSS3", "Sass"],
            "Outils":      ["Git", "VS Code", "Figma", "Postman", "npm"],
            "Bases":       ["REST API", "Jest (notions)", "Responsive Design", "Bootstrap"],
        },
        "langues": ["Français (natif)", "Anglais (B2)"],
    }),

    # ── CV3 : Dev Vue.js / Angular ─────────────────────────────────────────────
    ("cv3_thomas_nguyen_vuejs.pdf", {
        "nom": "Thomas Nguyen",
        "titre": "Développeur Frontend Vue.js / Angular",
        "email": "thomas.nguyen@email.com", "tel": "06 34 56 78 90", "ville": "Lyon",
        "resume": (
            "Développeur frontend avec 4 ans d'expérience, principalement sur Vue.js 3 et Angular. "
            "Bonne maîtrise de JavaScript/TypeScript et des patterns frontend modernes. "
            "Notions de React. Cherche à approfondir React sur un nouveau poste."
        ),
        "experiences": [
            {"poste": "Développeur Frontend Vue.js", "entreprise": "E-commerce Leader",
             "periode": "2021 – Présent", "lieu": "Lyon",
             "bullets": [
                 "Développement d'interfaces Vue 3 / Composition API pour un site e-commerce",
                 "State management avec Pinia, routing Vue Router",
                 "Tests avec Vitest, intégration Storybook",
             ]},
            {"poste": "Développeur Angular", "entreprise": "ESN Nationale",
             "periode": "2020 – 2021", "lieu": "Paris",
             "bullets": [
                 "Applications Angular 12 pour clients bancaires",
                 "RxJS, NgRx, Angular Material",
             ]},
        ],
        "formations": [
            {"diplome": "Licence Informatique", "ecole": "Université Lyon 1", "annee": "2020"},
        ],
        "competences": {
            "Frontend":    ["Vue.js 3", "Angular", "JavaScript", "TypeScript", "HTML5", "CSS3"],
            "Etat/Tests":  ["Pinia", "Vuex", "NgRx", "Vitest", "Jasmine"],
            "Notions":     ["React (bases)", "Node.js", "REST API"],
            "Outils":      ["Git", "Docker", "Vite", "Webpack"],
        },
        "langues": ["Français (natif)", "Anglais (B2)", "Vietnamien (natif)"],
    }),

    # ── CV4 : Fullstack React/Node 6 ans ──────────────────────────────────────
    ("cv4_maria_garcia_fullstack.pdf", {
        "nom": "Maria Garcia",
        "titre": "Développeuse Fullstack React / Node.js",
        "email": "maria.garcia@email.com", "tel": "06 45 67 89 01", "ville": "Paris",
        "resume": (
            "Développeuse fullstack avec 6 ans d'expérience, maîtrise complète de React "
            "côté frontend et Node.js / Express côté backend. Habituée à des projets complexes, "
            "architectures microservices, déploiement cloud AWS."
        ),
        "experiences": [
            {"poste": "Lead Développeuse Fullstack", "entreprise": "Scale-up SaaS B2B",
             "periode": "2020 – Présent", "lieu": "Paris",
             "bullets": [
                 "Architecture et développement d'une plateforme React/TypeScript (200k utilisateurs)",
                 "Backend Node.js/Express avec PostgreSQL, Redis, architecture microservices",
                 "Déploiement AWS (ECS, RDS, CloudFront), CI/CD Jenkins",
                 "Management technique de 3 développeurs juniors",
             ]},
            {"poste": "Développeuse React & Node.js", "entreprise": "Agence Tech",
             "periode": "2018 – 2020", "lieu": "Barcelone",
             "bullets": [
                 "Applications React avec Context API et Redux",
                 "APIs REST Node.js/Express pour clients PME",
             ]},
        ],
        "formations": [
            {"diplome": "Master Ingénierie Logicielle", "ecole": "Universidad Politécnica de Madrid", "annee": "2018"},
        ],
        "competences": {
            "Frontend":    ["React 18", "TypeScript", "Redux", "Next.js", "Tailwind CSS", "Storybook"],
            "Backend":     ["Node.js", "Express", "PostgreSQL", "Redis", "REST API", "GraphQL"],
            "Cloud/DevOps": ["AWS (ECS, RDS, S3)", "Docker", "CI/CD", "Git", "Terraform"],
            "Tests":       ["Jest", "Supertest", "Cypress", "TDD"],
        },
        "langues": ["Français (C1)", "Espagnol (natif)", "Anglais (C1)"],
    }),

    # ── CV5 : Dev Python Backend ───────────────────────────────────────────────
    ("cv5_karim_osman_python_backend.pdf", {
        "nom": "Karim Osman",
        "titre": "Développeur Backend Python / Django",
        "email": "karim.osman@email.com", "tel": "06 56 78 90 12", "ville": "Paris",
        "resume": (
            "Développeur backend Python avec 3 ans d'expérience sur Django et FastAPI. "
            "Expertise en conception d'APIs REST, bases de données PostgreSQL et déploiement Docker. "
            "Pas d'expérience frontend React mais motivé pour évoluer vers le fullstack."
        ),
        "experiences": [
            {"poste": "Développeur Backend Python", "entreprise": "HealthTech",
             "periode": "2021 – Présent", "lieu": "Paris",
             "bullets": [
                 "Développement d'APIs REST avec FastAPI et Django REST Framework",
                 "Modélisation de bases de données PostgreSQL complexes",
                 "Intégration de services tiers (Stripe, Twilio, AWS S3)",
                 "Tests automatisés avec pytest, couverture 90%",
             ]},
            {"poste": "Développeur Python Junior", "entreprise": "Startup IA",
             "periode": "2020 – 2021", "lieu": "Toulouse",
             "bullets": [
                 "Scripts d'automatisation Python, traitement de données",
                 "APIs Flask pour des modèles de machine learning",
             ]},
        ],
        "formations": [
            {"diplome": "Licence Informatique", "ecole": "Université Paul Sabatier Toulouse", "annee": "2020"},
        ],
        "competences": {
            "Backend":     ["Python", "Django", "FastAPI", "Flask", "REST API"],
            "Bases de données": ["PostgreSQL", "MySQL", "Redis", "SQLAlchemy"],
            "DevOps":      ["Docker", "Git", "Linux", "CI/CD", "AWS Lambda"],
            "Tests":       ["pytest", "unittest", "Postman"],
        },
        "langues": ["Français (natif)", "Arabe (natif)", "Anglais (B2)"],
    }),

    # ── CV6 : UX/UI Designer ──────────────────────────────────────────────────
    ("cv6_lucie_fontaine_uxui.pdf", {
        "nom": "Lucie Fontaine",
        "titre": "UX/UI Designer",
        "email": "lucie.fontaine@email.com", "tel": "06 67 89 01 23", "ville": "Paris",
        "resume": (
            "Designer UX/UI avec 4 ans d'expérience, spécialisée dans la conception "
            "d'interfaces web et mobile centrées utilisateur. Maîtrise de Figma et du Design System. "
            "Notions de HTML/CSS pour communiquer avec les développeurs frontend."
        ),
        "experiences": [
            {"poste": "UX/UI Designer Senior", "entreprise": "Product Studio",
             "periode": "2021 – Présent", "lieu": "Paris",
             "bullets": [
                 "Conception de Design System en Figma pour des apps React",
                 "User research, wireframes, prototypes interactifs",
                 "Collaboration étroite avec développeurs React pour l'intégration",
                 "Tests utilisateurs, itérations sur les maquettes",
             ]},
            {"poste": "Designer UI", "entreprise": "Agence Digitale",
             "periode": "2020 – 2021", "lieu": "Nantes",
             "bullets": [
                 "Design d'interfaces mobiles iOS/Android sur Figma et Sketch",
                 "Intégration HTML/CSS basique",
             ]},
        ],
        "formations": [
            {"diplome": "Bachelor Design Numérique", "ecole": "Gobelins Paris", "annee": "2020"},
        ],
        "competences": {
            "Design":      ["Figma", "Sketch", "Adobe XD", "Illustrator", "Photoshop"],
            "UX":          ["User Research", "Wireframing", "Prototypage", "Tests Utilisateurs", "Design System"],
            "Dev (notions)": ["HTML5", "CSS3", "Notions JavaScript", "Storybook"],
            "Collaboration": ["Jira", "Confluence", "Notion", "Zeplin"],
        },
        "langues": ["Français (natif)", "Anglais (C1)"],
    }),

    # ── CV7 : Comptable (domaine différent) ───────────────────────────────────
    ("cv7_jean_dupont_comptable.pdf", {
        "nom": "Jean Dupont",
        "titre": "Comptable Senior — Expert-Comptable Stagiaire",
        "email": "jean.dupont@email.com", "tel": "06 78 90 12 34", "ville": "Paris",
        "resume": (
            "Comptable confirmé avec 5 ans d'expérience en cabinet comptable et en entreprise. "
            "Spécialisé dans les clôtures de comptes, la gestion de la TVA et les bilans annuels. "
            "Maîtrise des logiciels Sage, SAP et Excel avancé."
        ),
        "experiences": [
            {"poste": "Comptable Senior", "entreprise": "Cabinet Comptable Dupont & Associés",
             "periode": "2020 – Présent", "lieu": "Paris",
             "bullets": [
                 "Tenue de la comptabilité générale d'un portefeuille de 30 clients PME",
                 "Établissement des bilans, comptes de résultats, déclarations fiscales",
                 "Gestion TVA, IS, révision des comptes en vue de la certification",
                 "Conseil fiscal aux dirigeants d'entreprise",
             ]},
            {"poste": "Comptable", "entreprise": "Groupe Industriel",
             "periode": "2018 – 2020", "lieu": "Lille",
             "bullets": [
                 "Comptabilité fournisseurs et clients",
                 "Rapprochements bancaires, clôtures mensuelles avec SAP",
             ]},
        ],
        "formations": [
            {"diplome": "DCG — Diplôme de Comptabilité et Gestion", "ecole": "INTEC Paris", "annee": "2018"},
            {"diplome": "BTS Comptabilité Gestion", "ecole": "Lycée Professionnel", "annee": "2016"},
        ],
        "competences": {
            "Comptabilité":   ["Comptabilité générale", "Clôtures", "Bilan", "TVA", "IS"],
            "Logiciels":      ["Sage 100", "SAP FI", "Ciel Compta", "Excel avancé", "Power BI"],
            "Fiscal":         ["Déclarations fiscales", "Liasse fiscale", "Droit fiscal des entreprises"],
        },
        "langues": ["Français (natif)", "Anglais (B1)"],
    }),

    # ── CV8 : Infirmière (domaine incompatible) ───────────────────────────────
    ("cv8_amina_diallo_infirmiere.pdf", {
        "nom": "Amina Diallo",
        "titre": "Infirmière Diplômée d'État — Spécialisation Urgences",
        "email": "amina.diallo@email.com", "tel": "06 89 01 23 45", "ville": "Paris",
        "resume": (
            "Infirmière diplômée avec 6 ans d'expérience aux urgences et en soins intensifs. "
            "Expertise en gestion des situations critiques, soins post-opératoires et relation patient. "
            "Bac+3 en Sciences Infirmières. Cherche à contribuer à un établissement de santé exigeant."
        ),
        "experiences": [
            {"poste": "Infirmière Urgences", "entreprise": "CHU de Paris",
             "periode": "2020 – Présent", "lieu": "Paris",
             "bullets": [
                 "Prise en charge des patients aux urgences (adultes et pédiatriques)",
                 "Administration des traitements, suivi des constantes, gestion des perfusions",
                 "Coordination avec les médecins urgentistes pour les protocoles de soins",
                 "Formation des étudiants infirmiers en stage",
             ]},
            {"poste": "Infirmière Soins Intensifs", "entreprise": "Clinique Privée",
             "periode": "2018 – 2020", "lieu": "Dakar",
             "bullets": [
                 "Surveillance post-opératoire et soins intensifs",
                 "Gestion des appareils de monitoring et ventilation assistée",
             ]},
        ],
        "formations": [
            {"diplome": "Diplôme d'État Infirmier (DEI)", "ecole": "IFSI Paris", "annee": "2018"},
            {"diplome": "Baccalauréat Scientifique", "ecole": "Lycée Technique", "annee": "2015"},
        ],
        "competences": {
            "Soins":       ["Soins infirmiers", "Gestion perfusions", "Pansements complexes", "Injections"],
            "Médical":     ["Pharmacologie", "Urgences", "Soins intensifs", "Post-opératoire", "Pédiatrie"],
            "Soft skills": ["Travail en équipe", "Gestion du stress", "Communication patient", "Rigueur"],
        },
        "langues": ["Français (natif)", "Anglais (B1)", "Wolof (natif)"],
    }),
]


if __name__ == "__main__":
    print(f"\nGénération des CVs dans : {OUT_DIR}\n")
    for filename, data in CVS:
        make_cv(filename, data)

    print(f"\n{'='*60}")
    print("OFFRE À CRÉER SUR LA PLATEFORME :")
    print(f"{'='*60}")
    print("""
Titre          : Développeur React Senior
Domaine        : Développement Frontend / IT
Type contrat   : CDI
Localisation   : Paris
Expérience req : 3 ans minimum
Niveau diplôme : Bac+3 minimum

Description :
  Nous recherchons un(e) Développeur React Senior pour rejoindre
  notre équipe produit à Paris. Vous serez responsable du
  développement et de la maintenance de notre application React,
  en collaboration avec les équipes design et backend.

Compétences requises :
  React, TypeScript, JavaScript, HTML5, CSS3, Git, Redux, Jest

Compétences appréciées :
  Next.js, Docker, CI/CD, GraphQL, Node.js

{'='*60}
SCORES ATTENDUS (ordre de classement) :
  1. Maria Garcia     (CV4 - Fullstack React) ~ 0.70
  2. Ahmed Benali     (CV1 - React Senior)    ~ 0.68
  3. Sophie Leclerc   (CV2 - React Junior)    ~ 0.58
  4. Thomas Nguyen    (CV3 - Vue.js)          ~ 0.50
  5. Karim Osman      (CV5 - Python Backend)  ~ 0.38
  6. Lucie Fontaine   (CV6 - UX/UI)          ~ 0.30
  7. Jean Dupont      (CV7 - Comptable)       ~ 0.10
  8. Amina Diallo     (CV8 - Infirmière)      ~ 0.08
{'='*60}
""")
