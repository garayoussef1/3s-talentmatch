"""
train_mlp_bge.py
================
Entraîne le MLP de scoring sur les features BGE-M3.

MLP : 5 → 128 → 64 → 32 → 1  (même architecture qu'avant)
Input  : [sem_sim, skill_rate, exp_score, formation_score, apr_rate]
Output : score final 0.0 → 1.0

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10/Scripts/python backend/scripts/train_mlp_bge.py

Sortie : data/models/talentmatch-bert-v2.0/scoring_mlp.pt  (remplace l'ancien)
"""
from __future__ import annotations
import sys, os, csv, json, random
from pathlib import Path
from datetime import datetime

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    print("[ERREUR] PyTorch non installé. Lancez : pip install torch")
    sys.exit(1)

DATASET_CSV = Path(__file__).resolve().parents[2] / "data" / "mlp_training_bge" / "dataset.csv"
OUT_MODEL   = Path(__file__).resolve().parents[2] / "data" / "models" / "talentmatch-bert-v2.0" / "scoring_mlp.pt"
OUT_REPORT  = Path(__file__).resolve().parents[2] / "data" / "mlp_training_bge" / "training_report.json"


# ── Architecture MLP ──────────────────────────────────────────────────────────
class ScoringMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, 128), nn.ReLU(), nn.Dropout(0.15),
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.10),
            nn.Linear(64, 32),  nn.ReLU(),
            nn.Linear(32, 1),   nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


# ── Chargement données ────────────────────────────────────────────────────────
def load_dataset(csv_path: Path):
    if not csv_path.exists():
        print(f"[ERREUR] Dataset introuvable : {csv_path}")
        print("Lancez d'abord : .venv-10/Scripts/python backend/scripts/generate_mlp_dataset_bge.py")
        sys.exit(1)

    X, y = [], []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = [
                float(row["sem_sim"]),
                float(row["skill_rate"]),
                float(row["exp_score"]),
                float(row["formation_score"]),
                float(row["apr_rate"]),
            ]
            label = float(row["label"])
            X.append(features)
            y.append(label)

    # Mélanger
    combined = list(zip(X, y))
    random.shuffle(combined)
    X, y = zip(*combined)

    return list(X), list(y)


# ── Entraînement ──────────────────────────────────────────────────────────────
def train():
    print("=" * 55)
    print("  Entraînement MLP sur features BGE-M3")
    print("=" * 55)

    X, y = load_dataset(DATASET_CSV)
    print(f"[INFO] {len(X)} paires chargées\n")

    # Split train/val (80/20)
    split = int(len(X) * 0.80)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.float32)
    X_val_t   = torch.tensor(X_val,   dtype=torch.float32)
    y_val_t   = torch.tensor(y_val,   dtype=torch.float32)

    train_ds = TensorDataset(X_train_t, y_train_t)
    train_dl = DataLoader(train_ds, batch_size=16, shuffle=True)

    model     = ScoringMLP()
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)

    EPOCHS = 150
    best_val_loss = float("inf")
    best_state    = None
    history       = []

    print(f"{'Epoch':>6} | {'Train Loss':>10} | {'Val Loss':>10} | {'Val MAE':>8}")
    print("-" * 45)

    for epoch in range(1, EPOCHS + 1):
        # ── Train ──────────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            optimizer.zero_grad()
            preds = model(xb)
            loss  = criterion(preds, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(X_train)

        # ── Val ────────────────────────────────────────────────────
        model.eval()
        with torch.no_grad():
            val_preds = model(X_val_t)
            val_loss  = criterion(val_preds, y_val_t).item()
            val_mae   = torch.mean(torch.abs(val_preds - y_val_t)).item()

        scheduler.step()
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, "val_mae": val_mae})

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state    = {k: v.clone() for k, v in model.state_dict().items()}

        if epoch % 25 == 0 or epoch == 1:
            print(f"{epoch:>6} | {train_loss:>10.6f} | {val_loss:>10.6f} | {val_mae:>8.4f}")

    # ── Sauvegarder le meilleur modèle ────────────────────────────
    model.load_state_dict(best_state)
    torch.save(model.state_dict(), OUT_MODEL)

    # ── Évaluation finale ─────────────────────────────────────────
    model.eval()
    with torch.no_grad():
        all_preds = model(torch.tensor(X, dtype=torch.float32)).numpy()
        all_true  = torch.tensor(y, dtype=torch.float32).numpy()
        mae_final = float(abs(all_preds - all_true).mean())

        # Accuracy de classement (correct si dans même catégorie)
        def cat(v):
            if v >= 0.75: return "excellent"
            if v >= 0.55: return "bon"
            if v >= 0.35: return "partiel"
            return "faible"

        correct = sum(cat(p) == cat(t) for p, t in zip(all_preds, all_true))
        accuracy = correct / len(all_true)

    print("\n" + "=" * 55)
    print(f"  Meilleure val_loss  : {best_val_loss:.6f}")
    print(f"  MAE final (global)  : {mae_final:.4f}  ({mae_final*100:.1f}%)")
    print(f"  Accuracy catégorie  : {accuracy:.1%}  ({correct}/{len(all_true)})")
    print(f"  Modèle sauvegardé   : {OUT_MODEL}")
    print("=" * 55)

    # ── Rapport JSON ───────────────────────────────────────────────
    report = {
        "version":    "TalentMatch-MLP v3.0 — BGE-M3",
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "base_model": "BAAI/bge-m3 + BAAI/bge-reranker-v2-m3",
        "architecture": "5 → 128 → 64 → 32 → 1",
        "dataset": {
            "source":    "Paires synthétiques générées avec BGE-M3",
            "total":     len(X),
            "train":     len(X_train),
            "val":       len(X_val),
        },
        "hyperparametres": {
            "epochs":     EPOCHS,
            "batch_size": 16,
            "lr":         1e-3,
            "optimizer":  "Adam",
        },
        "evaluation": {
            "best_val_loss":      round(best_val_loss, 6),
            "mae_final_pct":      round(mae_final * 100, 2),
            "accuracy_categorie": round(accuracy, 4),
        },
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  Rapport             : {OUT_REPORT}\n")
    print("Relancez le backend pour charger le nouveau MLP.")


if __name__ == "__main__":
    train()
