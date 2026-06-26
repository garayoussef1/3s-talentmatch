# -*- coding: utf-8 -*-
"""Test end-to-end de l'API entretien : start -> answer -> report."""
import sys, io, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"
tok = requests.post(f"{BASE}/api/auth/login",
    json={"email": "admin1@esprit.tn", "password": "Admin123!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

# Candidat + offre depuis un Match existant
sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models.match import Match
db = SessionLocal()
m = db.query(Match).first()
cand, offer = str(m.candidate_id), str(m.job_offer_id)
db.close()

print("=== 1. START ===")
r = requests.post(f"{BASE}/api/interviews/start", headers=H,
    json={"candidate_id": cand, "offer_id": offer}, timeout=120).json()
iid = r["interview_id"]
print(f"  interview={iid[:8]} provider={r['provider']} {r['total_questions']} questions")
# On répond à 3 questions techniques (index 2,3,4)
tech_qs = [q for q in r["questions"] if q["phase"] == "technical"][:2]

answers = {
    tech_qs[0]["id"]: "Chez mon precedent poste, j'ai mis en place une architecture microservices avec API Gateway, chaque service avec sa base PostgreSQL, communication via RabbitMQ. Resultat: deploiements independants, scalabilite x3.",
    tech_qs[1]["id"]: "Oui je connais ca, c'est important.",
}

print("\n=== 2. ANSWER (2 reponses : 1 detaillee, 1 vague) ===")
for qid, ans in answers.items():
    a = requests.post(f"{BASE}/api/interviews/{iid}/answer", headers=H,
        json={"question_id": qid, "answer_text": ans}, timeout=60).json()
    print(f"  Q{qid[:8]} -> score={a.get('score')} | flags_red={a.get('flags',{}).get('red')}")

print("\n=== 3. REPORT ===")
rep = requests.post(f"{BASE}/api/interviews/{iid}/report", headers=H, timeout=60).json()
print(f"  Score global: {rep.get('score_global_100')}/100")
print(f"  Recommandation: {rep.get('recommandation')}")
print(f"  Synthese: {rep.get('synthese_executive','')[:160]}")

print("\n=== 4. GET (relecture persistee) ===")
g = requests.get(f"{BASE}/api/interviews/{iid}", headers=H, timeout=30).json()
print(f"  status={g['status']} | global_score={g['global_score']} | reco={g['recommendation']}")
answered = sum(1 for q in g['questions'] if q['answered'])
print(f"  questions repondues: {answered}/{len(g['questions'])}")
print("\nOK - API entretien fonctionne de bout en bout (start->answer->report->get)")
