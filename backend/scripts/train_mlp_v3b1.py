"""
train_mlp_v3b1.py
=================
Entraine le MLP 10→64→32→1 sur dataset_v3b1.csv.
Architecture B1 : 10 features (titre_skill, crit_ratio, offer_type inclus).

Usage :
  python backend/scripts/train_mlp_v3b1.py

Sortie :
  data/models/fusion_mlp/fusion_mlp_v3b1.pt   (modele)
  data/models/fusion_mlp/fusion_mlp_v3b1_meta.json  (metriques)
"""
from __future__ import annotations
import sys, os, json, csv
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# ─────────────────────────────────────────────────────────────────────────────
DATASET = Path(__file__).resolve().parents[2] / "data" / "mlp_training_fusion" / "dataset_v3b1.csv"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "models" / "fusion_mlp"
OUT_PT  = OUT_DIR / "fusion_mlp_v3b1.pt"
OUT_META = OUT_DIR / "fusion_mlp_v3b1_meta.json"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "sem_sim", "skill_rate_w", "exp_score", "form_score",
    "sem_v2", "edu_dom_compat", "exp_dom_ratio",
    "title_skill_match", "crit_skill_ratio", "offer_type_enc",
]
N_FEATURES = len(FEATURE_COLS)   # 10

# ─────────────────────────────────────────────────────────────────────────────
def load_dataset():
    rows = []
    with open(DATASET, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                feats = [float(row[c]) for c in FEATURE_COLS]
                label = float(row["label"])
                rows.append((feats, label))
            except (KeyError, ValueError):
                continue
    return rows


def split(rows, val_ratio=0.10, test_ratio=0.10, seed=42):
    import random
    random.seed(seed)
    data = rows[:]
    random.shuffle(data)
    n    = len(data)
    n_test = max(1, int(n * test_ratio))
    n_val  = max(1, int(n * val_ratio))
    test  = data[:n_test]
    val   = data[n_test:n_test + n_val]
    train = data[n_test + n_val:]
    return train, val, test


def to_tensors(rows, torch):
    import torch as t
    X = t.tensor([r[0] for r in rows], dtype=t.float32)
    y = t.tensor([r[1] for r in rows], dtype=t.float32)
    return X, y


# ─────────────────────────────────────────────────────────────────────────────
class FusionMLP:
    """MLP 10→64→32→1 avec BatchNorm + Dropout.
    Utilise self.net pour compatibilite avec _ScoringMLPv3b1 dans bert_scorer.py.
    """
    def build(self, torch, nn):
        class _FusionMLP(nn.Module):
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
        return _FusionMLP()


def train():
    try:
        import torch
        import torch.nn as nn
        from torch.optim import Adam
        from torch.optim.lr_scheduler import ReduceLROnPlateau
    except ImportError:
        print("PyTorch requis : pip install torch")
        sys.exit(1)

    # ── Chargement données ───────────────────────────────────────────────────
    print(f"Chargement dataset : {DATASET}")
    rows = load_dataset()
    if len(rows) < 50:
        print(f"ERREUR : dataset trop petit ({len(rows)} lignes). Relancez generate_mlp_dataset_v3b1.py")
        sys.exit(1)

    train_rows, val_rows, test_rows = split(rows)
    print(f"  Train={len(train_rows)} / Val={len(val_rows)} / Test={len(test_rows)}")

    X_train, y_train = to_tensors(train_rows, torch)
    X_val,   y_val   = to_tensors(val_rows,   torch)
    X_test,  y_test  = to_tensors(test_rows,  torch)

    # Distribution labels
    labels = [r[1] for r in rows]
    n_pos  = sum(1 for l in labels if l >= 0.65)
    n_neg  = sum(1 for l in labels if l < 0.35)
    print(f"  Labels : pos={n_pos} ({100*n_pos//len(labels)}%) "
          f"neg={n_neg} ({100*n_neg//len(labels)}%) "
          f"mid={len(labels)-n_pos-n_neg}")

    # ── Modele ───────────────────────────────────────────────────────────────
    model = FusionMLP().build(torch, nn)
    optimizer = Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
    criterion = nn.MSELoss()

    # ── Entrainement ─────────────────────────────────────────────────────────
    MAX_EPOCHS   = 300
    PATIENCE     = 25
    best_val     = float("inf")
    best_state   = None
    no_improve   = 0

    print(f"\nEntrainement MLP {N_FEATURES}→64→32→1 (max {MAX_EPOCHS} epochs)...")
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        optimizer.zero_grad()
        pred = model(X_train).squeeze()
        loss = criterion(pred, y_train)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val).squeeze()
            val_loss = criterion(val_pred, y_val).item()

        scheduler.step(val_loss)

        if val_loss < best_val:
            best_val   = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1

        if epoch % 25 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d} | train={loss.item():.5f} | val={val_loss:.5f} | best={best_val:.5f}")

        if no_improve >= PATIENCE:
            print(f"  Early stopping a l'epoch {epoch} (patience={PATIENCE})")
            break

    # ── Evaluation test ──────────────────────────────────────────────────────
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        test_pred  = model(X_test).squeeze()
        test_loss  = criterion(test_pred, y_test).item()
        test_mae   = (test_pred - y_test).abs().mean().item()
        # Accuracy binaire (seuil 0.5)
        test_acc   = ((test_pred > 0.5) == (y_test > 0.5)).float().mean().item()

    print(f"\n=== Resultats finaux ===")
    print(f"  Val  Loss (MSE) : {best_val:.5f}")
    print(f"  Test Loss (MSE) : {test_loss:.5f}")
    print(f"  Test MAE        : {test_mae:.4f}")
    print(f"  Test Accuracy   : {test_acc*100:.1f}%")

    target_ok = best_val < 0.003
    print(f"  Cible Val<0.003 : {'OK' if target_ok else 'FAIL (continuer entrainement ou plus de data)'}")

    # ── Sauvegarde ───────────────────────────────────────────────────────────
    torch.save(model.state_dict(), OUT_PT)
    meta = {
        "n_features":   N_FEATURES,
        "feature_cols": FEATURE_COLS,
        "architecture": f"{N_FEATURES}->64->32->1",
        "n_train":      len(train_rows),
        "n_val":        len(val_rows),
        "n_test":       len(test_rows),
        "best_val_loss": round(best_val, 6),
        "test_loss":     round(test_loss, 6),
        "test_mae":      round(test_mae, 6),
        "test_accuracy": round(test_acc, 4),
        "dataset":       str(DATASET),
    }
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\nModele sauvegarde : {OUT_PT}")
    print(f"Meta sauvegardees : {OUT_META}")
    return best_val


if __name__ == "__main__":
    train()
