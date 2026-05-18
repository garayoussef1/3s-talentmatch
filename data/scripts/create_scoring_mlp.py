"""
TalentMatch-BERT v2.0 — Scoring MLP 5 dimensions
Features : sem_sim, skill_rate, exp_score, formation_score, appreciated_rate
Le modele decide le score final — pas une formule manuelle
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
import json
import os
import random

random.seed(42)
torch.manual_seed(42)

MODEL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'models', 'talentmatch-bert-v2.0')
)


# ── Exemples de reference (verite terrain) ─────────────────────────────────
# (sem_sim, skill_rate, exp_score, formation_score, appreciated_rate) -> score
REFERENCE = [
    # Excellent candidat
    (0.85, 1.00, 1.00, 1.00, 1.00, 0.95),
    (0.80, 0.90, 1.00, 1.00, 0.80, 0.92),
    (0.75, 1.00, 0.90, 1.00, 0.60, 0.90),
    (0.70, 0.85, 1.00, 0.90, 1.00, 0.88),
    (0.72, 0.80, 0.85, 1.00, 0.50, 0.85),

    # Bon profil
    (0.65, 0.70, 0.80, 0.80, 0.50, 0.78),
    (0.60, 0.75, 0.70, 1.00, 0.30, 0.75),
    (0.55, 0.80, 0.60, 0.80, 0.60, 0.72),
    (0.60, 0.60, 1.00, 0.70, 0.40, 0.70),
    (0.50, 0.70, 0.80, 0.90, 0.20, 0.68),

    # A evaluer
    (0.45, 0.50, 0.60, 0.60, 0.30, 0.55),
    (0.40, 0.55, 0.50, 0.80, 0.10, 0.52),
    (0.50, 0.40, 0.70, 0.50, 0.50, 0.50),
    (0.35, 0.50, 0.80, 0.70, 0.20, 0.48),
    (0.40, 0.40, 0.40, 1.00, 0.00, 0.45),

    # Profil insuffisant
    (0.30, 0.30, 0.40, 0.50, 0.10, 0.32),
    (0.25, 0.20, 0.30, 0.40, 0.00, 0.28),
    (0.20, 0.30, 0.50, 0.30, 0.00, 0.25),
    (0.15, 0.10, 0.20, 0.20, 0.00, 0.22),

    # Non adapte — domaine completement different
    (0.10, 0.00, 0.30, 0.30, 0.00, 0.20),
    (0.05, 0.00, 0.50, 0.80, 0.00, 0.20),
    (0.08, 0.10, 0.20, 0.50, 0.00, 0.20),

    # Stage / Junior — exp faible acceptable
    (0.60, 0.70, 0.30, 1.00, 0.50, 0.72),
    (0.55, 0.60, 0.20, 0.90, 0.40, 0.68),

    # Senior — exp tres importante
    (0.75, 0.80, 1.00, 1.00, 0.80, 0.92),
    (0.65, 0.70, 0.50, 0.90, 0.60, 0.72),

    # Beaucoup de competences appreciees — bonus
    (0.60, 0.65, 0.70, 0.80, 1.00, 0.82),
    (0.55, 0.60, 0.60, 0.70, 1.00, 0.78),

    # Bonne semantique mais peu de competences
    (0.70, 0.30, 0.60, 0.70, 0.20, 0.52),
    (0.75, 0.20, 0.80, 0.80, 0.00, 0.48),
]


def augment(examples, n=2000):
    """Genere des exemples synthetiques autour des references."""
    result = []
    for (s, sk, ex, fo, ap, label) in examples:
        result.append([s, sk, ex, fo, ap, label])

    for _ in range(n):
        base = random.choice(examples)
        s, sk, ex, fo, ap, label = base
        noise = [random.gauss(0, 0.06) for _ in range(5)]
        s2  = max(0.0, min(1.0, s  + noise[0]))
        sk2 = max(0.0, min(1.0, sk + noise[1]))
        ex2 = max(0.0, min(1.0, ex + noise[2]))
        fo2 = max(0.0, min(1.0, fo + noise[3]))
        ap2 = max(0.0, min(1.0, ap + noise[4]))
        # Recalculer le label selon les perturbations
        delta = (noise[0]*0.25 + noise[1]*0.35 + noise[2]*0.20
                 + noise[3]*0.12 + noise[4]*0.08)
        label2 = max(0.20, min(0.95, label + delta))
        result.append([s2, sk2, ex2, fo2, ap2, label2])

    return result


class ScoringMLP(nn.Module):
    """
    MLP 5 dimensions -> score 0-100%.
    Apprend a combiner : semantique, competences, experience,
    formation, appreciees. Les poids sont appris — pas une formule.
    """
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, 128),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1) * 100


# ── Donnees d'entrainement ─────────────────────────────────────────────────
data = augment(REFERENCE, n=3000)
random.shuffle(data)

tensors = torch.tensor(data, dtype=torch.float32)
X = tensors[:, :5]
y = tensors[:, 5]

split   = int(len(X) * 0.85)
X_train, y_train = X[:split], y[:split]
X_val,   y_val   = X[split:], y[split:]

train_ds = TensorDataset(X_train, y_train)
train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)

# ── Entrainement ───────────────────────────────────────────────────────────
mlp       = ScoringMLP()
optimizer = AdamW(mlp.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=150)

print("Entrainement MLP 5 dimensions...")
best_val = float('inf')
best_state = None

for epoch in range(150):
    mlp.train()
    for xb, yb in train_loader:
        optimizer.zero_grad()
        pred = mlp(xb) / 100
        loss = F.mse_loss(pred, yb)
        loss.backward()
        optimizer.step()
    scheduler.step()

    if (epoch + 1) % 30 == 0:
        mlp.eval()
        with torch.no_grad():
            val_pred = mlp(X_val) / 100
            val_loss = F.mse_loss(val_pred, y_val).item()
        print(f"  Epoch {epoch+1}/150 | Val Loss: {val_loss:.5f}")
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in mlp.state_dict().items()}

mlp.load_state_dict(best_state)
mlp.eval()

# ── Verification ───────────────────────────────────────────────────────────
print("\nVerification sur cas de reference :")
print("-" * 65)
tests = [
    ([0.80, 1.00, 1.00, 1.00, 1.00], "Excellent (sem=0.80, sk=100%, exp=100%, fo=100%)"),
    ([0.65, 0.70, 0.80, 0.80, 0.50], "Bon profil (sem=0.65, sk=70%, exp=80%, fo=80%)"),
    ([0.45, 0.50, 0.60, 0.60, 0.30], "A evaluer  (sem=0.45, sk=50%, exp=60%, fo=60%)"),
    ([0.20, 0.20, 0.30, 0.40, 0.00], "Non adapte (sem=0.20, sk=20%, exp=30%, fo=40%)"),
    ([0.08, 0.00, 0.20, 0.50, 0.00], "Hors domaine (sem=0.08, sk=0%, exp=20%, fo=50%)"),
    ([0.60, 0.70, 0.20, 1.00, 0.40], "Stage/Junior  (sem=0.60, sk=70%, exp=20%, fo=100%)"),
    ([0.55, 0.60, 0.60, 0.70, 1.00], "Bon + appreciees (sem=0.55, ap=100%)"),
]

with torch.no_grad():
    for features, label in tests:
        x   = torch.tensor([features], dtype=torch.float32)
        score = float(mlp(x))
        decision = (
            "Excellent"    if score >= 80 else
            "Bon profil"   if score >= 65 else
            "A evaluer"    if score >= 50 else
            "Non adapte"
        )
        print(f"  {label}")
        print(f"    -> {score:.1f}%  [{decision}]")

# ── Sauvegarde ─────────────────────────────────────────────────────────────
os.makedirs(MODEL_DIR, exist_ok=True)
torch.save(mlp.state_dict(), os.path.join(MODEL_DIR, 'scoring_mlp.pt'))

config = {
    'version':    'TalentMatch-BERT v2.0',
    'mlp_input':  ['sem_sim', 'skill_rate', 'exp_score', 'formation_score', 'appreciated_rate'],
    'mlp_dims':   [5, 128, 64, 32, 1],
    'thresholds': {'excellent': 80, 'bon_profil': 65, 'a_evaluer': 50, 'non_adapte': 0},
    'decisions': {
        'excellent':  'Excellent candidat',
        'bon_profil': 'Bon profil - Entretien recommande',
        'a_evaluer':  'Profil partiel - A evaluer',
        'non_adapte': 'Profil non adapte'
    }
}
with open(os.path.join(MODEL_DIR, 'scoring_config.json'), 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print(f"\nscoring_mlp.pt sauvegarde dans {MODEL_DIR}")
print("scoring_config.json sauvegarde")
print(f"Val Loss finale : {best_val:.5f}")
