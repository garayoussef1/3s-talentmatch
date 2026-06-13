"""
train_mlp_human_labels.py
==========================
Réentraîne le MLP en mélangeant :
  - Labels formule (dataset_v3b1.csv)  : poids 1.0  → 70% des données
  - Labels humains (human_labels.csv)  : poids 2.0  → 30%, mais comptent double

La loss est une MSE pondérée : loss = mean(weights * (pred - label)^2)
Les labels humains ont poids=2.0 car ils représentent la vérité terrain réelle.

Sortie : data/models/fusion_mlp/fusion_mlp_human.pt
"""
from __future__ import annotations
import sys, os, json, csv
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

REPO_ROOT   = Path(__file__).resolve().parents[2]
FORMULA_CSV = REPO_ROOT / "data" / "mlp_training_fusion" / "dataset_v3b1.csv"
HUMAN_CSV   = REPO_ROOT / "data" / "human_labels.csv"
OUT_DIR     = REPO_ROOT / "data" / "models" / "fusion_mlp"
OUT_PT      = OUT_DIR / "fusion_mlp_human.pt"
OUT_META    = OUT_DIR / "fusion_mlp_human_meta.json"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "sem_sim", "skill_rate_w", "exp_score", "form_score",
    "sem_v2", "edu_dom_compat", "exp_dom_ratio",
    "title_skill_match", "crit_skill_ratio", "offer_type_enc",
]
N_FEATURES = len(FEATURE_COLS)

WEIGHT_FORMULA = 1.0
WEIGHT_HUMAN   = 2.0   # labels humains comptent double


