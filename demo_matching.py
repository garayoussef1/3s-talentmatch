"""
Demo Matching — 3S TalentMatch PFE ESPRIT
==========================================
Compare Heuristique vs Sentence-BERT sur de vrais CVs.
Aucune base de données requise.

Usage:
    .venv-10\Scripts\python.exe demo_matching.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from types import SimpleNamespace

# Ajouter le backend au path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.extraction.cv_extractor import CVExtractor
from app.services.nlp.nlp_parser import NLPParser
from app.services.matching.match_engine import MatchEngine
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer

# ─────────────────────────────────────────────
# Offres fictives réalistes
# ─────────────────────────────────────────────
OFFRES = [
    SimpleNamespace(
        titre="Ingénieur Backend Python",
        description=(
            "Nous recherchons un ingénieur backend avec 2 ans d'expérience. "
            "Bac+5 requis. Maîtrise de Python, FastAPI, Docker, SQL, REST APIs. "
            "Expérience en développement de microservices appréciée."
        ),
        competences_requises=["Python", "FastAPI", "Docker", "SQL", "REST API"],
        localisation="Tunis",
    ),
    SimpleNamespace(
        titre="Data Scientist / ML Engineer",
        description=(
            "Poste de Data Scientist avec expérience en Machine Learning et Deep Learning. "
            "Bac+5. Maîtrise Python, TensorFlow ou PyTorch, Pandas, Scikit-learn. "
            "Expérience en NLP ou Computer Vision est un plus."
        ),
        competences_requises=["Python", "Machine Learning", "TensorFlow", "Pandas", "Deep Learning"],
        localisation="Tunis",
    ),
    SimpleNamespace(
        titre="Développeur Mobile React Native",
        description=(
            "Développeur mobile avec expérience React Native et développement iOS/Android. "
            "Bac+3 minimum. Connaissances JavaScript, TypeScript, Git."
        ),
        competences_requises=["React Native", "JavaScript", "TypeScript", "Mobile", "Git"],
        localisation="Tunis",
    ),
]

# CVs à tester (noms courts pour l'affichage)
CVS_CIBLES = [
    ("Wajih (EN)",  "Wajih Mokhtar Alouini CV ENGLISH .pdf"),
    ("Wajih (FR)",  "Wajih Mokhtar Alouini CV FRENCH.pdf"),
    ("Maram",       "MaramSliti Cv.pdf"),
    ("Ines",        "Ines_ben_saad_CV.pdf"),
    ("Ahmed Aziz",  "AhmedAziz_Ammar (1).pdf"),
    ("Ranim (EN)",  "C_v_Pro_RanimEnglish.pdf"),
]

def load_cv(cv_path: Path, extractor: CVExtractor, parser: NLPParser):
    """Charge et parse un CV. Retourne un objet candidat mock."""
    r = extractor.extract(str(cv_path))
    if not r.get("success"):
        return None
    res = parser.parse(r["text"], cv_id=cv_path.stem)
    return SimpleNamespace(
        raw_text=r["text"],
        parsed_data=res["parsed_data"],
        nom=res["parsed_data"].get("identite", {}).get("nom", cv_path.stem),
    )

def barre(score: float, width: int = 20) -> str:
    """Barre de progression ASCII."""
    filled = int(score * width)
    return "█" * filled + "░" * (width - filled)

def main():
    cv_dir = Path(__file__).parent / "data" / "Cv"
    print("\n" + "="*70)
    print("  3S TalentMatch - Demo Matching IA")
    print("="*70)

    print("\n[...] Chargement des modeles...")
    extractor = CVExtractor()
    parser = NLPParser()
    engine = MatchEngine()
    bert = BERTMatchingScorer()

    # Forcer le chargement du modele maintenant (lazy load)
    bert._get_model()
    if bert.ready:
        print(f"[OK] BERT pret : {bert.model_name}")
    else:
        print(f"[!!] BERT indisponible : {bert.load_error}")

    # Charger les CVs
    print("\n[...] Chargement des CVs...")
    candidats = []
    for label, filename in CVS_CIBLES:
        cv_path = cv_dir / filename
        if not cv_path.exists():
            continue
        c = load_cv(cv_path, extractor, parser)
        if c:
            candidats.append((label, c))
            print(f"  [OK] {label:15s} - {c.nom}")

    # Pour chaque offre, comparer les candidats
    for offre in OFFRES:
        print(f"\n{'='*70}")
        print(f"  OFFRE : {offre.titre}")
        print(f"  Skills: {', '.join(offre.competences_requises)}")
        print(f"{'='*70}")
        print(f"  {'Candidat':<18} {'Heuristique':>12} {'BERT':>10} {'Diff':>8}  Meilleur")
        print(f"  {'-'*60}")

        resultats = []
        for label, candidat in candidats:
            h_score, _ = engine.score(offre, candidat)
            b_score, b_details = bert.score(offre, candidat)
            diff = b_score - h_score
            resultats.append((label, h_score, b_score, diff, b_details))

        # Trier par score BERT
        resultats.sort(key=lambda x: x[2], reverse=True)

        for i, (label, h, b, diff, details) in enumerate(resultats):
            meilleur = "#1" if i == 0 else ("#2" if i == 1 else "  ")
            diff_str = f"+{diff:.0%}" if diff >= 0 else f"{diff:.0%}"
            diff_color = "^" if diff > 0.05 else ("v" if diff < -0.05 else "=")
            print(f"  {label:<18} {h:>10.1%}   {b:>8.1%}  {diff_str:>7} {diff_color}  {meilleur}")

            # Détails BERT
            if details.get("ready"):
                sem = details.get("bert_semantic", 0)
                ski = details.get("bert_skills", 0)
                inc = len(details.get("inconsistencies", []))
                pen = details.get("penalty", 0)
                print(f"  {'':18}   sem:{sem:.0%}  skills:{ski:.0%}  inco:{inc}  pen:-{pen:.0%}")

        # Résumé
        bert_scores = [r[2] for r in resultats]
        heur_scores = [r[1] for r in resultats]
        avg_diff = sum(r[3] for r in resultats) / len(resultats) if resultats else 0
        print(f"\n  >> BERT moyen: {sum(bert_scores)/len(bert_scores):.1%}  |  "
              f"Heuristique moyen: {sum(heur_scores)/len(heur_scores):.1%}  |  "
              f"Diff moyenne: {avg_diff:+.1%}")

    print(f"\n{'='*70}")
    print("  FIN DE LA DÉMONSTRATION")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
