# -*- coding: utf-8 -*-
"""
train_with_junior_labels.py — B : réentraîne le MLP avec labels humains junior.

1. Régénère les features 10D des cas junior/stage (via scorer, code à jour).
2. Applique les labels humains (logique recruteur) avec poids x2.
3. Combine avec dataset_v3b1.csv (labels formule, poids x1).
4. Réentraîne le MLP 10->64->32->1 (transfer learning depuis v3b1).
5. Sauvegarde fusion_mlp_human.pt.

Usage : python backend/scripts/train_with_junior_labels.py
"""
import sys, os, csv, json, warnings
warnings.filterwarnings("ignore")
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
import torch.nn as nn
from torch.optim import Adam
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer

FEATURE_COLS = ["sem_sim","skill_rate_w","exp_score","form_score","sem_v2",
                "edu_dom_compat","exp_dom_ratio","title_skill_match",
                "crit_skill_ratio","offer_type_enc"]
FORMULA_CSV = os.path.join(REPO, "data", "mlp_training_fusion", "dataset_v3b1.csv")
V3B1_PT     = os.path.join(REPO, "data", "models", "fusion_mlp", "fusion_mlp_v3b1.pt")
OUT_PT      = os.path.join(REPO, "data", "models", "fusion_mlp", "fusion_mlp_human.pt")
HUMAN_CSV   = os.path.join(REPO, "data", "human_labels_junior.csv")

WEIGHT_FORMULA = 1.0
WEIGHT_HUMAN   = 2.0


# ── Cas junior + labels humains (logique recruteur) ──────────────────────────
from gen_junior_cases import CASES as JUNIOR_CASES, Offer, Cand

# Cas d'équilibrage ADJACENTS : compétences faibles mais domaine voisin →
# score MOYEN-BAS (ne pas écraser comme un hors-domaine). Empêche le modèle de
# sur-pénaliser les profils partiels légitimes.
ADJACENT_CASES = [
    (Offer("Chargé RH Recrutement", "Recrutement RH paie GPEC droit travail",
           ["Recrutement","RH","Paie","GPEC","Droit du travail"], exp=2, edu=3, niveau="Junior"),
     Cand("Comptable vers RH (adjacent)", "Comptabilité SAP IFRS audit fiscalité 4 ans Bac+5",
          ["Comptabilité générale","SAP","IFRS","Audit interne"], exp=4, edu=5, spec="Finance")),
    (Offer("Data Scientist ML", "Machine learning Python TensorFlow Pandas Bac+5",
           ["Machine Learning","Python","TensorFlow","scikit-learn","Pandas"], exp=3, edu=5),
     Cand("Dev Fullstack vers Data (adjacent)", "Python React Node PostgreSQL Docker 4 ans Bac+5",
          ["Python","React","Node.js","PostgreSQL","Docker"], exp=4, edu=5, spec="Informatique")),
    (Offer("Contrôleur de Gestion", "Contrôle gestion SAP IFRS reporting Bac+5",
           ["Contrôle de gestion","SAP","IFRS","Reporting financier","Excel"], exp=3, edu=5),
     Cand("RH vers Finance (adjacent)", "RH recrutement paie GPEC droit travail 3 ans Bac+3",
          ["RH","Recrutement","Paie","GPEC","Droit du travail"], exp=3, edu=3, spec="Ressources Humaines")),
]

CASES = list(JUNIOR_CASES) + ADJACENT_CASES

HUMAN_LABELS = {
    # Junior/stage — compétences déterminantes
    "Stagiaire 2/5 (faible)":      0.45,
    "Stagiaire 3/5 (moyen)":       0.70,
    "Stagiaire 4/5 (bon)":         0.85,
    "Stagiaire 5/5 (excellent)":   0.95,
    "Junior React 2/5 (faible)":   0.25,
    "Junior React 3/5 (moyen)":    0.60,
    "Junior React 5/5 (excellent)":0.85,
    # Adjacents — moyen-bas (crédit pour la proximité de domaine)
    "Comptable vers RH (adjacent)":        0.22,
    "Dev Fullstack vers Data (adjacent)":  0.38,
    "RH vers Finance (adjacent)":          0.22,
}