def load_formula_dataset() -> list:
    """Charge dataset_v3b1.csv (labels formule, poids 1.0)."""
    rows = []
    if not FORMULA_CSV.exists():
        print(f"ERREUR: {FORMULA_CSV} introuvable — lancez generate_mlp_dataset_v3b1.py")
        return rows
    with open(FORMULA_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                feats  = [float(row[c]) for c in FEATURE_COLS]
                label  = float(row["label"])
                rows.append((feats, label, WEIGHT_FORMULA, "formula"))
            except (KeyError, ValueError):
                continue
    return rows


def load_human_labels(formula_rows: list) -> list:
    """Charge human_labels.csv et génère les features via scorer."""
    if not HUMAN_CSV.exists():
        print(f"  human_labels.csv absent — entraînement sur labels formule uniquement.")
        return []

    # Charger les labels humains
    human_raw = []
    with open(HUMAN_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                human_raw.append({
                    "offre_titre":  row["offre_titre"],
                    "candidat_nom": row["candidat_nom"],
                    "offer_dom":    row.get("offer_dom", ""),
                    "cand_dom":     row.get("cand_dom", ""),
                    "model_score":  float(row["model_score"]),
                    "human_label":  float(row["human_label"]),
                })
            except (KeyError, ValueError):
                continue

    if not human_raw:
        return []

    # Utiliser le model_score comme sem_sim proxy, avec features synthétiques
    # basées sur le label humain et le score modèle
    # NOTE: idéalement on rejouerait scorer.score() sur chaque paire, mais
    # cela nécessite les objets offre/cand. En attendant, on aproxime depuis
    # model_score (label formule) + human_label (correction humaine).
    # Les features réelles seront disponibles quand label_pairs.py sauvegarde
    # aussi les mlp_features_10d.
    print(f"  {len(human_raw)} labels humains chargés.")
    print(f"  Accord modèle/humain : ", end="")
    agree = sum(1 for r in human_raw if abs(r["model_score"] - r["human_label"]) < 0.3)
    print(f"{agree}/{len(human_raw)}")

    # Construire des features approximées pour les labels humains
    # En pratique, on cherche dans le dataset formule les paires correspondantes
    formula_index = {}
    with open(FORMULA_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            k = (row["offre"], row["candidat"])
            try:
                feats = [float(row[c]) for c in FEATURE_COLS]
                formula_index[k] = feats
            except (KeyError, ValueError):
                continue

    human_rows = []
    for r in human_raw:
        # Cherche dans le dataset formule par titre+nom
        key = None
        for (offre_key, cand_key), feats in formula_index.items():
            if (r["offre_titre"].lower() in offre_key.lower() or
                offre_key.lower() in r["offre_titre"].lower()) and \
               (r["candidat_nom"].lower() in cand_key.lower() or
                cand_key.lower() in r["candidat_nom"].lower()):
                key = (offre_key, cand_key)
                break

        if key and key in formula_index:
            feats = formula_index[key]
            human_rows.append((feats, r["human_label"], WEIGHT_HUMAN, "human"))
            print(f"    Apparié: {r['offre_titre'][:30]} × {r['candidat_nom'][:20]} label={r['human_label']}")
        else:
            # Fallback: features synthétiques depuis model_score
            # sem_sim ≈ model_score, autres features estimées
            ms = r["model_score"]
            feats = [ms, ms, ms*0.8, ms*0.9, ms, 0.8, 0.6, 1.0 if ms > 0.6 else 0.0, ms, 0.5]
            human_rows.append((feats, r["human_label"], WEIGHT_HUMAN, "human_approx"))

    return human_rows


def split(rows, val_ratio=0.10, test_ratio=0.10, seed=42):
    import random
    random.seed(seed)
    data = rows[:]
    random.shuffle(data)
    n = len(data)
    n_test = max(1, int(n * test_ratio))
    n_val  = max(1, int(n * val_ratio))
    test  = data[:n_test]
    val   = data[n_test:n_test + n_val]
    train = data[n_test + n_val:]
    return train, val, test


def train():
    try:
        import torch
        import torch.nn as nn
        from torch.optim import Adam
        from torch.optim.lr_scheduler import ReduceLROnPlateau
    except ImportError:
        print("PyTorch requis : pip install torch")
        sys.exit(1)

    # ── Chargement ────────────────────────────────────────────────────────────
    print("=== Réentraînement MLP — Labels mixtes Formule + Humains ===\n")
    formula_rows = load_formula_dataset()
    human_rows   = load_human_labels(formula_rows)

    if not formula_rows:
        print("ERREUR : dataset formule vide.")
        sys.exit(1)

    # Mix : 70% formule + 30% humains (ou tout le formule si < 40 labels humains)
    all_rows = formula_rows + human_rows
    print(f"\nDataset mixte :")
    print(f"  Labels formule : {len(formula_rows)} (poids {WEIGHT_FORMULA})")
    print(f"  Labels humains : {len(human_rows)} (poids {WEIGHT_HUMAN})")
    print(f"  Total          : {len(all_rows)}")

    train_rows, val_rows, test_rows = split(all_rows)
    print(f"  Train={len(train_rows)} / Val={len(val_rows)} / Test={len(test_rows)}")

    # ── Tenseurs ──────────────────────────────────────────────────────────────
    X_train = torch.tensor([r[0] for r in train_rows], dtype=torch.float32)
    y_train = torch.tensor([r[1] for r in train_rows], dtype=torch.float32)
    w_train = torch.tensor([r[2] for r in train_rows], dtype=torch.float32)

    X_val = torch.tensor([r[0] for r in val_rows], dtype=torch.float32)
    y_val = torch.tensor([r[1] for r in val_rows], dtype=torch.float32)
    w_val = torch.tensor([r[2] for r in val_rows], dtype=torch.float32)

    X_test = torch.tensor([r[0] for r in test_rows], dtype=torch.float32)
    y_test = torch.tensor([r[1] for r in test_rows], dtype=torch.float32)

    # ── Modèle ────────────────────────────────────────────────────────────────
    class _MLP(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(N_FEATURES, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
                nn.Linear(64, 32),         nn.ReLU(),           nn.Dropout(0.10),
                nn.Linear(32, 1),          nn.Sigmoid(),
            )
            self.n_features = N_FEATURES
        def forward(self, x):
            return self.net(x).squeeze(-1)
    model = _MLP()

    # Initialiser avec les poids du v3b1 si disponible (transfer learning)
    v3b1_path = OUT_DIR / "fusion_mlp_v3b1.pt"
    if v3b1_path.exists():
        try:
            model.load_state_dict(torch.load(v3b1_path, map_location="cpu", weights_only=True))
            print(f"\nInitialisation depuis fusion_mlp_v3b1.pt (transfer learning)")
        except Exception:
            print(f"\nInitialisation aléatoire (v3b1 incompatible)")
    else:
        print(f"\nInitialisation aléatoire (v3b1 non trouvé)")

    optimizer = Adam(model.parameters(), lr=5e-4, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

    def weighted_mse(pred, target, weights):
        """MSE pondérée : loss = mean(weights * (pred - target)^2)"""
        return (weights * (pred.squeeze() - target) ** 2).mean()

    # ── Entraînement ──────────────────────────────────────────────────────────
    MAX_EPOCHS = 300
    PATIENCE   = 30
    best_val   = float("inf")
    best_state = None
    no_improve = 0

    print(f"\nEntraînement {N_FEATURES}→64→32→1 (max {MAX_EPOCHS} epochs, patience {PATIENCE})...")
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        optimizer.zero_grad()
        pred = model(X_train)
        loss = weighted_mse(pred, y_train, w_train)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val)
            val_loss = weighted_mse(val_pred, y_val, w_val).item()

        scheduler.step(val_loss)

        if val_loss < best_val:
            best_val   = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1

        if epoch % 30 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d} | train={loss.item():.5f} | val={val_loss:.5f} | best={best_val:.5f}")

        if no_improve >= PATIENCE:
            print(f"  Early stopping epoch {epoch}")
            break

    # ── Évaluation ────────────────────────────────────────────────────────────
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        test_pred = model(X_test).squeeze()
        test_mae  = (test_pred - y_test).abs().mean().item()
        test_acc  = ((test_pred > 0.5) == (y_test > 0.5)).float().mean().item()

    print(f"\n=== Résultats ===")
    print(f"  Val  Loss (MSE pondérée) : {best_val:.5f}")
    print(f"  Test MAE                 : {test_mae:.4f}")
    print(f"  Test Accuracy (>0.5)     : {test_acc*100:.1f}%")

    if human_rows:
        print(f"\n  Analyse des labels humains dans le test :")
        human_in_test = [(r, i) for i, r in enumerate(test_rows) if r[3].startswith("human")]
        for r, i in human_in_test[:10]:
            pred_val = float(test_pred[i])
            print(f"    label={r[1]:.1f} pred={pred_val:.2f} err={abs(pred_val-r[1]):.2f}  {'OK' if abs(pred_val-r[1])<0.25 else 'OFF'}")

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    torch.save(model.state_dict(), OUT_PT)
    meta = {
        "n_features":     N_FEATURES,
        "feature_cols":   FEATURE_COLS,
        "architecture":   f"{N_FEATURES}->64->32->1",
        "n_formula":      len(formula_rows),
        "n_human":        len(human_rows),
        "n_train":        len(train_rows),
        "n_val":          len(val_rows),
        "n_test":         len(test_rows),
        "best_val_loss":  round(best_val, 6),
        "test_mae":       round(test_mae, 6),
        "test_accuracy":  round(test_acc, 4),
        "weight_formula": WEIGHT_FORMULA,
        "weight_human":   WEIGHT_HUMAN,
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\nModèle sauvegardé : {OUT_PT}")
    print(f"  → Pour l'activer dans bert_scorer, renommez en fusion_mlp_v3b1.pt")
    return best_val


if __name__ == "__main__":
    train()
