"""
Validation complète du pipeline extraction + parsing.
Teste 10 CVs réels variés du dossier data/Cv/

Usage :
    python tests/test_validation_complete.py
    python tests/test_validation_complete.py --rapport  (rapport détaillé)
"""
from __future__ import annotations

import sys
import os
import io
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# IMPORTANT: ce fichier est aussi importé par pytest (collection).
# On évite donc toute mutation globale (stdout, sys.path) à l'import.
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.nlp_parser import NLPParser

# ─────────────────────────────────────────────────────────────────
# 10 CVs de test — vrais fichiers du dossier data/Cv/
# ─────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "Cv"

CV_TESTS = [
    {
        "id": 1,
        "label": "CV PDF textuel FR",
        "file": "Ines_ben_saad_CV.pdf",
        "type": "pdf_texte",
        "langue": "FR",
        "attendu": {"nom": True, "email": True, "competences": True},
    },
    {
        "id": 2,
        "label": "CV PDF textuel FR (2)",
        "file": "MaramSliti Cv.pdf",
        "type": "pdf_texte",
        "langue": "FR",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 3,
        "label": "CV PDF anglais",
        "file": "C_v_Pro_RanimEnglish.pdf",
        "type": "pdf_texte",
        "langue": "EN",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 4,
        "label": "CV PDF FR professionnel",
        "file": "C_v_Pro_RanimFrancais.pdf",
        "type": "pdf_texte",
        "langue": "FR",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 5,
        "label": "CV PDF anglais ingénieur",
        "file": "Wajih Mokhtar Alouini CV ENGLISH .pdf",
        "type": "pdf_texte",
        "langue": "EN",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 6,
        "label": "CV PDF FR ingénieur",
        "file": "Wajih Mokhtar Alouini CV FRENCH.pdf",
        "type": "pdf_texte",
        "langue": "FR",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 7,
        "label": "CV PDF Ahmed Aziz",
        "file": "AhmedAziz_Ammar (1).pdf",
        "type": "pdf_texte",
        "langue": "FR",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 8,
        "label": "CV DOCX FR",
        "file": "C_v_Pro_RanimFrancais.docx",
        "type": "docx",
        "langue": "FR",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 9,
        "label": "CV DOCX Asma",
        "file": "ASMA GHARBI.docx",
        "type": "docx",
        "langue": "FR",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
    {
        "id": 10,
        "label": "CV JPG image",
        "file": "Cv En Français.jpg",
        "type": "image_ocr",
        "langue": "FR",
        "attendu": {"nom": True, "email": False, "competences": True},
    },
]

# ─────────────────────────────────────────────────────────────────
# Seuils
# ─────────────────────────────────────────────────────────────────
SEUIL_TEXTE_MIN    = 100    # chars minimum pour extraction réussie
SEUIL_PARSING_MIN  = 0.20   # confidence minimum pour parsing réussi
SEUIL_CONFIANCE_OK = 0.55   # bon CV bien parsé


# ─────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────

def run_validation(detail: bool = False) -> Dict:
    extractor = CVExtractor()
    parser    = NLPParser()

    resultats: List[Dict] = []

    print()
    print("=" * 65)
    print("  VALIDATION COMPLETE PIPELINE — 3S TalentMatch")
    print("=" * 65)
    print(f"  Dossier CVs : {DATA_DIR}")
    print(f"  Nombre CVs  : {len(CV_TESTS)}")
    print("=" * 65)
    print()

    for cv in CV_TESTS:
        filepath = DATA_DIR / cv["file"]
        res: Dict = {
            "id":           cv["id"],
            "label":        cv["label"],
            "type":         cv["type"],
            "langue":       cv["langue"],
            "file":         cv["file"],
            "fichier_existe": filepath.exists(),
            # Extraction
            "extraction_ok":     False,
            "extraction_methode": None,
            "extraction_chars":  0,
            "extraction_temps":  0.0,
            "extraction_erreur": None,
            # Parsing
            "parsing_ok":        False,
            "nom_extrait":       None,
            "email_extrait":     None,
            "nb_competences":    0,
            "nb_experiences":    0,
            "nb_formations":     0,
            "nb_langues":        0,
            "confidence":        0.0,
            "parsing_temps":     0.0,
            "parsing_erreur":    None,
            # Champs manquants
            "champs_manquants":  [],
            "champs_faibles":    [],
            # Problèmes
            "problemes":         [],
        }

        print(f"  [{cv['id']:02d}] {cv['label']:40} ({cv['type']})")

        # ── Fichier manquant ──────────────────────────────────────
        if not filepath.exists():
            res["problemes"].append("Fichier introuvable")
            print(f"       ✗ FICHIER MANQUANT : {cv['file']}")
            resultats.append(res)
            continue

        # ── EXTRACTION ───────────────────────────────────────────
        t0 = time.time()
        try:
            ext_result = extractor.extract(str(filepath))
            res["extraction_temps"]   = round(time.time() - t0, 2)
            res["extraction_methode"] = ext_result.get("method", "?")

            if not ext_result.get("success"):
                res["extraction_erreur"] = ext_result.get("error", "Erreur inconnue")
                res["problemes"].append(f"Extraction échouée : {res['extraction_erreur']}")
            else:
                text = ext_result.get("text", "") or ""
                res["extraction_chars"] = len(text)
                if len(text) >= SEUIL_TEXTE_MIN:
                    res["extraction_ok"] = True
                else:
                    res["problemes"].append(f"Texte trop court : {len(text)} chars")

        except Exception as e:
            res["extraction_temps"]  = round(time.time() - t0, 2)
            res["extraction_erreur"] = str(e)
            res["problemes"].append(f"Exception extraction : {e}")
            text = ""

        extr_status = "OK" if res["extraction_ok"] else "FAIL"
        print(f"       Extraction : {extr_status:4}  "
              f"{res['extraction_chars']:6} chars  "
              f"{res['extraction_temps']:.2f}s  "
              f"[{res['extraction_methode']}]")

        if not res["extraction_ok"]:
            resultats.append(res)
            continue

        # ── PARSING ──────────────────────────────────────────────
        t1 = time.time()
        try:
            parse_result = parser.parse(text, cv_id=str(cv["id"]))
            res["parsing_temps"] = round(time.time() - t1, 2)

            if not parse_result.get("success"):
                res["parsing_erreur"] = parse_result.get("error", "Erreur inconnue")
                res["problemes"].append(f"Parsing échoué : {res['parsing_erreur']}")
            else:
                pd = parse_result.get("parsed_data", {})
                meta = pd.get("metadata", {})

                res["nom_extrait"]    = pd.get("identite", {}).get("nom_complet")
                res["email_extrait"]  = pd.get("contacts", {}).get("email")
                res["nb_competences"] = len(pd.get("competences", []))
                res["nb_experiences"] = len(pd.get("experiences", []))
                res["nb_formations"]  = len(pd.get("formations", []))
                res["nb_langues"]     = len(pd.get("langues", []))
                res["confidence"]     = meta.get("confidence_score", 0.0)
                res["champs_manquants"] = meta.get("champs_manquants", [])
                res["champs_faibles"]   = meta.get("champs_faibles", [])

                # Critères de réussite parsing
                if res["confidence"] >= SEUIL_PARSING_MIN:
                    res["parsing_ok"] = True
                else:
                    res["problemes"].append(
                        f"Confidence trop basse : {round(res['confidence']*100)}%"
                    )

                # Problèmes détectés
                if not res["nom_extrait"]:
                    res["problemes"].append("Nom non extrait")
                if res["nb_competences"] == 0:
                    res["problemes"].append("Aucune compétence extraite")
                if res["nb_experiences"] == 0:
                    res["problemes"].append("Aucune expérience extraite")
                if res["champs_manquants"]:
                    res["problemes"].append(
                        f"Champs manquants : {', '.join(res['champs_manquants'])}"
                    )

        except Exception as e:
            res["parsing_temps"]  = round(time.time() - t1, 2)
            res["parsing_erreur"] = str(e)
            res["problemes"].append(f"Exception parsing : {e}")

        conf_pct = round(res["confidence"] * 100)
        parse_status = "OK" if res["parsing_ok"] else "FAIL"
        print(f"       Parsing    : {parse_status:4}  "
              f"conf={conf_pct:3}%  "
              f"{res['parsing_temps']:.2f}s  "
              f"nom={'oui' if res['nom_extrait'] else 'non':3}  "
              f"skills={res['nb_competences']:3}  "
              f"exp={res['nb_experiences']}  "
              f"form={res['nb_formations']}")

        if res["problemes"] and detail:
            for p in res["problemes"]:
                print(f"         ⚠  {p}")

        resultats.append(res)

    # ─────────────────────────────────────────────────────────────
    # MÉTRIQUES GLOBALES
    # ─────────────────────────────────────────────────────────────
    existants      = [r for r in resultats if r["fichier_existe"]]
    n              = len(existants)
    n_extr_ok      = sum(1 for r in existants if r["extraction_ok"])
    n_parse_ok     = sum(1 for r in existants if r["parsing_ok"])
    conf_list      = [r["confidence"] for r in existants if r["extraction_ok"] and r["parsing_ok"]]
    conf_moy       = round(sum(conf_list) / len(conf_list), 2) if conf_list else 0.0
    t_extr_list    = [r["extraction_temps"] for r in existants if r["extraction_ok"]]
    t_parse_list   = [r["parsing_temps"] for r in existants if r["parsing_ok"]]
    t_extr_moy     = round(sum(t_extr_list) / len(t_extr_list), 2) if t_extr_list else 0.0
    t_parse_moy    = round(sum(t_parse_list) / len(t_parse_list), 2) if t_parse_list else 0.0
    conf_ok        = sum(1 for r in existants if r["confidence"] >= SEUIL_CONFIANCE_OK)

    echoues        = [r for r in existants if not r["parsing_ok"] or r["problemes"]]
    tous_problemes: List[str] = []
    for r in echoues:
        for p in r["problemes"]:
            tous_problemes.append(f"{r['label']} : {p}")

    # Recommandations automatiques
    recommandations: List[str] = []
    if any("colonne" in p.lower() or "column" in p.lower() for p in tous_problemes):
        recommandations.append("Ajouter pdfplumber pour mieux gérer les PDFs 2 colonnes")
    if any(r["langue"] == "EN" and not r["nom_extrait"] for r in existants):
        recommandations.append("Modèle spaCy EN (en_core_web_md) pour les CVs anglais")
    if any("ocr" in (r["extraction_methode"] or "") for r in existants):
        recommandations.append("Vérifier qualité OCR sur images — augmenter DPI si besoin")
    if any(r["nb_competences"] == 0 for r in existants if r["extraction_ok"]):
        recommandations.append("Enrichir dictionnaire compétences pour CVs atypiques")
    if any(r["nb_experiences"] == 0 for r in existants if r["extraction_ok"]):
        recommandations.append("Améliorer détection section Expériences pour formats non standards")
    if not recommandations:
        recommandations.append("Pipeline performant — prêt pour le matching")

    # ─────────────────────────────────────────────────────────────
    # AFFICHAGE RAPPORT
    # ─────────────────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("  RAPPORT DE VALIDATION")
    print("=" * 65)

    extr_pct  = round(n_extr_ok / n * 100) if n else 0
    parse_pct = round(n_parse_ok / n * 100) if n else 0
    conf_ok_pct = round(conf_ok / n * 100) if n else 0

    icon_e = "OK" if extr_pct  >= 80 else "!!"
    icon_p = "OK" if parse_pct >= 70 else "!!"
    icon_c = "OK" if conf_moy  >= 0.55 else "!!"

    print()
    print(f"  [{icon_e}] Extraction  : {n_extr_ok}/{n} ({extr_pct}%)   "
          f"temps moyen : {t_extr_moy}s")
    print(f"  [{icon_p}] Parsing     : {n_parse_ok}/{n} ({parse_pct}%)   "
          f"temps moyen : {t_parse_moy}s")
    print(f"  [{icon_c}] Conf. moy.  : {conf_moy} ({round(conf_moy*100)}%)  "
          f"CVs conf >= {round(SEUIL_CONFIANCE_OK*100)}% : {conf_ok}/{n}")
    print()

    # Tableau récapitulatif
    print("  " + "-" * 61)
    print(f"  {'#':>2}  {'Label':38}  {'Extr':4}  {'Pars':4}  {'Conf':5}")
    print("  " + "-" * 61)
    for r in resultats:
        if not r["fichier_existe"]:
            print(f"  {r['id']:>2}  {r['label']:38}  {'N/A':4}  {'N/A':4}  {'N/A':5}")
            continue
        e = "OK" if r["extraction_ok"] else "FAIL"
        p = "OK" if r["parsing_ok"]    else "FAIL"
        c = f"{round(r['confidence']*100):3}%"
        print(f"  {r['id']:>2}  {r['label']:38}  {e:4}  {p:4}  {c:5}")
    print("  " + "-" * 61)

    # Problèmes
    if tous_problemes:
        print()
        print("  PROBLEMES IDENTIFIES :")
        for i, p in enumerate(tous_problemes, 1):
            print(f"    {i}. {p}")

    # Recommandations
    print()
    print("  RECOMMANDATIONS :")
    for i, r in enumerate(recommandations, 1):
        print(f"    {i}. {r}")

    print()
    # Verdict final
    if parse_pct >= 80 and conf_moy >= 0.55:
        print("  >> PIPELINE VALIDE — prêt pour le matching")
    elif parse_pct >= 60:
        print("  >> PIPELINE ACCEPTABLE — quelques améliorations recommandées")
    else:
        print("  >> PIPELINE A AMELIORER avant de passer au matching")
    print("=" * 65)
    print()

    return {
        "extraction_taux": extr_pct,
        "parsing_taux":    parse_pct,
        "confidence_moy":  conf_moy,
        "temps_extr_moy":  t_extr_moy,
        "temps_parse_moy": t_parse_moy,
        "problemes":       tous_problemes,
        "recommandations": recommandations,
        "resultats":       resultats,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapport", action="store_true",
                    help="Afficher les problèmes détaillés pendant le test")
    args = ap.parse_args()
    run_validation(detail=args.rapport)
