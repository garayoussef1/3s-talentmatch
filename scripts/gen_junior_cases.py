# -*- coding: utf-8 -*-
"""
gen_junior_cases.py — Génère des cas junior/stage variés pour annotation humaine (B).

But : enseigner au MLP que, sur les postes junior/stage, un candidat avec PEU de
compétences (même bien diplômé) ne doit pas être bien classé. On fait varier le
nombre de compétences (2/5 → 5/5) sur des titres génériques ET spécifiques.

Sortie : affiche un tableau (score actuel + features) pour annotation, et écrit
les features dans data/junior_cases_features.csv (réutilisé après annotation).
"""
import sys, os, csv, warnings
warnings.filterwarnings("ignore")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "backend"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer

OUT = os.path.join(REPO, "data", "junior_cases_features.csv")


class Offer:
    def __init__(self, titre, desc, skills, exp=0, edu=4, niveau="Stage"):
        self.titre = titre; self.description = desc
        self.competences_requises = skills; self.competences_appreciees = []
        self.experience_requise = exp; self.formation_requise_niveau = edu
        self.domaine_metier = ""; self.niveau_seniorite = niveau
        self.type_contrat = "Stage"; self.localisation = None; self.status = "active"
        self.nb_postes = 1
        self.raw_text = desc + " " + " ".join(skills)

class Cand:
    def __init__(self, nom, cv, skills, exp=0, edu=4, spec="Informatique"):
        self.nom = nom; self.email = "x@x.com"; self.raw_text = cv; self.cv_id = None
        self.parsed_data = {
            "competences": skills,
            "experiences": [{"poste": nom, "description": cv, "duree_mois": int(exp * 12)}],
            "formations": [{"diplome": "Licence", "specialite": spec, "niveau_bac_plus": edu}],
            "metadata": {"annees_experience_totales": exp, "niveau_formation_max": edu},
        }


# ── Offres junior/stage (génériques + spécifiques) ────────────────────────────
O_STAGE_WEB = Offer("Stage Développement Web Full Stack",
    "Stage développement web full stack Python React Node.js Git",
    ["Python","React","Node.js","Git","HTML"], exp=0, edu=4, niveau="Stage")
O_JUNIOR_REACT = Offer("Développeur React Junior",
    "Junior React TypeScript JavaScript CSS",
    ["React","TypeScript","JavaScript","CSS","HTML"], exp=1, edu=3, niveau="Junior")

# ── Candidats à compétences croissantes (même diplôme Bac+4 info) ──────────────
CASES = [
    # (offre, candidat) — compétences de faible à fort
    (O_STAGE_WEB, Cand("Stagiaire 2/5 (faible)",
        "Python HTML CSS débutant Bac+4", ["Python","HTML","CSS"], edu=4)),
    (O_STAGE_WEB, Cand("Stagiaire 3/5 (moyen)",
        "Python React HTML CSS Git Bac+4", ["Python","React","HTML","Git"], edu=4)),
    (O_STAGE_WEB, Cand("Stagiaire 4/5 (bon)",
        "Python React Node.js Git HTML projets Bac+4",
        ["Python","React","Node.js","Git"], edu=4)),
    (O_STAGE_WEB, Cand("Stagiaire 5/5 (excellent)",
        "Python React Node.js Git HTML CSS Express projets Bac+4",
        ["Python","React","Node.js","Git","HTML","CSS","Express.js"], edu=4)),
    (O_JUNIOR_REACT, Cand("Junior React 2/5 (faible)",
        "JavaScript HTML CSS débutant Bac+3", ["JavaScript","HTML","CSS"], edu=3)),
    (O_JUNIOR_REACT, Cand("Junior React 3/5 (moyen)",
        "React JavaScript HTML CSS Bac+3", ["React","JavaScript","HTML"], edu=3)),
    (O_JUNIOR_REACT, Cand("Junior React 5/5 (excellent)",
        "React TypeScript JavaScript CSS HTML Redux Bac+3",
        ["React","TypeScript","JavaScript","CSS","HTML"], edu=3)),
]

FEATURE_COLS = ["sem_sim","skill_rate_w","exp_score","form_score","sem_v2",
                "edu_dom_compat","exp_dom_ratio","title_skill_match",
                "crit_skill_ratio","offer_type_enc"]


def main():
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()

    print("=" * 84)
    print("  CAS JUNIOR/STAGE À ANNOTER (B) — score actuel + compétences")
    print("=" * 84)
    print(f"  {'#':2} {'Score':6} {'Candidat':26} {'Offre':22} {'Comp.':6} {'Skills matchées'}")
    print(f"  {'─'*2} {'─'*6} {'─'*26} {'─'*22} {'─'*6} {'─'*22}")

    rows = []
    for i, (offer, cand) in enumerate(CASES, 1):
        score, det = scorer.score(offer, cand)
        feats = det.get("mlp_features_10d", [])
        comp = det.get("competences", 0)
        matched = [m["skill"] if isinstance(m, dict) else m
                   for m in det.get("skills_matched", [])]
        print(f"  {i:2} {score*100:5.1f}% {cand.nom[:26]:26} {offer.titre[:22]:22} "
              f"{comp:4.0f}% {', '.join(matched[:4])}")
        rows.append({
            "idx": i,
            "offre": offer.titre,
            "candidat": cand.nom,
            "model_score": round(score, 4),
            **{c: round(feats[j], 4) for j, c in enumerate(FEATURE_COLS)},
        })

    # Sauvegarde des features pour le réentraînement post-annotation
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["idx","offre","candidat","model_score"] + FEATURE_COLS)
        w.writeheader()
        w.writerows(rows)

    print("\n  Features sauvegardées :", OUT)
    print("\n  → Donne-moi tes labels (0 = mauvais, 0.5 = moyen, 1 = bon), format : 1=.., 2=..")
    print("    Logique recruteur attendue : 2/5 skills → bas, 5/5 → haut.")


if __name__ == "__main__":
    main()
