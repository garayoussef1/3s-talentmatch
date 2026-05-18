"""
Test rapide de l'ontologie métier et du prestige institution.
Simule le scénario médical qui échouait (ranking inversé).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.matching_sandbox.bert_scorer import (
    _detect_profession_from_cv,
    _detect_offer_domain,
    _institution_prestige_score,
    _ADJACENT_DOMAINS,
)

# ── Simuler des candidats (parsed_data minimal) ───────────────────────────────
CANDIDATS = [
    {
        "nom": "Amira Boukadida — Médecin Généraliste",
        "raw": "médecin généraliste cabinet libéral diagnostic clinique prescription médicale",
        "parsed": {
            "experiences": [{"poste": "Médecin Généraliste", "description": "Cabinet médical"}],
            "formations": [{"diplome": "Doctorat en Médecine", "etablissement": "Faculté de Médecine de Tunis"}],
            "metadata": {"titre_professionnel": "Médecin Généraliste"},
        },
    },
    {
        "nom": "Yassine Gharbi — Urgentiste",
        "raw": "médecin urgentiste samu urgences réanimation ecg triage",
        "parsed": {
            "experiences": [{"poste": "Médecin Urgentiste", "description": "Hôpital Charles Nicolle"}],
            "formations": [{"diplome": "Doctorat en Médecine", "etablissement": "Faculté de Médecine"}],
            "metadata": {"titre_professionnel": "Médecin Urgentiste"},
        },
    },
    {
        "nom": "Rim Sfaxi — Infirmière",
        "raw": "infirmière soins infirmiers bloc opératoire pédiatrie ecg pharmacologie",
        "parsed": {
            "experiences": [{"poste": "Infirmière", "description": "Clinique Internationale"}],
            "formations": [{"diplome": "Licence Soins Infirmiers", "etablissement": "ISET Tunis"}],
            "metadata": {"titre_professionnel": "Infirmière Diplômée"},
        },
    },
    {
        "nom": "Sonia Maalej — Pharmacienne",
        "raw": "pharmacienne pharmacologie médicaments dispensation conseil patient",
        "parsed": {
            "experiences": [{"poste": "Pharmacienne", "description": "Pharmacie centrale"}],
            "formations": [{"diplome": "Doctorat en Pharmacie", "etablissement": "Faculté de Pharmacie"}],
            "metadata": {"titre_professionnel": "Pharmacienne"},
        },
    },
    {
        "nom": "Karim Jebali — Ingénieur Biomédical",
        "raw": "ingénieur biomédical maintenance dispositifs médicaux matériel médical ecg",
        "parsed": {
            "experiences": [{"poste": "Ingénieur Biomédical", "description": "Maintenance équipements"}],
            "formations": [{"diplome": "Ingénieur en Génie Biomédical", "etablissement": "INSAT"}],
            "metadata": {"titre_professionnel": "Ingénieur Biomédical"},
        },
    },
]

# ── Simuler l'offre : Médecin Généraliste ─────────────────────────────────────
class FakeOffer:
    titre = "Médecin Généraliste / Responsable Médical"
    description = "Recherche médecin généraliste expérimenté pour consultation, diagnostic clinique, prescription médicale, suivi patient, pédiatrie, ECG, vaccination."

offer = FakeOffer()
offer_domain, offer_level = _detect_offer_domain(offer)

print("=" * 70)
print(f"OFFRE : {offer.titre}")
print(f"Domaine détecté : {offer_domain}  |  Niveau attendu : {offer_level}")
print("=" * 70)

OFFER_SKILLS = [
    "Médecine générale", "Diagnostic clinique", "Prescription médicale",
    "Urgences médicales", "Suivi patient", "Dossier médical électronique",
    "Pharmacologie", "Pédiatrie", "Cardiologie basique", "ECG",
    "Éthique médicale", "Vaccination"
]

print(f"\n{'Candidat':<45} {'Domaine':<18} {'Niv':<5} {'Skills implicites → matchés'}")
print("-" * 110)

for c in CANDIDATS:
    domain, level, implied = _detect_profession_from_cv(c["raw"], c["parsed"])
    prestige = _institution_prestige_score(c["parsed"])

    # Compter combien de skills de l'offre sont couverts par les compétences implicites
    from app.services.matching.match_engine import _normalize_skill
    implied_norms = {_normalize_skill(s) for s in implied}
    offer_norms = {_normalize_skill(s) for s in OFFER_SKILLS}
    matched_by_ontology = offer_norms & implied_norms

    # Détection mismatch
    cap = None
    if offer_domain and domain and offer_domain != domain:
        pair = (offer_domain, domain)
        cap = 0.62 if pair in _ADJACENT_DOMAINS else 0.44

    cap_str = f" [CAP={int(cap*100)}%]" if cap else ""
    print(f"{c['nom']:<45} {str(domain):<18} {level:<5} {len(matched_by_ontology)}/12 skills{cap_str}")
    print(f"  Prestige institution: {prestige:.2f}  |  Skills implicites: {', '.join(implied[:5])}{'...' if len(implied)>5 else ''}")
    print()

print("=" * 70)
print("RANKING ATTENDU APRÈS ONTOLOGIE :")
print("  1. Amira (Médecin Généraliste) — 10-12/12 skills, même domaine")
print("  2. Yassine (Urgentiste)        — 7-9/12 skills, même domaine")
print("  3. Rim (Infirmière)            — 3-4/12 skills + CAP 62%")
print("  4. Sonia (Pharmacienne)        — 2-3/12 skills + CAP 44%")
print("  5. Karim (Biomédical)          — 1-2/12 skills + CAP 44%")
