"""Écrit les labels humains dans data/human_labels.csv."""
import csv, os
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT  = REPO / "data" / "human_labels.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

COLS = ["offre_titre","candidat_nom","offer_dom","cand_dom",
        "model_score","human_label","timestamp"]

PAIRS = [
    ("Développeur Python Senior",       "Dev Python 2ans",        "it",         "it",         0.723, 0.5),
    ("Infirmier Urgences Senior",        "Responsable RH 7ans",   "sante",      "rh",         0.091, 0.0),
    ("Infirmier IDE Soins Intensif",     "Infirmier IDE 4ans",     "sante",      "sante",      0.888, 1.0),
    ("Contrôleur de Gestion",            "Comptable 5ans",         "finance",    "finance",    0.760, 1.0),
    ("Chargé RH Recrutement",            "Ingénieur GC 4ans",      "rh",         "btp",        0.146, 0.0),
    ("Ingénieur DevOps Cloud",           "Dev Python 5ans",        "it",         "it",         0.361, 0.5),
    ("Développeur React Frontend",       "Infirmier IDE 4ans",     "it",         "sante",      0.050, 0.0),
    ("Stage Développeur Python",         "Dev Python 2ans",        "it",         "it",         0.834, 0.5),
    ("Auditeur Interne Junior",          "Juriste Affaires 4ans",  "finance",    "droit",      0.117, 0.0),
    ("Infirmier IDE Soins Intensif",     "HR Manager EN",          "sante",      "rh",         0.104, 0.0),
    ("Contrôleur de Gestion",            "Auditeur 2ans",          "finance",    "finance",    0.309, 0.5),
    ("Développeur React Frontend",       "Dev React 3ans",         "it",         "it",         0.761, 1.0),
    ("Auditeur Interne Junior",          "Dev Java 4ans",          "finance",    "it",         0.222, 0.0),
    ("Chargé RH Recrutement",            "Responsable RH 7ans",   "rh",         "rh",         0.375, 0.5),
    ("Développeur Python Senior",        "Recruteur Junior",       "it",         "rh",         0.119, 0.0),
    ("Infirmier Urgences Senior",        "Infirmier IDE 4ans",     "sante",      "sante",      0.801, 1.0),
    ("Ingénieur DevOps Cloud",           "Dev React 3ans",         "it",         "it",         0.235, 0.0),
    ("Juriste Droit des Affaires",       "Chargée RH 3ans",        "droit",      "rh",         0.454, 0.5),
    ("Responsable RH Senior",            "Resp Logistique 4ans",   "rh",         "logistique", 0.116, 0.0),
    ("Infirmier Urgences Senior",        "Dev Java Junior",        "sante",      "it",         0.075, 0.0),
    ("Infirmier IDE Soins Intensif",     "Infirmier 2ans",         "sante",      "sante",      0.784, 1.0),
    ("Infirmier IDE Soins Intensif",     "Comptable Junior 1an",   "sante",      "finance",    0.099, 0.0),
    ("Responsable RH Senior",            "Dev Java Junior",        "rh",         "it",         0.119, 0.0),
    ("Juriste Droit des Affaires",       "Dev Python 5ans",        "droit",      "it",         0.103, 0.0),
    ("Chargé RH Recrutement",            "Recruteur Junior",       "rh",         "rh",         0.518, 0.5),
    ("Juriste Droit des Affaires",       "Ingénieur GC 4ans",      "droit",      "btp",        0.112, 0.0),
    ("Infirmier Urgences Senior",        "Juriste Affaires 4ans",  "sante",      "droit",      0.050, 0.0),
    ("Responsable Logistique",           "DevOps 4ans",            "logistique", "it",         0.224, 0.0),
    ("Auditeur Interne Junior",          "Auditeur 2ans",          "finance",    "finance",    0.881, 1.0),
    ("Data Scientist ML",                "Resp Logistique 4ans",   "it",         "logistique", 0.108, 0.0),
    ("Infirmier IDE Soins Intensif",     "Dev Java 4ans",          "sante",      "it",         0.104, 0.0),
    ("Juriste Droit des Affaires",       "Dev Java Junior",        "droit",      "it",         0.089, 0.0),
    ("Responsable RH Senior",            "Chargée RH 3ans",        "rh",         "rh",         0.748, 0.5),
    ("Chef de Projet Marketing",         "Chargée RH 3ans",        "marketing",  "rh",         0.125, 0.0),
    ("Comptable Senior",                 "Auditeur 2ans",          "finance",    "finance",    0.331, 0.5),
    ("Infirmier Urgences Senior",        "DevOps 4ans",            "sante",      "it",         0.079, 0.0),
    ("Stage Développeur Python",         "Comptable Junior 1an",   "it",         "finance",    0.231, 0.0),
    ("Développeur Python Senior",        "Comptable 5ans",         "it",         "finance",    0.129, 0.0),
    ("Comptable Senior",                 "Contrôleur GS 3ans",     "finance",    "finance",    0.298, 0.5),
    ("Data Scientist ML",                "Comptable 5ans",         "it",         "finance",    0.164, 0.0),
]

ts = datetime.now().strftime("%Y-%m-%d %H:%M")
exists = OUT.exists()
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for (ot, cn, od, cd, ms, hl) in PAIRS:
        w.writerow({"offre_titre": ot, "candidat_nom": cn,
                    "offer_dom": od, "cand_dom": cd,
                    "model_score": ms, "human_label": hl,
                    "timestamp": ts})

print(f"40 labels écrits dans {OUT}")

# Stats
labels = [p[5] for p in PAIRS]
n0   = labels.count(0.0)
n05  = labels.count(0.5)
n1   = labels.count(1.0)
agree = sum(1 for ms, hl in [(p[4], p[5]) for p in PAIRS] if abs(ms - hl) < 0.3)
print(f"  0 (mauvais) : {n0}  |  0.5 (moyen) : {n05}  |  1 (bon) : {n1}")
print(f"  Accord modèle/humain (Δ<0.3) : {agree}/40")