def regenerate_junior_features(scorer):
    """Calcule les features 10D à jour pour chaque cas junior + son label."""
    rows = []
    print("Régénération des features junior (code à jour)...")
    for offer, cand in CASES:
        score, det = scorer.score(offer, cand)
        feats = det.get("mlp_features_10d")
        label = HUMAN_LABELS.get(cand.nom)
        if feats is None or label is None:
            print(f"  SKIP {cand.nom}: features ou label manquant")
            continue
        rows.append({"candidat": cand.nom, "model_score": round(score, 4),
                     "human_label": label,
                     **{c: round(feats[j], 4) for j, c in enumerate(FEATURE_COLS)}})
        print(f"  {cand.nom[:28]:28} score_actuel={score*100:5.1f}% -> label_humain={label}")

    # Sauvegarde traçable
    with open(HUMAN_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["candidat","model_score","human_label"]+FEATURE_COLS)
        w.writeheader(); w.writerows(rows)
    print(f"  Labels junior écrits : {HUMAN_CSV}")
    return rows


def load_formula():
    rows = []
    with open(FORMULA_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                feats = [float(r[c]) for c in FEATURE_COLS]
                rows.append((feats, float(r["label"]), WEIGHT_FORMULA))
            except (KeyError, ValueError):
                continue
    return rows


def build_mlp():
    class _MLP(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(10, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
                nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
                nn.Linear(32, 1),  nn.Sigmoid())
            self.n_features = 10
        def forward(self, x): return self.net(x).squeeze(-1)
    return _MLP()


def main():
    scorer = BERTMatchingScorer(); scorer._ensure_loaded()

    junior_rows = regenerate_junior_features(scorer)
    human = [([float(r[c]) for c in FEATURE_COLS], r["human_label"], WEIGHT_HUMAN)
             for r in junior_rows]
    formula = load_formula()

    all_rows = formula + human
    print(f"\nDataset : {len(formula)} formule (x1) + {len(human)} junior humain (x2) "
          f"= {len(all_rows)} lignes")

    import random; random.seed(42); random.shuffle(all_rows)
    n = len(all_rows); n_val = max(1, int(n*0.1))
    val, train = all_rows[:n_val], all_rows[n_val:]

    X_tr = torch.tensor([r[0] for r in train], dtype=torch.float32)
    y_tr = torch.tensor([r[1] for r in train], dtype=torch.float32)
    w_tr = torch.tensor([r[2] for r in train], dtype=torch.float32)
    X_va = torch.tensor([r[0] for r in val], dtype=torch.float32)
    y_va = torch.tensor([r[1] for r in val], dtype=torch.float32)
    w_va = torch.tensor([r[2] for r in val], dtype=torch.float32)

    model = build_mlp()
    if os.path.exists(V3B1_PT):
        try:
            model.load_state_dict(torch.load(V3B1_PT, map_location="cpu", weights_only=True))
            print("Transfer learning depuis fusion_mlp_v3b1.pt")
        except Exception:
            print("Init aléatoire")

    opt = Adam(model.parameters(), lr=5e-4, weight_decay=1e-4)
    wmse = lambda p, t, w: (w * (p.squeeze() - t) ** 2).mean()

    best, best_state, no_imp = 1e9, None, 0
    for epoch in range(1, 301):
        model.train(); opt.zero_grad()
        loss = wmse(model(X_tr), y_tr, w_tr); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vl = wmse(model(X_va), y_va, w_va).item()
        if vl < best:
            best, best_state, no_imp = vl, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            no_imp += 1
        if epoch % 30 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d} | train={loss.item():.5f} | val={vl:.5f} | best={best:.5f}")
        if no_imp >= 30:
            print(f"  Early stopping epoch {epoch}"); break

    model.load_state_dict(best_state)
    torch.save(model.state_dict(), OUT_PT)
    print(f"\nModèle sauvegardé : {OUT_PT}")

    # Vérifie l'effet sur les cas junior
    print("\n=== Effet sur les cas junior (MLP seul) ===")
    model.eval()
    with torch.no_grad():
        for r in junior_rows:
            x = torch.tensor([[float(r[c]) for c in FEATURE_COLS]], dtype=torch.float32)
            pred = float(model(x))
            print(f"  {r['candidat'][:28]:28} label={r['human_label']:.2f} "
                  f"MLP_pred={pred:.2f}  {'OK' if abs(pred-r['human_label'])<0.2 else 'écart'}")


if __name__ == "__main__":
    main()
