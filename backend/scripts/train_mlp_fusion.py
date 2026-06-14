"""
train_mlp_fusion.py
====================
Entraîne le MLP Fusion v3.0 : combine BGE-M3 (4 dim) + BERT v2 (1 dim) +
2 features discriminantes (skills_raw, edu_gap).

Architecture : 7 -> 64 -> 32 -> 1

Input features :
  [sem_bge, comp_bge, exp_bge, form_bge, sem_v2, skills_raw, edu_gap]

  - sem_bge    : similarité sémantique BGE-M3 (cross-encoder)
  - comp_bge   : score compétences BGE-M3 (avec boost BERT)
  - exp_bge    : score expérience BGE-M3
  - form_bge   : score formation BGE-M3
  - sem_v2     : similarité sémantique BERT v2 fine-tuné
  - skills_raw : ratio brut compétences matchées (sans boost BERT) — discriminant hors-domaine
  - edu_gap    : (req_edu - cand_edu) / 5.0 — positif = sous-qualifié

Output : score final 0.0 -> 1.0

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10/Scripts/python backend/scripts/train_mlp_fusion.py

Sortie : data/models/fusion_mlp/fusion_mlp.pt
         data/models/fusion_mlp/training_report.json
"""
from __future__ import annotations
import sys, csv, json, random
from pathlib import Path
from datetime import datetime

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    print("[ERREUR] PyTorch non installé. Lancez : pip install torch")
    sys.exit(1)

REPO_ROOT   = Path(__file__).resolve().parents[2]
DATASET_CSV = REPO_ROOT / "data" / "mlp_training_fusion" / "dataset_fusion.csv"
OUT_DIR     = REPO_ROOT / "data" / "models" / "fusion_mlp"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MODEL   = OUT_DIR / "fusion_mlp.pt"
OUT_REPORT  = OUT_DIR / "training_report.json"

FEATURES = ["sem_bge", "comp_bge", "exp_bge", "form_bge", "sem_v2", "skills_raw", "edu_gap"]


# ── Architecture MLP ──────────────────────────────────────────────────────────
class FusionMLP(nn.Module):
    """MLP Fusion v3.0 — 7 -> 64 -> 32 -> 1.

    Les 2 nouvelles features (skills_raw, edu_gap) permettent au MLP d'apprendre
    les pénalités hors-domaine et formation sans règles codées en dur.
    """
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(7, 64),  nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
            nn.Linear(32, 1),  nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


# ── Chargement données ────────────────────────────────────────────────────────
def load_dataset(csv_path: Path):
    if not csv_path.exists():
        print(f"[ERREUR] Dataset introuvable : {csv_path}")
        print("Lancez d'abord :")
        print("  .venv-10/Scripts/python backend/scripts/generate_mlp_dataset_fusion.py")
        sys.exit(1)

    X, y = [], []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            X.append([float(row[f]) for f in FEATURES])
            y.append(float(row["label"]))

    combined = list(zip(X, y))
    random.shuffle(combined)
    X, y = zip(*combined)
    return list(X), list(y)


