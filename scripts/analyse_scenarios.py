"""Analyse complète du matching sur toutes les offres actives."""
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

BASE = "http://127.0.0.1:8000"

# Auth
r = requests.post(f"{BASE}/api/auth/login",
    json={"email": "admin1@esprit.tn", "password": "Admin123!"})
TOKEN = r.json().get("access_token", "")
H = {"Authorization": f"Bearer {TOKEN}"}

# Offres actives depuis la DB
from app.database import SessionLocal
from app.models.job_offer import JobOffer
db = SessionLocal()
offers = db.query(JobOffer).filter(JobOffer.status=='active').all()
db.close()

DECISIONS = {
    "Excellent candidat":                "EXCELLENT",
    "Bon profil - Entretien recommandé": "BON",
    "Profil partiel - À évaluer":        "PARTIEL",
    "Profil non adapté":                 "NON ADAPTÉ",
}

print("=" * 80)
print("  ANALYSE MATCHING — Scénarios réels en production")
print("=" * 80)

all_issues = []

for offer in offers:
    r = requests.post(f"{BASE}/api/match/{offer.id}", headers=H, timeout=120)
    if r.status_code != 200:
        print(f"\n[ERREUR] {offer.titre}: {r.status_code}")
        continue

    data = r.json()
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        print(f"\n[VIDE] {offer.titre}: aucun candidat")
        continue

    results_sorted = sorted(results, key=lambda x: -x.get("bert_score", x.get("score", 0)))
    nb_postes = offer.nb_postes or 1
    skills_req = offer.competences_requises or []

    print(f"\n{'━'*80}")
    print(f"  OFFRE : {offer.titre}")
    print(f"  Skills requises : {', '.join(skills_req[:6])}")
    print(f"  Exp : {offer.experience_requise} ans | Postes : {nb_postes}")
    print(f"  {len(results)} candidats analysés")
    print(f"{'─'*80}")
    print(f"  {'#':2} {'Score':6} {'Candidat':28} {'Compét':7} {'Exp':5} {'Décision':20} {'Alertes'}")
    print(f"  {'─'*2} {'─'*6} {'─'*28} {'─'*7} {'─'*5} {'─'*20} {'─'*15}")

    for i, r_cand in enumerate(results_sorted[:8], 1):
        score = r_cand.get("bert_score", r_cand.get("score", 0))
        name  = r_cand.get("candidate_name", r_cand.get("nom", "?"))
        det   = r_cand.get("bert_details", r_cand.get("details", {}))

        comp  = det.get("competences", 0)
        exp   = det.get("experience", 0)
        dec   = DECISIONS.get(det.get("decision", ""), det.get("decision", "")[:16])
        ts    = det.get("title_skill", "")
        ts_ko = det.get("title_skill_missing", False)
        otype = det.get("offer_type", "")
        mlpv  = det.get("mlp_version", "?")

        # Alertes
        alerts = []
        if ts_ko and ts:
            alerts.append(f"★{ts} manquant")
        if comp < 30:
            alerts.append("skills<<")
        if exp < 20 and offer.experience_requise > 0:
            alerts.append("exp<<")
        crit = det.get("skills_criticality", {})
        missing = det.get("skills_missing", [])
        crit_miss = [m for m in missing if crit.get(m if isinstance(m,str) else m.get("skill",""), "") == "critique"]
        if crit_miss:
            alerts.append(f"critique manq: {crit_miss[0] if isinstance(crit_miss[0],str) else crit_miss[0].get('skill','')[:10]}")

        retained = "✓" if i <= nb_postes else " "
        alert_str = " | ".join(alerts[:2])

        print(f"  {retained}{i:1} {score*100:5.1f}% {name[:28]:28s} {comp:5.0f}%  {exp:4.0f}% {dec[:20]:20s} {alert_str}")

    # Analyse qualité
    top = results_sorted[0]
    top_det = top.get("bert_details", {})
    top_score = top.get("bert_score", top.get("score", 0))
    offer_type = top_det.get("offer_type", "?")
    weights = top_det.get("weights_used", {})

    print(f"\n  ANALYSE :")
    print(f"    Type offre détecté : {offer_type}")
    if weights:
        print(f"    Poids appliqués    : skills={weights.get('skills',0)*100:.0f}% / "
              f"sem={weights.get('semantique',0)*100:.0f}% / "
              f"exp={weights.get('experience',0)*100:.0f}% / "
              f"form={weights.get('formation',0)*100:.0f}%")
    print(f"    MLP version        : {top_det.get('mlp_version', '?')}")

    # Problèmes potentiels
    scores = [x.get("bert_score", x.get("score", 0)) for x in results_sorted]
    gap = scores[0] - scores[1] if len(scores) > 1 else 0
    if top_score < 0.60:
        all_issues.append(f"  ⚠  '{offer.titre}' : meilleur candidat seulement {top_score*100:.0f}% — pool faible ?")
    if gap < 0.10 and len(scores) > 1:
        all_issues.append(f"  ⚠  '{offer.titre}' : #1 et #2 très proches ({scores[0]*100:.0f}% vs {scores[1]*100:.0f}%) — décision difficile")
    recommended = sum(1 for s in scores if s >= 0.65)
    if recommended == 0:
        all_issues.append(f"  ⚠  '{offer.titre}' : aucun candidat recommandé (>65%)")

print(f"\n{'='*80}")
print(f"  SYNTHÈSE GLOBALE")
print(f"{'='*80}")
if all_issues:
    print("  Points d'attention :")
    for issue in all_issues:
        print(issue)
else:
    print("  Aucun problème majeur détecté.")
print()
