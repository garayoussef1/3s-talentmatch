"""
Test complet de toutes les améliorations Sprint 2.
Lance avec : python -m pytest tests/test_toutes_ameliorations.py -v -s
Ou directement : python tests/test_toutes_ameliorations.py
"""
import sys
import os
import json
import io

# IMPORTANT: ce module est importé par pytest. On évite donc les mutations
# globales (stdout, sys.path) à l'import; elles ne sont utiles qu'en exécution directe.
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.nlp.nlp_parser import NLPParser

# ────────────────────────────────────────────────────────────────
# CV de test — contient TOUT ce qu'on veut tester
# ────────────────────────────────────────────────────────────────
CV_TEST = """
Ahmed Ben Salah
ahmed.bensalah@gmail.com | +216 55 987 654
linkedin.com/in/ahmedbensalah | github.com/ahmedbensalah

COMPETENCES
Pyhton, JavaScrip, Java, C++, SQL, Djnago, Reactjs, Sprinng, Vuejs, MySQL, Mongoo, Postgress, Rediss, Doker, Kubrnetes, Jenkins, Ansible, Git, Figma

EXPERIENCES PROFESSIONNELLES
2022-2024 | Developpeur Backend Senior | TechCorp Tunisia
  - Developpement API REST et bases de donnees
  - Migration base de donnees vers cloud
  - Pipeline CI/CD et containerisation

2020-2022 | Ingenieur DevOps | Vermeg Tunis
  - Infrastructure cloud avec 30 microservices
  - Automatisation des deploiements

2019-2020 | Stage PFE Developpeur Full Stack | Startup Innovate
  - Plateforme e-commerce avec paiement en ligne

FORMATIONS
2022-2024 | Master Genie Logiciel et IA | ESPRIT, Tunis
2018-2022 | Licence Informatique | FST Sousse 2022
2018 | Baccalaureat Informatique Mention Bien | Lycee Bourguiba, Monastir

LANGUES
Arabe : native
Francais : courant
Anglais : intermediate
Allemand
"""

# ────────────────────────────────────────────────────────────────
SEP = "=" * 60

def _ok(cond, msg_ok, msg_fail):
    status = "✓ OK" if cond else "✗ FAIL"
    print(f"  {status}  {msg_ok if cond else msg_fail}")
    return cond


