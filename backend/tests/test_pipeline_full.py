"""Test du pipeline NLP complet avec un CV réaliste tunisien."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.nlp.nlp_parser import NLPParser

cv_text = """YOUSSEF GARA
Ariana, Tunisie
youssef.gara@esprit.tn
+216 22 333 444
LinkedIn: linkedin.com/in/youssef-gara
GitHub: github.com/youssefgara

PROFIL
Ingenieur logiciel Full-Stack avec 3 ans d experience en developpement web et mobile.

COMPETENCES TECHNIQUES
- Langages : Python, Java, JavaScript, TypeScript, SQL
- Front-end : React, Angular, Vue.js, HTML, CSS, Bootstrap, Tailwind
- Back-end : FastAPI, Django, Spring Boot, Node.js, Express.js
- Base de donnees : PostgreSQL, MySQL, MongoDB, Redis
- DevOps : Docker, Kubernetes, Jenkins, GitLab CI/CD, GitHub Actions
- Cloud : AWS, Azure, Google Cloud
- Outils : Git, Jira, Confluence, VS Code, IntelliJ

EXPERIENCE PROFESSIONNELLE

Developpeur Full-Stack | Sofrecom Tunisie | Janvier 2023 - Present
- Developpement d applications web avec React et FastAPI
- Mise en place de pipelines CI/CD avec GitLab

Stage PFE | Orange Labs | Fevrier 2022 - Juin 2022
- Conception et developpement d un systeme de recommandation
- Technologies : Python, TensorFlow, Flask

Stage d ete | Vermeg | Juillet 2021 - Aout 2021
- Developpement front-end avec Angular et TypeScript

FORMATION

Diplome National d Ingenieur en Informatique | ESPRIT | 2019 - 2024
Baccalaureat Sciences Experimentales | Lycee Pilote Ariana | 2019
Mention Tres Bien

LANGUES
- Francais : Langue maternelle
- Anglais : Courant (B2)
- Arabe : Langue maternelle
"""

parser = NLPParser()
raw = parser.parse(cv_text)
assert raw["success"], f"Pipeline failed: {raw.get('error')}"
result = raw["parsed_data"]

print("=" * 60)
print("PIPELINE NLP COMPLET - CV REALISTE")
print("=" * 60)

print("\n--- IDENTITE ---")
print(f"  nom: {result['identite']['nom_complet']}")

print("\n--- CONTACTS ---")
for k, v in result["contacts"].items():
    if v:
        print(f"  {k}: {v}")

print(f"\n--- COMPETENCES ({result['metadata']['total_competences']}) ---")
for cat, skills in result["competences_par_categorie"].items():
    print(f"  {cat}: {skills}")

print(f"\n--- FORMATIONS ({len(result['formations'])}) ---")
for f in result["formations"]:
    print(f"  - {f.get('diplome','?')} | {f.get('etablissement','?')} | {f.get('annee_debut','?')} - {f.get('annee_fin','?')}")

print(f"\n--- EXPERIENCES ({len(result['experiences'])}) ---")
for e in result["experiences"]:
    print(f"  - {e.get('poste','?')} | {e.get('entreprise','?')} | {e.get('date_debut','?')} - {e.get('date_fin','?')}")

print(f"\n--- LANGUES ({len(result['langues'])}) ---")
for l in result["langues"]:
    print(f"  - {l['langue']}: {l['niveau']}")

print(f"\n--- METADATA ---")
for k, v in result["metadata"].items():
    print(f"  {k}: {v}")

# Validations
errors = []
if not result["identite"]["nom_complet"]:
    errors.append("NOM MANQUANT")
if not result["contacts"].get("email"):
    errors.append("EMAIL MANQUANT")
if not result["contacts"].get("telephone"):
    errors.append("TELEPHONE MANQUANT")
if not result["contacts"].get("linkedin"):
    errors.append("LINKEDIN MANQUANT")
if not result["contacts"].get("github"):
    errors.append("GITHUB MANQUANT")
if result["metadata"]["total_competences"] < 10:
    errors.append(f"PEU DE COMPETENCES: {result['metadata']['total_competences']}")
if len(result["formations"]) < 1:
    errors.append("AUCUNE FORMATION")
if len(result["experiences"]) < 2:
    errors.append(f"PEU D'EXPERIENCES: {len(result['experiences'])}")

print("\n" + "=" * 60)
if errors:
    print("PROBLEMES DETECTES:")
    for e in errors:
        print(f"  WARN: {e}")
else:
    print("TOUS LES CHAMPS EXTRAITS CORRECTEMENT !")
print("=" * 60)
