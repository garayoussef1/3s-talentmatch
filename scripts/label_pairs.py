#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
label_pairs.py — Annotation humaine des paires (offre, CV)
===========================================================
Sélectionne 40 paires variées depuis le catalogue du dataset,
les présente une par une, collecte un label humain (0 / 0.5 / 1),
et sauvegarde dans data/human_labels.csv.

Usage :
  python scripts/label_pairs.py              # annoter toutes les paires
  python scripts/label_pairs.py --resume     # continuer une session
  python scripts/label_pairs.py --show       # afficher les labels déjà saisis

Labels :
  0   — Mauvais match (ne pas recruter)
  0.5 — Match moyen (peut-être, à évaluer)
  1   — Bon match (recruter / inviter)
  s   — Skip (passer sans annoter)
  q   — Quit (sauvegarder et quitter)
"""
from __future__ import annotations
import sys, os, csv, random, argparse, time
from pathlib import Path
from datetime import datetime

# ── Chemins ──────────────────────────────────────────────────────────────────
REPO     = Path(__file__).resolve().parent.parent
BACKEND  = REPO / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",   "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

LABELS_CSV = REPO / "data" / "human_labels.csv"
LABELS_CSV.parent.mkdir(parents=True, exist_ok=True)

LABELS_COLS = ["offre_titre", "candidat_nom", "offer_dom", "cand_dom",
               "model_score", "human_label", "timestamp"]

# ── Imports après path setup ──────────────────────────────────────────────────
import numpy as np
from app.services.matching_sandbox.bert_scorer import (
    BERTMatchingScorer, _normalize_skill, _TECH_EXPANSION,
)
from app.services.matching.match_engine import (
    _offer_text_for_semantic, _candidate_text_for_semantic
)

# ── Mock objects (copié du générateur) ───────────────────────────────────────
class Offer:
    def __init__(self, titre, desc, skills, exp=3, edu=5, domaine="", niveau=""):
        self.titre=titre; self.description=desc; self.competences_requises=skills
        self.competences_appreciees=[]; self.experience_requise=exp
        self.formation_requise_niveau=edu; self.domaine_metier=domaine
        self.niveau_seniorite=niveau; self.type_contrat="CDI"
        self.localisation=None; self.status="active"
        self.raw_text=desc+" "+" ".join(skills)

class Cand:
    def __init__(self, nom, cv, skills, exp=3, edu=5, exps=None, fmts=None):
        self.nom=nom; self.email=nom+"@x.com"; self.raw_text=cv; self.cv_id=None
        self.parsed_data={
            "competences":skills,
            "experiences":exps or [{"poste":nom,"description":cv,"duree_mois":int(exp*12)}],
            "formations":fmts or [],
            "metadata":{"annees_experience_totales":exp,"niveau_formation_max":edu},
        }

# ── Catalogue (25 offres × 28 candidats = 700 paires potentielles) ───────────
# Identique au générateur, mais avec métadonnées domaine pour sélection variée
OFFERS = [
    # IT
    ("Dev Python FastAPI",     "it",  Offer("Développeur Python FastAPI","CDI Python FastAPI PostgreSQL Docker Bac+5 3 ans",["Python","FastAPI","PostgreSQL","Docker","Git"],exp=3,edu=5,niveau="Confirmé")),
    ("Dev Python Senior",      "it",  Offer("Développeur Python Senior","CDI Python 5 ans FastAPI Django Redis Kubernetes Bac+5",["Python","FastAPI","Django","PostgreSQL","Redis","Kubernetes"],exp=5,edu=5,niveau="Senior")),
    ("Stage Dev Python",       "it",  Offer("Stage Développeur Python","Stage Python Django REST Bac+4",["Python","Django","REST API","Git"],exp=0,edu=4,niveau="Stage")),
    ("Dev React Frontend",     "it",  Offer("Développeur React Frontend","CDI React TypeScript Node CSS Bac+3 2 ans",["React","TypeScript","Node.js","CSS","Figma"],exp=2,edu=3,niveau="Junior")),
    ("Ingénieur DevOps",       "it",  Offer("Ingénieur DevOps Cloud","CDI DevOps Kubernetes Docker Terraform AWS CI/CD 3 ans Bac+5",["DevOps","Kubernetes","Docker","Terraform","AWS","CI/CD"],exp=3,edu=5,niveau="Confirmé")),
    ("Data Scientist",         "it",  Offer("Data Scientist ML","CDI Machine Learning Python TensorFlow scikit-learn Pandas 3 ans Bac+5",["Machine Learning","Python","TensorFlow","scikit-learn","Pandas","SQL"],exp=3,edu=5,niveau="Confirmé")),
    # Finance
    ("Contrôleur Gestion",    "finance", Offer("Contrôleur de Gestion","CDI contrôle gestion Excel SAP IFRS reporting 3 ans Bac+5",["Contrôle de gestion","Excel","SAP","IFRS","Reporting financier","Analyse financière"],exp=3,edu=5,niveau="Confirmé")),
    ("Comptable Senior",      "finance", Offer("Comptable Senior","CDI comptabilité SAP IFRS bilan audit 5 ans Bac+5",["Comptabilité générale","SAP","IFRS","Audit interne","Fiscalité","Excel"],exp=5,edu=5,niveau="Senior")),
    ("Auditeur Junior",       "finance", Offer("Auditeur Interne Junior","CDD audit interne comptabilité Excel reporting Bac+3",["Audit interne","Comptabilité","Excel","Reporting financier"],exp=1,edu=3,niveau="Junior")),
    # RH
    ("Chargé RH",             "rh",  Offer("Chargé RH Recrutement","CDI recrutement sourcing LinkedIn GPEC paie droit travail Bac+3 2 ans",["Recrutement","RH","LinkedIn","Paie","GPEC","Droit du travail"],exp=2,edu=3,niveau="Junior")),
    ("Responsable RH Senior", "rh",  Offer("Responsable RH Senior","CDI RH SIRH GPEC paie relations sociales 7 ans Bac+5",["RH","SIRH","GPEC","Gestion paie","Relations sociales","Droit du travail"],exp=7,edu=5,niveau="Senior")),
    # Santé
    ("Infirmier IDE",         "sante", Offer("Infirmier IDE Soins Intensifs","CDI infirmier IDE soins intensifs réanimation urgences ECG Bac+3",["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences","ECG"],exp=2,edu=3)),
    ("Infirmier Senior",      "sante", Offer("Infirmier Urgences Senior","CDI infirmier urgences réanimation soins critiques 5 ans Bac+3",["Soins infirmiers","Urgences","Réanimation","Soins critiques","ECG"],exp=5,edu=3,niveau="Senior")),
    # Droit
    ("Juriste Affaires",      "droit", Offer("Juriste Droit des Affaires","CDI juriste droit affaires contrats RGPD conformité 3 ans Bac+5",["Droit des affaires","Contrats","RGPD","Conformité","Droit commercial"],exp=3,edu=5)),
    # BTP
    ("Ingénieur GC",          "btp",  Offer("Ingénieur Génie Civil","CDI génie civil BIM AutoCAD Revit chantier 3 ans Bac+5",["Génie civil","BIM","AutoCAD","Revit","Suivi de chantier"],exp=3,edu=5)),
    # Logistique
    ("Resp Logistique",       "logistique", Offer("Responsable Logistique","CDI logistique supply chain SAP WMS stocks transport 3 ans Bac+5",["Logistique","Supply chain","Gestion des stocks","SAP","WMS","Transport"],exp=3,edu=5)),
    # Marketing
    ("Chef Projet Mktg",      "marketing", Offer("Chef de Projet Marketing","CDI marketing digital SEO Google Ads CRM 3 ans Bac+5",["Marketing digital","SEO","Google Ads","CRM","HubSpot","Community Management"],exp=3,edu=5)),
]

CANDS = [
    # IT
    ("Dev Python 5ans",    "it",  Cand("Dev Python 5ans","Python 5 ans FastAPI Django PostgreSQL Docker Redis Kubernetes CI/CD Bac+5",["Python","FastAPI","Django","PostgreSQL","Docker","Redis","Git","CI/CD"],exp=5,edu=5)),
    ("Dev Python 2ans",    "it",  Cand("Dev Python 2ans","Python 2 ans FastAPI PostgreSQL Docker Git REST Bac+5",["Python","FastAPI","PostgreSQL","Docker","Git"],exp=2,edu=5)),
    ("Stage Python",       "it",  Cand("Stage Python","Etudiant Python Django REST stage Bac+4",["Python","Django","REST API","Git"],exp=0,edu=4)),
    ("Dev React 3ans",     "it",  Cand("Dev React 3ans","React TypeScript Node.js CSS Redux 3 ans Bac+3",["React","TypeScript","Node.js","CSS","Redux"],exp=3,edu=3)),
    ("DevOps 4ans",        "it",  Cand("DevOps 4ans","DevOps Kubernetes Docker Terraform AWS CI/CD Jenkins 4 ans Bac+5",["DevOps","Kubernetes","Docker","Terraform","AWS","CI/CD","Jenkins"],exp=4,edu=5)),
    ("Data Scientist 3ans","it",  Cand("Data Scientist 3ans","Machine Learning Python TensorFlow scikit-learn Pandas SQL NLP 3 ans Bac+5",["Machine Learning","Python","TensorFlow","scikit-learn","Pandas","SQL","NLP"],exp=3,edu=5)),
    ("Dev Java 4ans",      "it",  Cand("Dev Java 4ans","Java Spring Boot Hibernate PostgreSQL Docker Maven 4 ans Bac+5",["Java","Spring Boot","PostgreSQL","Docker","Maven","Git"],exp=4,edu=5)),
    ("Dev Java Junior",    "it",  Cand("Dev Java Junior","Java Spring Boot MySQL débutant 1 an Bac+3",["Java","Spring Boot","MySQL","Git"],exp=1,edu=3)),
    # Finance
    ("Comptable 5ans",     "finance", Cand("Comptable 5ans","Comptabilité SAP IFRS bilan audit interne fiscalité contrôle gestion 5 ans Bac+5",["Comptabilité générale","SAP","IFRS","Audit interne","Fiscalité","Contrôle de gestion","Excel"],exp=5,edu=5)),
    ("Contrôleur GS 3ans", "finance", Cand("Contrôleur GS 3ans","Contrôle gestion SAP IFRS Excel reporting analyse financière 3 ans Bac+5",["Contrôle de gestion","SAP","IFRS","Excel","Reporting financier","Analyse financière"],exp=3,edu=5)),
    ("Auditeur 2ans",      "finance", Cand("Auditeur 2ans","Audit interne comptabilité Excel reporting 2 ans Bac+3",["Audit interne","Comptabilité","Excel","Reporting financier"],exp=2,edu=3)),
    ("Comptable Junior",   "finance", Cand("Comptable Junior 1an","Comptable débutant 1 an SAP Excel IFRS reporting Bac+5",["Comptabilité","SAP","Excel","IFRS","Reporting financier"],exp=1,edu=5)),
    # RH
    ("Chargée RH 3ans",    "rh",  Cand("Chargée RH 3ans","RH recrutement sourcing LinkedIn paie GPEC droit travail SIRH 3 ans Bac+3",["RH","Recrutement","LinkedIn","Paie","GPEC","Droit du travail","SIRH"],exp=3,edu=3)),
    ("Responsable RH 7ans","rh",  Cand("Responsable RH 7ans","RH SIRH GPEC gestion paie relations sociales droit travail 7 ans Bac+5",["RH","SIRH","GPEC","Gestion paie","Relations sociales","Droit du travail"],exp=7,edu=5)),
    ("Recruteur Junior",   "rh",  Cand("Recruteur Junior","Recrutement sourcing LinkedIn débutant 1 an Bac+3",["Recrutement","LinkedIn","Sourcing"],exp=1,edu=3)),
    ("HR Manager EN",      "rh",  Cand("HR Manager EN","HR Manager talent management recruiting human resources payroll 4 ans Bac+5",["talent management","recruiting","human resources","payroll","HRIS"],exp=4,edu=5)),
    # Santé
    ("Infirmier IDE 4ans", "sante", Cand("Infirmier IDE 4ans","Infirmier IDE soins intensifs réanimation urgences ECG 4 ans Bac+3",["Soins infirmiers","IDE","Soins intensifs","Réanimation","Urgences","ECG"],exp=4,edu=3)),
    ("Infirmier 2ans",     "sante", Cand("Infirmier 2ans","Infirmier urgences réanimation soins critiques ECG 2 ans Bac+3",["Soins infirmiers","Urgences","Réanimation","Soins critiques","ECG"],exp=2,edu=3)),
    # Droit
    ("Juriste Affaires 4ans","droit", Cand("Juriste Affaires 4ans","Juriste droit affaires contrats RGPD conformité 4 ans Bac+5",["Droit des affaires","Contrats","RGPD","Conformité","Droit commercial"],exp=4,edu=5)),
    # BTP
    ("Ingénieur GC 4ans",  "btp",  Cand("Ingénieur GC 4ans","Ingénieur génie civil BIM AutoCAD Revit chantier 4 ans Bac+5",["Génie civil","BIM","AutoCAD","Revit","Suivi de chantier"],exp=4,edu=5)),
    # Logistique
    ("Resp Logistique 4ans","logistique", Cand("Resp Logistique 4ans","Logistique supply chain SAP WMS stocks transport 4 ans Bac+5",["Logistique","Supply chain","Gestion des stocks","SAP","WMS","Transport"],exp=4,edu=5)),
    # Marketing
    ("Chef Mktg 3ans",     "marketing", Cand("Chef Mktg 3ans","Marketing digital SEO Google Ads CRM HubSpot 3 ans Bac+5",["Marketing digital","SEO","Google Ads","CRM","HubSpot","Community Management"],exp=3,edu=5)),
]


# ── Sélection des 40 paires ───────────────────────────────────────────────────
def select_pairs(scorer: BERTMatchingScorer) -> list:
    """Génère toutes les paires, les score, sélectionne 40 variées."""
    random.seed(42)
    all_pairs = []

    print("Calcul des scores sur toutes les paires...")
    # Batch encode
    all_texts = (
        [o.raw_text for _, _, o in OFFERS] +
        [c.raw_text for _, _, c in CANDS]
    )
    embs = scorer._st_model.encode(
        all_texts, batch_size=16, normalize_embeddings=True, show_progress_bar=True
    )
    offer_embs = np.array(embs[:len(OFFERS)])
    cand_embs  = np.array(embs[len(OFFERS):])
    sim_matrix = offer_embs @ cand_embs.T

    for oi, (oname, odom, offer) in enumerate(OFFERS):
        for ci, (cname, cdom, cand) in enumerate(CANDS):
            sem = float(np.clip(sim_matrix[oi, ci], 0, 1))
            # Estimation rapide du score sans full scorer.score() pour la sélection
            same_dom = (odom == cdom)
            all_pairs.append({
                "oi": oi, "ci": ci,
                "oname": oname, "cname": cname,
                "odom": odom, "cdom": cdom,
                "offer": offer, "cand": cand,
                "sem": sem,
                "same_dom": same_dom,
            })

    # Tri par sémantique (proxy du score) pour sélection stratifiée
    all_pairs.sort(key=lambda p: p["sem"])

    # 15 confiant bas (sem < 0.55 et hors-domaine)
    conf_low  = [p for p in all_pairs if p["sem"] < 0.55 and not p["same_dom"]][:20]
    # 15 hésitants (sem 0.55–0.70 ou même domaine partiel)
    hesitant  = [p for p in all_pairs if 0.55 <= p["sem"] <= 0.72][:25]
    # 10 confiant haut (même domaine, sem > 0.70)
    conf_high = [p for p in all_pairs if p["sem"] > 0.70 and p["same_dom"]][:15]

    selected  = (
        random.sample(conf_high, min(15, len(conf_high))) +
        random.sample(hesitant,  min(15, len(hesitant))) +
        random.sample(conf_low,  min(10, len(conf_low)))
    )
    random.shuffle(selected)

    # Dédupliquer
    seen = set()
    result = []
    for p in selected:
        k = (p["oi"], p["ci"])
        if k not in seen:
            seen.add(k)
            result.append(p)

    return result[:40]


# ── Charger les labels déjà saisis ───────────────────────────────────────────
def load_existing_labels() -> dict:
    """Retourne {(offre_titre, candidat_nom): human_label}."""
    done = {}
    if not LABELS_CSV.exists():
        return done
    with open(LABELS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            k = (row["offre_titre"], row["candidat_nom"])
            done[k] = float(row["human_label"])
    return done


def save_label(row: dict) -> None:
    exists = LABELS_CSV.exists()
    with open(LABELS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LABELS_COLS)
        if not exists:
            w.writeheader()
        w.writerow(row)


# ── Affichage d'une paire ─────────────────────────────────────────────────────
def display_pair(idx: int, total: int, p: dict, details: dict, score: float) -> None:
    offer  = p["offer"]; cand = p["cand"]
    matched = [m["skill"] if isinstance(m, dict) else m for m in details.get("skills_matched", [])]
    missing = [m["skill"] if isinstance(m, dict) else m for m in details.get("skills_missing", [])]
    crit_ok = details.get("skills_criticality", {})

    print(f"\n{'='*65}")
    print(f"  Paire {idx}/{total}  |  Domaines : {p['odom']} → {p['cdom']}")
    print(f"{'='*65}")
    print(f"  OFFRE    : {offer.titre}")
    print(f"  Skills   : {', '.join(offer.competences_requises[:6])}")
    print(f"  Exp req  : {offer.experience_requise} ans | Edu req : Bac+{offer.formation_requise_niveau}")
    print(f"  {'─'*61}")
    print(f"  CANDIDAT : {cand.nom}")
    print(f"  Skills   : {', '.join(cand.parsed_data['competences'][:6])}")
    exp_c = cand.parsed_data['metadata'].get('annees_experience_totales', 0)
    edu_c = cand.parsed_data['metadata'].get('niveau_formation_max', 0)
    print(f"  Exp cand : {exp_c} ans | Edu cand : Bac+{edu_c}")
    print(f"  {'─'*61}")
    pct = score * 100
    conf = "confiant" if abs(score - 0.5) > 0.25 else "hésitant"
    print(f"  Score modèle : {pct:.1f}%  [{conf}]")
    print(f"  Compétences  : {details.get('competences',0):.0f}%  Exp: {details.get('experience',0):.0f}%  Form: {details.get('formation',0):.0f}%")
    if matched:
        crit_matched = [s for s in matched if crit_ok.get(s) == "critique"]
        print(f"  ✓ Matchées   : {', '.join(matched[:5])}" + (f" (+{len(matched)-5})" if len(matched) > 5 else ""))
        if crit_matched: print(f"    ★ Critiques : {', '.join(crit_matched)}")
    if missing:
        crit_miss = [s for s in missing if crit_ok.get(s) == "critique"]
        print(f"  ✗ Manquantes : {', '.join(missing[:5])}" + (f" (+{len(missing)-5})" if len(missing) > 5 else ""))
        if crit_miss: print(f"    ★ Critique manquante : {', '.join(crit_miss)}")
    print(f"{'─'*65}")


# ── Boucle d'annotation ───────────────────────────────────────────────────────
def annotate(pairs: list, scorer: BERTMatchingScorer, resume: bool) -> None:
    done = load_existing_labels() if resume else {}
    total = len(pairs)
    annotated = skipped = 0

    print(f"\nAnnotation de {total} paires. Touches : 0 / 0.5 / 1 / s (skip) / q (quit)")
    if done:
        print(f"  {len(done)} labels déjà présents — les paires déjà annotées seront ignorées.")

    for idx, p in enumerate(pairs, 1):
        key = (p["offer"].titre, p["cand"].nom)
        if key in done:
            print(f"  #{idx:02d} déjà annoté ({p['offer'].titre} × {p['cand'].nom}) → {done[key]}")
            continue

        # Score complet pour l'affichage
        try:
            score, details = scorer.score(p["offer"], p["cand"])
        except Exception as e:
            print(f"  #{idx:02d} ERREUR score : {e} — skip")
            skipped += 1
            continue

        display_pair(idx, total, p, details, score)

        while True:
            try:
                inp = input("  Votre label [0 / 0.5 / 1 / s / q] : ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Interruption — sauvegarde en cours...")
                break
            if inp == "q":
                print(f"\n  Arrêt. {annotated} labels sauvegardés.")
                return
            if inp == "s":
                skipped += 1
                break
            if inp in ("0", "0.5", "1"):
                label = float(inp)
                save_label({
                    "offre_titre":   p["offer"].titre,
                    "candidat_nom":  p["cand"].nom,
                    "offer_dom":     p["odom"],
                    "cand_dom":      p["cdom"],
                    "model_score":   round(score, 4),
                    "human_label":   label,
                    "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                annotated += 1
                icon = "✓" if abs(score - label) < 0.3 else "⚠"
                print(f"  {icon}  Sauvegardé : label={label}  (modèle={score*100:.1f}%)")
                break
            print("  Entrée invalide — taper 0, 0.5, 1, s ou q")

    print(f"\n{'='*65}")
    print(f"  Terminé. Annotés={annotated}, Skippés={skipped}")
    print(f"  Labels dans : {LABELS_CSV}")
    print("=" * 65)


# ── Affichage des labels existants ────────────────────────────────────────────
def show_labels() -> None:
    if not LABELS_CSV.exists():
        print("Aucun label encore — lancez label_pairs.py sans --show.")
        return
    rows = []
    with open(LABELS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"\n{len(rows)} labels dans {LABELS_CSV}")
    print(f"{'Offre':30s} {'Candidat':25s} {'Modèle':8s} {'Label':6s} {'Accord'}")
    print("-" * 80)
    agree = disagree = 0
    for r in rows:
        ms = float(r["model_score"]); hl = float(r["human_label"])
        ok = abs(ms - hl) < 0.3
        if ok: agree += 1
        else:  disagree += 1
        icon = "✓" if ok else "✗"
        print(f"{r['offre_titre'][:30]:30s} {r['candidat_nom'][:25]:25s} {ms*100:5.1f}%  {hl:4.1f}  {icon}")
    print(f"\nAccord modèle/humain : {agree}/{len(rows)} ({100*agree//max(len(rows),1)}%)")
    print(f"Désaccords           : {disagree}")

    disagree_rows = [r for r in rows if abs(float(r["model_score"]) - float(r["human_label"])) >= 0.3]
    if disagree_rows:
        print(f"\nDésaccords significatifs (Δ ≥ 0.3) :")
        for r in disagree_rows:
            ms = float(r["model_score"]); hl = float(r["human_label"])
            direction = "trop haut" if ms > hl else "trop bas"
            print(f"  {r['offre_titre'][:28]:28s} × {r['candidat_nom'][:20]:20s} modèle={ms*100:.0f}% humain={hl} → {direction}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Annotation humaine de paires offre/CV")
    parser.add_argument("--resume", action="store_true", help="Continuer une session (sauter les déjà annotés)")
    parser.add_argument("--show",   action="store_true", help="Afficher les labels existants sans annoter")
    parser.add_argument("--n",      type=int, default=40, help="Nombre de paires à annoter (défaut: 40)")
    args = parser.parse_args()

    if args.show:
        show_labels()
        return

    print("Chargement du scorer BGE-M3...")
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    print("Scorer OK.\n")

    pairs = select_pairs(scorer)
    print(f"\n{len(pairs)} paires sélectionnées :")
    conf_h  = sum(1 for p in pairs if p["sem"] > 0.70 and p["same_dom"])
    hesit   = sum(1 for p in pairs if 0.55 <= p["sem"] <= 0.72)
    hors    = sum(1 for p in pairs if p["sem"] < 0.55 and not p["same_dom"])
    print(f"  Confiant haut (bon match attendu) : {conf_h}")
    print(f"  Hésitants (score 40-70%)          : {hesit}")
    print(f"  Hors-domaine (mauvais attendu)    : {hors}")

    annotate(pairs[:args.n], scorer, resume=args.resume)


if __name__ == "__main__":
    main()
