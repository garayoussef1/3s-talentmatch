"""
train_mlp_v3.py
================
Entraîne le MLP Fusion v3 : 9 features → score [0,1].

Nouvelles features vs v2 :
  edu_domain_compat : compatibilité domaine formation candidat / offre (0.45–1.00)
  exp_domain_ratio  : ratio années expérience pertinentes / années totales (0.0–1.0)

Architecture : 9 -> 64 -> 32 -> 1

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10\\Scripts\\python backend/scripts/train_mlp_v3.py

Sortie : data/models/fusion_mlp/fusion_mlp_v3.pt
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
    print("[ERREUR] PyTorch non installe. Lancez : pip install torch")
    sys.exit(1)

REPO_ROOT   = Path(__file__).resolve().parents[2]
# Priorité dataset réel > dataset synthétique
_REAL = REPO_ROOT / "data" / "mlp_training_fusion" / "dataset_fusion_real.csv"
_SYN  = REPO_ROOT / "data" / "mlp_training_fusion" / "dataset_fusion_v3.csv"
DATASET_CSV = _REAL if _REAL.exists() else _SYN
OUT_DIR     = REPO_ROOT / "data" / "models" / "fusion_mlp"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MODEL   = OUT_DIR / "fusion_mlp_v3.pt"
OUT_REPORT  = OUT_DIR / "training_report_v3.json"

FEATURES = [
    "sem_bge", "comp_bge", "exp_bge", "form_bge",  # BGE-M3
    "sem_v2",                                        # Cross-encoder
    "skills_raw",                                    # Overlap brut compétences
    "edu_gap",                                       # Ecart niveau formation
    "edu_domain_compat",                             # NEW: compatibilité domaine formation
    "exp_domain_ratio",                              # NEW: ratio années exp pertinentes
]


class FusionMLPv3(nn.Module):
    """MLP Fusion v3 — 9 features → score [0,1]."""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(9, 64),  nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
            nn.Linear(32, 1),  nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def load_dataset(csv_path: Path):
    if not csv_path.exists():
        print(f"[ERREUR] Dataset introuvable : {csv_path}")
        print("Lancez d'abord : python backend/scripts/generate_mlp_dataset_v3.py")
        sys.exit(1)
    X, y = [], []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                feats = [float(row[f]) for f in FEATURES]
                label = float(row["label"])
                X.append(feats)
                y.append(label)
            except (KeyError, ValueError) as e:
                print(f"  [WARN] Ligne ignoree : {e}")
    print(f"[OK] {len(X)} paires chargees")
    return X, y


def main():
    print("=" * 60)
    print("  Entrainement MLP Fusion v3  [9 features -> 64 -> 32 -> 1]")
    print("=" * 60)

    X_all, y_all = load_dataset(DATASET_CSV)
    N = len(X_all)

    # Shuffle + split 80/20
    indices = list(range(N))
    random.seed(42)
    random.shuffle(indices)
    split = int(0.80 * N)
    train_idx = indices[:split]
    val_idx   = indices[split:]

    X_tr = torch.tensor([X_all[i] for i in train_idx], dtype=torch.float32)
    y_tr = torch.tensor([y_all[i] for i in train_idx], dtype=torch.float32)
    X_va = torch.tensor([X_all[i] for i in val_idx],   dtype=torch.float32)
    y_va = torch.tensor([y_all[i] for i in val_idx],   dtype=torch.float32)

    print(f"\n  Train : {len(train_idx)} paires  |  Val : {len(val_idx)} paires")

    train_loader = DataLoader(TensorDataset(X_tr, y_tr), batch_size=32, shuffle=True)

    model     = FusionMLPv3()
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_state    = None
    history       = []

    EPOCHS = 160
    print(f"\n  Epochs : {EPOCHS}  |  LR : 1e-3  |  Batch : 32\n")

    for epoch in range(1, EPOCHS + 1):
        # Train
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(train_idx)
        scheduler.step()

        # Val
        model.eval()
        with torch.no_grad():
            val_pred = model(X_va)
            val_loss = criterion(val_pred, y_va).item()
            val_mae  = (val_pred - y_va).abs().mean().item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state    = {k: v.clone() for k, v in model.state_dict().items()}

        history.append({
            "epoch": epoch, "train_loss": round(train_loss, 6),
            "val_loss": round(val_loss, 6), "val_mae": round(val_mae, 4),
        })

        if epoch % 20 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{EPOCHS}  "
                  f"train_loss={train_loss:.5f}  val_loss={val_loss:.5f}  val_mae={val_mae:.4f}")

    # Charger le meilleur modèle
    model.load_state_dict(best_state)
    torch.save(best_state, OUT_MODEL)
    print(f"\n[OK] Meilleur modele sauvegarde -> {OUT_MODEL}")
    print(f"     Meilleur val_loss = {best_val_loss:.6f}")

    # Evaluation finale
    model.eval()
    with torch.no_grad():
        pred_all = model(X_va).numpy()
        true_all = y_va.numpy()

    mae = abs(pred_all - true_all).mean()
    rmse = ((pred_all - true_all) ** 2).mean() ** 0.5

    # Quelques exemples
    print("\n--- Exemples predictions ---")
    for i in range(min(8, len(val_idx))):
        print(f"  vrai={true_all[i]:.3f}  predit={pred_all[i]:.3f}  "
              f"err={abs(pred_all[i]-true_all[i]):.3f}")

    print(f"\n  MAE  = {mae:.4f}")
    print(f"  RMSE = {rmse:.4f}")

    # Rapport
    report = {
        "version": "v3",
        "features": FEATURES,
        "n_features": len(FEATURES),
        "architecture": "9 -> 64 -> 32 -> 1",
        "n_train": len(train_idx),
        "n_val":   len(val_idx),
        "best_val_loss": round(best_val_loss, 6),
        "final_mae":  round(float(mae),  4),
        "final_rmse": round(float(rmse), 4),
        "trained_at": datetime.now().isoformat(),
        "history": history[-10:],
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[OK] Rapport -> {OUT_REPORT}")
    print("\n[DONE] MLP v3 entraine avec succes !")


if __name__ == "__main__":
    main()
