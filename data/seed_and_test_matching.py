"""
seed_and_test_matching.py
=========================
Script de test complet :
  1. Connexion API (admin)
  2. Création de N offres variées (domaines différents)
  3. Lancement du matching BGE-M3 sur chaque offre
  4. Affichage tableau de résultats

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10/Scripts/python data/seed_and_test_matching.py

Prérequis : backend running sur http://localhost:8000
            Au moins 1 candidat uploadé dans la base
"""

import requests
import json
import sys
from tabulate import tabulate   # pip install tabulate si absent

BASE = "http://localhost:8000/api"

# ── Identifiants admin ────────────────────────────────────────────────────────
ADMIN_EMAIL    = "admin@talentmatch.com"
ADMIN_PASSWORD = "Admin1234!"   # à adapter si différent

# ── Offres à créer (domaines variés) ─────────────────────────────────────────
OFFRES = [
    {
        "titre": "Ingénieur Backend Python / FastAPI",
        "entreprise": "3S Informatique",
        "description": (
            "Nous recherchons un ingénieur backend confirmé maîtrisant Python et FastAPI. "
            "Vous développerez des APIs REST performantes, gérerez une base PostgreSQL via SQLAlchemy, "
            "mettrez en place du cache Redis et travaillerez en environnement Docker / CI-CD GitLab. "
            "Formation requise : Bac+5 en informatique. Expérience : 3 ans minimum."
        ),
        "competences_requises": ["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "REST API", "Redis", "SQLAlchemy"],
        "competences_appreciees": ["Kubernetes", "RabbitMQ", "pytest"],
        "localisation": "Tunis",
        "type_contrat": "CDI",
        "nb_postes": 1,
        "experience_requise": 3,
    },
    {
        "titre": "Data Scientist / Machine Learning Engineer",
        "entreprise": "DataLab Tunisie",
        "description": (
            "Rejoignez notre équipe data pour construire et déployer des modèles ML en production. "
            "Vous travaillerez sur du traitement de données avec Pandas/NumPy, entraînerez des modèles "
            "scikit-learn et TensorFlow, et exposerez les prédictions via des APIs Python. "
            "Formation Bac+5 en Data Science ou Mathématiques appliquées. Expérience : 2 ans."
        ),
        "competences_requises": ["Python", "Machine Learning", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "SQL", "Git"],
        "competences_appreciees": ["PyTorch", "MLflow", "Docker", "Spark"],
        "localisation": "Tunis",
        "type_contrat": "CDI",
        "nb_postes": 2,
        "experience_requise": 2,
    },
    {
        "titre": "Développeur Frontend React / TypeScript",
        "entreprise": "WebVision",
        "description": (
            "Nous cherchons un développeur frontend passionné pour créer des interfaces modernes. "
            "Vous maîtrisez React, TypeScript, et les outils comme Vite et Tailwind CSS. "
            "Expérience avec les APIs REST et GraphQL. Sens du détail UI/UX requis. "
            "Formation Bac+3 minimum. Expérience : 2 ans."
        ),
        "competences_requises": ["React", "TypeScript", "JavaScript", "HTML", "CSS", "Git", "REST API", "Tailwind"],
        "competences_appreciees": ["Next.js", "GraphQL", "Redux", "Figma"],
        "localisation": "Sfax",
        "type_contrat": "CDI",
        "nb_postes": 1,
        "experience_requise": 2,
    },
    {
        "titre": "Ingénieur DevOps / Cloud AWS",
        "entreprise": "CloudOps TN",
        "description": (
            "Poste DevOps pour gérer l'infrastructure cloud AWS de nos clients. "
            "Vous automatiserez les déploiements avec Terraform et Ansible, gérerez des clusters Kubernetes, "
            "mettrez en place des pipelines CI/CD Jenkins/GitLab et assurerez la supervision (Grafana, Prometheus). "
            "Formation Bac+5. Expérience : 4 ans minimum."
        ),
        "competences_requises": ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Git", "Linux", "Ansible"],
        "competences_appreciees": ["Prometheus", "Grafana", "Jenkins", "Bash"],
        "localisation": "Tunis",
        "type_contrat": "CDI",
        "nb_postes": 1,
        "experience_requise": 4,
    },
    {
        "titre": "Développeur Full Stack Java / Angular — Stage",
        "entreprise": "Banque Centrale TN",
        "description": (
            "Stage de fin d'études pour un développeur full stack Java/Angular. "
            "Vous participerez au développement d'une application bancaire interne : "
            "backend Spring Boot, base Oracle, frontend Angular. Durée : 6 mois. "
            "Formation Bac+5 en cours (ingénieur ou master). Débutant accepté."
        ),
        "competences_requises": ["Java", "Spring Boot", "Angular", "SQL", "Git", "REST API"],
        "competences_appreciees": ["Oracle", "JPA", "TypeScript", "Maven"],
        "localisation": "Tunis",
        "type_contrat": "Stage",
        "nb_postes": 2,
        "experience_requise": 0,
    },
    {
        "titre": "Analyste Cybersécurité / Pentester",
        "entreprise": "SecureIT Maghreb",
        "description": (
            "Rejoignez notre équipe sécurité pour réaliser des audits et tests d'intrusion. "
            "Vous maîtrisez les outils Kali Linux, Burp Suite, Nmap, Metasploit. "
            "Connaissance des normes ISO 27001 et OWASP. Certifications CEH ou OSCP appréciées. "
            "Formation Bac+5 sécurité informatique. Expérience : 2 ans."
        ),
        "competences_requises": ["Cybersécurité", "Pentest", "Kali Linux", "Burp Suite", "Python", "Réseaux", "Linux"],
        "competences_appreciees": ["OSCP", "Metasploit", "OWASP", "ISO 27001"],
        "localisation": "Tunis",
        "type_contrat": "CDI",
        "nb_postes": 1,
        "experience_requise": 2,
    },
]


def separator(char="─", n=80):
    print(char * n)


def login(session: requests.Session) -> bool:
    r = session.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        print(f"[ERREUR] Login échoué : {r.status_code} — {r.text[:200]}")
        return False
    token = r.json().get("access_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"[OK] Connecté en tant que {ADMIN_EMAIL}")
    return True


def create_offer(session: requests.Session, data: dict) -> dict | None:
    r = session.post(f"{BASE}/offers", json=data)
    if r.status_code in (200, 201):
        offer = r.json()
        print(f"  [+] Offre créée : '{data['titre']}' → id={offer['id'][:8]}...")
        return offer
    print(f"  [!] Échec création '{data['titre']}' : {r.status_code} — {r.json()}")
    return None


def get_candidates(session: requests.Session) -> list:
    r = session.get(f"{BASE}/candidates?limit=200")
    if r.status_code == 200:
        return r.json().get("candidates", r.json()) if isinstance(r.json(), dict) else r.json()
    return []


def run_matching(session: requests.Session, offer_id: str) -> list:
    r = session.post(
        f"{BASE}/match-sandbox/{offer_id}",
        params={"engine": "bert"},
        timeout=120,
    )
    if r.status_code == 200:
        data = r.json()
        return data.get("results", data) if isinstance(data, dict) else data
    print(f"  [!] Matching échoué pour {offer_id[:8]} : {r.status_code}")
    return []


def score_bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    separator("═")
    print("  3S TALENTMATCH — Script de test matching multi-offres")
    separator("═")

    # 1. Login
    if not login(session):
        sys.exit(1)

    # 2. Vérifier qu'il y a des candidats
    candidates = get_candidates(session)
    if not candidates:
        print("\n[ERREUR] Aucun candidat en base. Uploadez des CVs d'abord via l'interface.")
        sys.exit(1)
    print(f"[INFO] {len(candidates)} candidat(s) disponible(s) en base.\n")

    # 3. Créer les offres
    separator()
    print("CRÉATION DES OFFRES DE TEST")
    separator()
    created_offers = []
    for offre_data in OFFRES:
        offer = create_offer(session, offre_data)
        if offer:
            created_offers.append(offer)

    print(f"\n→ {len(created_offers)}/{len(OFFRES)} offres créées.\n")

    if not created_offers:
        print("[ERREUR] Aucune offre créée, vérifiez le backend.")
        sys.exit(1)

    # 4. Matching sur chaque offre
    separator()
    print("LANCEMENT DU MATCHING BGE-M3 SUR CHAQUE OFFRE")
    separator()

    all_results = []

    for offer in created_offers:
        print(f"\n  🔍 Matching : '{offer['titre']}'  [{offer['type_contrat']}]")
        results = run_matching(session, offer["id"])

        if not results:
            print("     Aucun résultat.")
            continue

        sorted_results = sorted(results, key=lambda r: r.get("bert_score", 0), reverse=True)
        rows = []
        for idx, r in enumerate(sorted_results[:5]):
            pct = round((r.get("bert_score") or 0) * 100, 1)
            bd  = r.get("bert_details") or {}
            rows.append([
                f"#{idx+1}",
                r.get("candidate_name", "—")[:28],
                score_bar(pct),
                f"{round(bd.get('competences', 0))}%",
                f"{round(bd.get('experience',  0))}%",
                f"{round(bd.get('formation',   0))}%",
                f"{round(bd.get('semantique',  0))}%",
            ])
            all_results.append({
                "offre":       offer["titre"][:35],
                "contrat":     offer["type_contrat"],
                "candidat":    r.get("candidate_name", "—")[:28],
                "score":       pct,
                "rang":        idx + 1,
            })

        print(tabulate(
            rows,
            headers=["#", "Candidat", "Score global", "Compét.", "Expér.", "Form.", "Sémant."],
            tablefmt="rounded_outline",
        ))

    # 5. Synthèse globale
    separator("═")
    print("\nSYNTHÈSE GLOBALE — Top candidat par offre\n")
    summary = {}
    for r in all_results:
        key = r["offre"]
        if key not in summary or r["score"] > summary[key]["score"]:
            summary[key] = r

    summary_rows = [
        [v["offre"], v["contrat"], v["candidat"], f"{v['score']:.1f}%"]
        for v in summary.values()
    ]
    print(tabulate(
        summary_rows,
        headers=["Offre", "Contrat", "Meilleur candidat", "Score"],
        tablefmt="rounded_outline",
    ))

    separator("═")
    print(f"\n[TERMINÉ] {len(created_offers)} offres testées sur {len(candidates)} candidat(s).")
    print(f"Retrouvez toutes les offres dans l'interface : http://localhost:3000/offers\n")


if __name__ == "__main__":
    main()
