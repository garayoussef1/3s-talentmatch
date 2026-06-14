"""
train_mlp_universal.py
======================
Entraîne le FusionMLP v4.0 sur le dataset universel 50 domaines.

Features (7) : sem_bge, comp_bge, exp_bge, form_bge,
               skills_raw, edu_gap_norm, domain_compat_score

Architecture : 7 → 64 → 32 → 1  (identique à _ScoringMLP dans bert_scorer.py)

Output : data/models/fusion_mlp/fusion_mlp.pt  (lu directement par bert_scorer.py)

Usage :
  cd c:/Users/youssef/Desktop/3s-talentmatch
  .venv-10/Scripts/python backend/scripts/train_mlp_universal.py
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

DATASET_CSV = Path(__file__).resolve().parents[2] / "data" / "mlp_training_universal" / "dataset.csv"

# Chemin cible = celui lu par bert_scorer.py (_MLP_WEIGHTS_PATH)
OUT_MODEL   = (
    Path(__file__).resolve().parents[1]
    / "app" / "services" / "matching_sandbox"
    / ".." / ".." / ".." / ".."
    / "data" / "models" / "fusion_mlp" / "fusion_mlp.pt"
).resolve()

OUT_REPORT  = Path(__file__).resolve().parents[2] / "data" / "mlp_training_universal" / "training_report.json"

FEATURES = [
    "sem_bge", "comp_bge", "exp_bge", "form_bge",
    "skills_raw", "edu_gap_norm", "domain_compat_score",
]
N_FEATURES = len(FEATURES)   # 7


class ScoringMLP(nn.Module):
    """Architecture identique à _ScoringMLP dans bert_scorer.py."""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(N_FEATURES, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
            nn.Linear(32, 1),  nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def load_dataset(csv_path: Path):
    if not csv_path.exists():
        print(f"[ERREUR] Dataset introuvable : {csv_path}")
        print("Lancez d'abord : python -m scripts.generate_mlp_dataset_universal")
        sys.exit(1)

    X, y, meta = [], [], []
    missing_domain_compat = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                features = [float(row[f]) for f in FEATURES]
            except KeyError:
                # Ancien dataset sans domain_compat_score — on infère depuis domain_match
                dm = row.get("domain_match", "same")
                dc = {"same": 1.0, "adjacent": 0.65, "different": 0.0}.get(dm, 0.5)
                features = [
                    float(row["sem_bge"]), float(row["comp_bge"]),
                    float(row["exp_bge"]), float(row["form_bge"]),
                    float(row.get("skills_raw", 0.5)),
                    float(row.get("edu_gap_norm", 0.0)),
                    dc,
                ]
                missing_domain_compat += 1
            X.append(features)
            y.append(float(row["label"]))
            meta.append(row.get("domain_match", "unknown"))

    if missing_domain_compat:
        print(f"  WARN: {missing_domain_compat} lignes sans domain_compat_score — inféré depuis domain_match")

    combined = list(zip(X, y, meta))
    random.shuffle(combined)
    X, y, meta = zip(*combined)
    return list(X), list(y), list(meta)


def train():
    print("=" * 60)
    print(f"  FusionMLP v4.0 — {N_FEATURES} features — Dataset universel")
    print("=" * 60)

    X, y, meta = load_dataset(DATASET_CSV)
    n_total = len(X)

    same_n = sum(1 for m in meta if m == "same")
    adj_n  = sum(1 for m in meta if m == "adjacent")
    diff_n = sum(1 for m in meta if m == "different")
    print(f"\n[INFO] {n_total} paires chargées")
    print(f"  same={same_n}  adjacent={adj_n}  different={diff_n}")
    print(f"  Features : {FEATURES}\n")

    split = int(n_total * 0.80)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.float32)
    X_val_t   = torch.tensor(X_val,   dtype=torch.float32)
    y_val_t   = torch.tensor(y_val,   dtype=torch.float32)

    # Poids par sample : on sur-pondère les paires adjacentes et différentes
    # pour que le modèle apprenne les frontières de domaine plus finement.
    _WEIGHTS = {"same": 1.0, "adjacent": 2.5, "different": 2.0}
    sample_weights = torch.tensor(
        [_WEIGHTS.get(m, 1.0) for m in meta[:split]], dtype=torch.float32
    )
    from torch.utils.data import WeightedRandomSampler
    sampler = WeightedRandomSampler(sample_weights, num_samples=len(sample_weights), replacement=True)

    train_ds = TensorDataset(X_train_t, y_train_t)
    train_dl = DataLoader(train_ds, batch_size=32, sampler=sampler)

    model     = ScoringMLP()
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=300, eta_min=1e-5)

    EPOCHS        = 300
    best_val_loss = float("inf")
    best_state    = None
    history       = []

    print(f"{'Epoch':>6} | {'Train Loss':>10} | {'Val Loss':>10} | {'Val MAE':>8}")
    print("-" * 48)

    for epoch in range(1, EPOCHS + 1):
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

        if epoch % 50 == 0 or epoch == 1:
            print(f"{epoch:>6} | {train_loss:>10.6f} | {val_loss:>10.6f} | {val_mae:>8.4f}")

    model.load_state_dict(best_state)
    OUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), OUT_MODEL)

    # Évaluation finale par catégorie
    model.eval()
    with torch.no_grad():
        all_X     = torch.tensor(X, dtype=torch.float32)
        all_preds = model(all_X).numpy()
        all_true  = torch.tensor(y, dtype=torch.float32).numpy()
        mae_final = float(abs(all_preds - all_true).mean())

        def cat(v):
            if v >= 0.75: return "excellent"
            if v >= 0.55: return "bon"
            if v >= 0.35: return "partiel"
            return "faible"

        correct  = sum(cat(float(p)) == cat(t) for p, t in zip(all_preds, all_true))
        accuracy = correct / len(all_true)

        mae_by_type = {}
        for dm in ("same", "adjacent", "different"):
            idxs = [i for i, m in enumerate(meta) if m == dm]
            if idxs:
                pd = all_preds[idxs]
                td = all_true[idxs]
                mae_by_type[dm] = round(float(abs(pd - td).mean()), 4)

        # Vérification spécifique : adjacent + grand écart formation
        adj_high_gap = [
            i for i, m in enumerate(meta)
            if m == "adjacent" and X[i][5] >= 0.8   # edu_gap_norm >= 0.8
        ]
        if adj_high_gap:
            scores_problem = [float(all_preds[i]) for i in adj_high_gap]
            mean_problem   = sum(scores_problem) / len(scores_problem)
            print(f"\n  [CHECK] Adjacent + edu_gap>=0.8 : {len(adj_high_gap)} paires")
            print(f"          Score moyen prédit : {mean_problem:.3f} (attendu < 0.20)")

    print("\n" + "=" * 60)
    print(f"  Meilleure val_loss   : {best_val_loss:.6f}")
    print(f"  MAE final (global)   : {mae_final:.4f}  ({mae_final*100:.1f}%)")
    print(f"  Accuracy catégorie   : {accuracy:.1%}  ({correct}/{len(all_true)})")
    print(f"  MAE par type         : {mae_by_type}")
    print(f"  Modèle sauvegardé    : {OUT_MODEL}")
    print("=" * 60)

    report = {
        "version":    "TalentMatch-MLP v4.0 — Universal 50 domaines — 7 features",
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "base_model": "BAAI/bge-m3 + BAAI/bge-reranker-v2-m3",
        "architecture": f"{N_FEATURES} → 64 → 32 → 1",
        "features": FEATURES,
        "dataset": {
            "source":    "Dataset universel synthétique 50 domaines professionnels",
            "csv":       str(DATASET_CSV),
            "total":     n_total,
            "train":     len(X_train),
            "val":       len(X_val),
            "same":      same_n,
            "adjacent":  adj_n,
            "different": diff_n,
        },
        "hyperparametres": {
            "epochs":     EPOCHS,
            "batch_size": 32,
            "lr":         1e-3,
            "optimizer":  "Adam + CosineAnnealingLR",
            "sampling":   "WeightedRandomSampler (adjacent×2.5, different×2.0)",
        },
        "evaluation": {
            "best_val_loss":      round(best_val_loss, 6),
            "mae_final_pct":      round(mae_final * 100, 2),
            "accuracy_categorie": round(accuracy, 4),
            "mae_by_domain_type": mae_by_type,
        },
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Rapport : {OUT_REPORT}")
    print("  Relancez le backend pour charger le nouveau MLP.\n")


if __name__ == "__main__":
    train()