# ── Entraînement ──────────────────────────────────────────────────────────────
def train():
    print("=" * 60)
    print("  Entraînement MLP Fusion v3.0  [7 -> 64 -> 32 -> 1]")
    print("  Features : sem_bge | comp_bge | exp_bge | form_bge | sem_v2 | skills_raw | edu_gap")
    print("=" * 60)

    X, y = load_dataset(DATASET_CSV)
    n    = len(X)
    print(f"[INFO] {n} paires chargées\n")

    # Split 80/20
    split   = int(n * 0.80)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.float32)
    X_val_t   = torch.tensor(X_val,   dtype=torch.float32)
    y_val_t   = torch.tensor(y_val,   dtype=torch.float32)
    X_all_t   = torch.tensor(X,       dtype=torch.float32)

    train_ds = TensorDataset(X_train_t, y_train_t)
    train_dl = DataLoader(train_ds, batch_size=16, shuffle=True)

    model     = FusionMLP()
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=5e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

    EPOCHS         = 200
    PATIENCE       = 40
    best_val_loss  = float("inf")
    best_state     = None
    no_improve     = 0
    history        = []

    print(f"{'Epoch':>6} | {'Train Loss':>10} | {'Val Loss':>10} | {'Val MAE':>8} | {'LR':>10}")
    print("-" * 55)

    for epoch in range(1, EPOCHS + 1):
        # Train
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            optimizer.zero_grad()
            preds      = model(xb)
            loss       = criterion(preds, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(X_train)
        scheduler.step()

        # Val
        model.eval()
        with torch.no_grad():
            val_preds = model(X_val_t)
            val_loss  = criterion(val_preds, y_val_t).item()
            val_mae   = torch.mean(torch.abs(val_preds - y_val_t)).item()

        history.append({"epoch": epoch, "train": train_loss, "val": val_loss, "mae": val_mae})

        # Early stopping
        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            best_state    = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve    = 0
        else:
            no_improve += 1

        if epoch % 20 == 0 or epoch == 1:
            lr_now = optimizer.param_groups[0]["lr"]
            print(f"{epoch:>6} | {train_loss:>10.6f} | {val_loss:>10.6f} | {val_mae:>8.4f} | {lr_now:>10.2e}")

        if no_improve >= PATIENCE:
            print(f"\n[Early stop] Epoch {epoch} — pas d'amélioration depuis {PATIENCE} epochs.")
            break

    # ── Sauvegarder le meilleur état ─────────────────────────────
    model.load_state_dict(best_state)
    torch.save(model.state_dict(), OUT_MODEL)

    # ── Évaluation finale ─────────────────────────────────────────
    model.eval()
    with torch.no_grad():
        all_preds = model(X_all_t).numpy()
        all_true  = torch.tensor(y, dtype=torch.float32).numpy()
        mae_final = float(abs(all_preds - all_true).mean())

        def cat(v):
            if v >= 0.75: return "excellent"
            if v >= 0.55: return "bon"
            if v >= 0.35: return "partiel"
            return "faible"

        correct  = sum(cat(float(p)) == cat(t) for p, t in zip(all_preds, all_true))
        accuracy = correct / len(all_true)

    print("\n" + "=" * 60)
    print(f"  Meilleure val_loss  : {best_val_loss:.6f}")
    print(f"  MAE final (global)  : {mae_final:.4f}  ({mae_final*100:.1f}%)")
    print(f"  Accuracy catégorie  : {accuracy:.1%}  ({correct}/{len(all_true)})")
    print(f"  Modèle sauvegardé   : {OUT_MODEL}")
    print("=" * 60)

    # ── Rapport JSON ───────────────────────────────────────────────
    report = {
        "version":      "TalentMatch-MLP-Fusion v3.0",
        "date":         datetime.now().strftime("%Y-%m-%d %H:%M"),
        "description":  "Fusion intelligente BGE-M3 + BERT v2 + pénalités hors-domaine/formation (apprise par MLP)",
        "architecture": "7 -> 64 -> 32 -> 1  [BatchNorm + Dropout]",
        "features":     FEATURES,
        "dataset": {
            "source":  "Paires synthétiques, scores extraits depuis BGE-M3 + BERT v2",
            "total":   n,
            "train":   len(X_train),
            "val":     len(X_val),
        },
        "hyperparametres": {
            "epochs":       EPOCHS,
            "batch_size":   16,
            "lr":           1e-3,
            "weight_decay": 5e-4,
            "optimizer":    "Adam + CosineAnnealingLR",
            "patience":     PATIENCE,
        },
        "evaluation": {
            "best_val_loss":      round(best_val_loss, 6),
            "mae_final_pct":      round(mae_final * 100, 2),
            "accuracy_categorie": round(accuracy, 4),
        },
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  Rapport             : {OUT_REPORT}")
    print("\nRelancez le backend pour activer automatiquement le MLP Fusion.")


if __name__ == "__main__":
    train()