def run():
    print(f"\n{SEP}")
    print("  TEST TOUTES AMELIORATIONS — 3S TalentMatch")
    print(SEP)

    parser = NLPParser()
    result = parser.parse(CV_TEST)
    data = result["parsed_data"]

    skills      = data.get("competences", [])
    experiences = data.get("experiences", [])
    formations  = data.get("formations", [])
    langues     = data.get("langues", [])
    meta        = data.get("metadata", {})
    breakdown   = meta.get("confidence_breakdown", {})

    passed = 0
    total  = 0

    # ────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("1. FUZZY MATCHING — correction fautes de frappe")
    print(f"{'─'*60}")

    fuzzy_skills = [s for s in skills if s.get("source") == "fuzzy"]
    print(f"  Compétences corrigées par fuzzy : {len(fuzzy_skills)}")
    for s in fuzzy_skills:
        print(f"    '{s['original_token']}' → '{s['name']}'  (score={s.get('fuzzy_score')}%)")

    # Test fuzzy direct sur section isolée (sans normalize_pdf_text)
    from app.services.nlp.skills_extractor import SkillsExtractor
    ext_test = SkillsExtractor()
    section_test = "COMPETENCES\nPyhton, JavaScrip, Djnago, Sprinng, Doker, Kubrnetes, Mongoo, Postgress, Rediss"
    result_test = ext_test.extract(section_test)
    fuzzy_test = {s["original_token"]: s["name"] for s in result_test["skills"] if s.get("source") == "fuzzy"}

    checks = {
        "Python":     "Pyhton",
        "JavaScript": "JavaScrip",
        "Django":     "Djnago",
        "Spring":     "Sprinng",
        "Docker":     "Doker",
        "Kubernetes": "Kubrnetes",
        "MongoDB":    "Mongoo",
        "PostgreSQL": "Postgress",
        "Redis":      "Rediss",
    }
    for canonical, typo in checks.items():
        corrected = fuzzy_test.get(typo) == canonical
        total += 1
        if _ok(corrected,
               f"'{typo}' corrigé en '{canonical}'",
               f"'{typo}' NON corrigé (résultat: {fuzzy_test.get(typo, 'absent')})"):
            passed += 1

    # ────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("2. FORMATIONS — lieu + année nettoyée du nom")
    print(f"{'─'*60}")

    for f in formations:
        print(f"  diplome:  {f.get('diplome')}")
        print(f"  etab:     {f.get('etablissement')}")
        print(f"  lieu:     {f.get('lieu')}")
        print(f"  annee:    {f.get('annee')}")
        cands = f.get("ia_candidats_etablissement", [])
        if cands:
            print(f"  IA candidats: {[(c['valeur'], c['score']) for c in cands[:3]]}")
        print()

    fst = next((f for f in formations if "fst" in (f.get("etablissement") or "").lower()), None)
    total += 1
    if _ok(fst and "2022" not in (fst.get("etablissement") or ""),
           "FST Sousse : année absente du nom d'établissement",
           "FST Sousse : année encore présente dans le nom"):
        passed += 1

    total += 1
    if _ok(fst and fst.get("lieu") == "Sousse",
           f"FST Sousse : lieu = '{fst.get('lieu') if fst else None}'",
           f"FST Sousse : lieu manquant ou incorrect (={fst.get('lieu') if fst else None})"):
        passed += 1

    esprit = next((f for f in formations if "esprit" in (f.get("etablissement") or "").lower()), None)
    total += 1
    if _ok(esprit and esprit.get("lieu") in ("Tunis", "tunis"),
           f"ESPRIT : lieu = '{esprit.get('lieu') if esprit else None}'",
           f"ESPRIT : lieu manquant"):
        passed += 1

    # ────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("3. LANGUES — normalisation des niveaux")
    print(f"{'─'*60}")

    for l in langues:
        print(f"  {l['langue']:12} → niveau: {l['niveau']}")

    niveaux = {l["langue"].lower(): l["niveau"] for l in langues}

    total += 1
    if _ok(niveaux.get("arabe") == "Natif",
           "Arabe : 'native' normalisé en 'Natif'",
           f"Arabe : niveau = '{niveaux.get('arabe')}'"):
        passed += 1

    total += 1
    if _ok(niveaux.get("anglais") == "Intermédiaire",
           "Anglais : 'intermediate' normalisé en 'Intermédiaire'",
           f"Anglais : niveau = '{niveaux.get('anglais')}'"):
        passed += 1

    total += 1
    if _ok(niveaux.get("allemand") == "Non spécifié",
           "Allemand : absent → 'Non spécifié'",
           f"Allemand : niveau = '{niveaux.get('allemand')}'"):
        passed += 1

    # ────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("4. IA MEILLEUR CHOIX — candidats entreprises scorés")
    print(f"{'─'*60}")

    for e in experiences:
        print(f"  poste:      {e.get('poste')}")
        print(f"  entreprise: {e.get('entreprise')}")
        cands = e.get("ia_candidats_entreprise", [])
        if cands:
            print(f"  IA candidats:")
            for c in cands[:3]:
                print(f"    [{c['score']:+d}] {c['valeur']:25} ({c['source']})")
        print()

    techcorp = next((e for e in experiences if "techcorp" in (e.get("entreprise") or "").lower()), None)
    total += 1
    if _ok(techcorp is not None,
           "TechCorp Tunisia détecté comme entreprise",
           "TechCorp Tunisia NON détecté"):
        passed += 1

    total += 1
    if _ok(any(e.get("ia_candidats_entreprise") for e in experiences),
           "Candidats IA entreprise présents dans au moins 1 expérience",
           "Aucun candidat IA entreprise trouvé"):
        passed += 1

    # ────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("5. AUTO-DICT EXPERIENCES — sauvegarde postes/entreprises")
    print(f"{'─'*60}")

    dict_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "experiences_discovered.json"
    )
    try:
        with open(dict_path, encoding="utf-8") as f:
            disc = json.load(f)
        print(f"  Postes connus    : {len(disc['postes'])}")
        print(f"  Entreprises conn.: {len(disc['entreprises'])}")
        for k, v in list(disc["postes"].items())[:5]:
            print(f"    poste: '{k}' (vu {v}x)")
        for k, v in list(disc["entreprises"].items())[:5]:
            print(f"    entreprise: '{k}' (vu {v}x)")

        total += 1
        if _ok(len(disc["postes"]) > 0,
               "Dict postes non vide après parsing",
               "Dict postes VIDE — sauvegarde échouée"):
            passed += 1
    except Exception as ex:
        print(f"  ERREUR lecture dict : {ex}")
        total += 1

    # ────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("6. SCORE DE CONFIANCE — breakdown détaillé")
    print(f"{'─'*60}")

    confidence = meta.get("confidence_score", 0)
    print(f"  Score global : {confidence} ({round(confidence*100)}%)")
    print()
    for champ, v in breakdown.items():
        bar = "█" * int(v["score"] / v["max"] * 10) if v["max"] > 0 else ""
        print(f"  {champ:15} {bar:10} {v['pct']:5}  {v['detail']}")

    print()
    print(f"  champs_manquants : {meta.get('champs_manquants', [])}")
    print(f"  champs_faibles   : {meta.get('champs_faibles', [])}")

    total += 1
    if _ok(confidence >= 0.70,
           f"Score de confiance OK : {round(confidence*100)}%",
           f"Score trop bas : {round(confidence*100)}%"):
        passed += 1

    total += 1
    if _ok(len(breakdown) == 8,
           f"Breakdown complet : {len(breakdown)} dimensions",
           f"Breakdown incomplet : {len(breakdown)}/8 dimensions"):
        passed += 1

    # ────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    color = "✓" if passed == total else "✗"
    print(f"  {color}  RÉSULTAT : {passed}/{total} tests passés")
    print(SEP)

    return passed == total


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
