"""
TalentMatch — Minage des triplets Kaggle/ESCO pour le MLP
==========================================================
Exploite les 2200 triplets d'entraînement BERT comme source de paires
(offre, CV, score) pour enrichir le dataset MLP.

Stratégie :
  triplet (anchor, positive, negative)
    → (anchor→offre, positive→cv) : target = 0.88  (bon match prouvé)
    → (anchor→offre, negative→cv) : target = 0.20  (mauvais match prouvé)

Ces labels binaires compensent le manque de gradations (couvert par les 216
exemples programmatiques) mais apportent la diversité des 278 métiers ESCO.

Usage (depuis backend/) :
    python ../data/scripts/mine_triplets_mlp.py
"""
from __future__ import annotations

import os, sys, json, random, re
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from app.models.candidate import Candidate
from app.models.job_offer import JobOffer

random.seed(42)
torch.manual_seed(42)

DATA_DIR   = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_DIR  = os.path.join(DATA_DIR, 'models', 'talentmatch-bert-v2.0')
TRIPLETS_PATH = os.path.join(DATA_DIR, 'training', 'triplets_merged.json')

# ─────────────────────────────────────────────────────────────────────────────
# Parsers texte → JobOffer / Candidate
# ─────────────────────────────────────────────────────────────────────────────

def _extract_skills_from_text(text: str, sep: str = ",") -> list[str]:
    """Extrait une liste de skills depuis une chaîne."""
    raw = re.split(r"[,\n]", text)
    skills = []
    for s in raw:
        s = s.strip()
        s = re.sub(r"\(obligatoire\)|\(bonus\)|\(apprécié\)", "", s, flags=re.I).strip()
        if s and 2 < len(s) < 45 and not s.startswith("|"):
            skills.append(s)
    return skills[:10]


def parse_fr_anchor(text: str) -> JobOffer | None:
    """
    Format FR: 'Poste : X | Description | Competences requises : A, B\nC'
    """
    if "Poste :" not in text:
        return None
    parts = [p.strip() for p in text.split("|")]
    titre = parts[0].replace("Poste :", "").strip() if parts else ""
    if not titre or len(titre) > 120:
        return None
    # Skills
    required, appreciated = [], []
    for part in parts:
        key = part.lower()
        if "competences requises" in key or "compétences requises" in key:
            raw = re.split(r"compétences requises\s*:|competences requises\s*:", part, flags=re.I)[-1]
            required = _extract_skills_from_text(raw)
        elif "competences appréciées" in key or "appréciées" in key or "appreciees" in key:
            raw = re.split(r"appréciées\s*:|appreciees\s*:", part, flags=re.I)[-1]
            appreciated = _extract_skills_from_text(raw)
    if not required:
        return None
    return JobOffer(
        titre=titre,
        description=text[:600],
        competences_requises=required,
        competences_appreciees=appreciated,
    )


def parse_en_anchor(text: str) -> JobOffer | None:
    """
    Format EN ESCO: 'Job offer: X. Description. Required skills: A, B, C.'
    """
    if "Job offer:" not in text and "Required skills:" not in text:
        return None
    titre = ""
    if "Job offer:" in text:
        titre = text.split("Job offer:")[1].split(".")[0].strip()
        if len(titre) > 120:
            titre = titre[:80]
    required = []
    if "Required skills:" in text:
        raw = text.split("Required skills:")[-1].split(".")[0]
        required = _extract_skills_from_text(raw)
    if not required or not titre:
        return None
    return JobOffer(
        titre=titre,
        description=text[:500],
        competences_requises=required,
        competences_appreciees=[],
    )


def parse_fr_cv(text: str) -> Candidate | None:
    """
    Format FR Kaggle: 'Profil : Name.pdf | ... | Competences : A, B, C | ...'
    """
    if len(text) < 80:
        return None
    skills = []
    parts = text.split("|")
    for part in parts:
        if re.search(r"competences?\s*:", part, re.I):
            raw = re.split(r"competences?\s*:", part, flags=re.I)[-1]
            skills = _extract_skills_from_text(raw)
            break
    if not skills:
        # Fallback: chercher des mots-clés techniques
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9+#.]{2,20}\b", text[:500])
        skills = list(dict.fromkeys(words))[:8]
    parsed = {
        "competences": skills,
        "formations": [],
        "experiences": [],
        "metadata": {"annees_experience_totales": 2, "niveau_formation_max": 4},
    }
    return Candidate(raw_text=text[:700], parsed_data=parsed)


def parse_en_cv(text: str) -> Candidate | None:
    """
    Format EN ESCO: 'Professional profile: X. Experience with A, B, C.'
    """
    if len(text) < 60:
        return None
    skills = []
    if "Experience with" in text:
        raw = text.split("Experience with")[-1].split(".")[0]
        skills = _extract_skills_from_text(raw)
    parsed = {
        "competences": skills,
        "formations": [],
        "experiences": [],
        "metadata": {"annees_experience_totales": 3, "niveau_formation_max": 4},
    }
    return Candidate(raw_text=text[:600], parsed_data=parsed)


def parse_triplet(triplet: dict) -> list[dict]:
    """
    Convertit un triplet en 2 paires (positive→0.88, negative→0.20).
    Retourne [] si le parsing échoue.
    """
    anchor   = triplet.get("anchor", "")
    positive = triplet.get("positive", "")
    negative = triplet.get("negative", "")

    # Détecter le format
    is_fr = "Poste :" in anchor or triplet.get("lang") == "fr"
    is_en = "Job offer:" in anchor or triplet.get("lang") == "en"

    if is_fr:
        offer     = parse_fr_anchor(anchor)
        pos_cv    = parse_fr_cv(positive)
        neg_cv    = parse_fr_cv(negative)
    elif is_en:
        offer     = parse_en_anchor(anchor)
        pos_cv    = parse_en_cv(positive)
        neg_cv    = parse_en_cv(negative)
    else:
        return []

    if not offer or not pos_cv or not neg_cv:
        return []

    occ = triplet.get("occupation", "unknown")
    return [
        {"offre": offer, "cv": pos_cv, "score": 0.88, "label": f"triplet_pos_{occ[:30]}"},
        {"offre": offer, "cv": neg_cv, "score": 0.20, "label": f"triplet_neg_{occ[:30]}"},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# MLP
# ─────────────────────────────────────────────────────────────────────────────

class ScoringMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, 128), nn.ReLU(), nn.Dropout(0.15),
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.10),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1) * 100


def augment_realistic(examples: list, n: int) -> list:
    result = list(examples)
    for _ in range(n):
        if random.random() < 0.65:
            base = random.choice(examples)
            fs, label = base[:5], base[5]
            noise = [random.gauss(0, 0.04) for _ in range(5)]
            fs2 = [max(0.0, min(1.0, f + no)) for f, no in zip(fs, noise)]
            delta = sum(noise[i] * [0.22, 0.32, 0.20, 0.14, 0.12][i] for i in range(5))
            label2 = max(0.18, min(0.95, label + delta))
        else:
            a, b = random.sample(examples, 2)
            alpha = random.random()
            fs2 = [a[i] * alpha + b[i] * (1 - alpha) for i in range(5)]
            label2 = a[5] * alpha + b[5] * (1 - alpha)
        result.append(fs2 + [label2])
    return result


def extract_features(scorer: BERTMatchingScorer, annotations: list, batch_label: str = "") -> list:
    rows = []
    n = len(annotations)
    for i, ann in enumerate(annotations):
        try:
            _, details = scorer.score(ann["offre"], ann["cv"])
            sem_sim    = details["bert_semantic"]
            skill_rate = details["bert_skills"]
            exp_score  = details["experience"] / 100
            form_score = details["formation"] / 100
            criteres   = details.get("criteres", {}).get("apprecies", [])
            apr_rate   = (sum(1 for c in criteres if c.get("matched")) / len(criteres)
                          if criteres else 0.5)
            rows.append([sem_sim, skill_rate, exp_score, form_score, apr_rate, ann["score"]])
            if (i + 1) % 100 == 0 or i == 0:
                print(f"  {batch_label}[{i+1:4d}/{n}] {ann['label'][:40]:<40} target={ann['score']:.2f}")
        except Exception as e:
            pass  # On saute silencieusement les erreurs de parsing
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Chargement dataset programmatique (generate_mlp_dataset.py)
# ─────────────────────────────────────────────────────────────────────────────

def load_programmatic_features(scorer: BERTMatchingScorer) -> list:
    """Recharge et extrait les features du catalogue programmatique."""
    # Import local pour éviter les imports circulaires
    script_dir = os.path.dirname(__file__)
    sys.path.insert(0, script_dir)
    from generate_mlp_dataset import CATALOG, WRONG_DOMAIN_POOL, build_annotations

    annotations = build_annotations(CATALOG, WRONG_DOMAIN_POOL)
    print(f"  {len(annotations)} exemples programmatiques charges")
    return extract_features(scorer, annotations, batch_label="prog ")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("TalentMatch — Minage triplets Kaggle/ESCO pour MLP")
    print("=" * 70)

    # ── 1. Charger les triplets ──────────────────────────────────────────────
    print(f"\n1) Chargement triplets depuis {TRIPLETS_PATH}...")
    with open(TRIPLETS_PATH, encoding="utf-8") as f:
        all_triplets = json.load(f)
    print(f"   {len(all_triplets)} triplets charges")

    # ── 2. Parser les triplets en paires ────────────────────────────────────
    print("\n2) Parsing des triplets...")
    mined = []
    failed = 0
    for t in all_triplets:
        pairs = parse_triplet(t)
        if pairs:
            mined.extend(pairs)
        else:
            failed += 1

    random.shuffle(mined)
    print(f"   {len(mined)} paires extraites  ({failed} triplets ignorés — texte trop court ou format inconnu)")

    # ── 3. Charger le scorer BERT ────────────────────────────────────────────
    print("\n3) Chargement scorer BERT v2.0...")
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    print(f"   Modele v2.0={scorer._use_v2}")

    # ── 4. Extraire features — dataset programmatique (216 ex.) ─────────────
    print("\n4) Extraction features — dataset programmatique (avec gradations)...")
    prog_rows = load_programmatic_features(scorer)
    print(f"   {len(prog_rows)} exemples extraits avec succes")

    # ── 5. Extraire features — triplets minés ───────────────────────────────
    print(f"\n5) Extraction features — {len(mined)} paires triplets (binaires)...")
    print("   (affichage toutes les 100 paires)")
    triplet_rows = extract_features(scorer, mined, batch_label="mine ")
    print(f"   {len(triplet_rows)} paires extraites avec succes")

    # ── 6. Combiner ─────────────────────────────────────────────────────────
    all_rows = prog_rows + triplet_rows
    print(f"\n6) Dataset combine : {len(prog_rows)} prog + {len(triplet_rows)} triplets = {len(all_rows)} total")

    # ── 7. Augmentation ──────────────────────────────────────────────────────
    # Moins d'augmentation car dataset déjà grand
    n_augment = max(2000, 8000 - len(all_rows))
    augmented = augment_realistic(all_rows, n=n_augment)
    random.shuffle(augmented)
    print(f"7) Augmentation : +{n_augment} → {len(augmented)} exemples total")

    # ── 8. Préparer le dataset ───────────────────────────────────────────────
    print("\n8) Preparation dataset...")
    tensors = torch.tensor(augmented, dtype=torch.float32)
    X, y = tensors[:, :5], tensors[:, 5]
    split = int(len(X) * 0.85)
    loader = DataLoader(TensorDataset(X[:split], y[:split]), batch_size=128, shuffle=True)
    X_val, y_val = X[split:], y[split:]

    # ── 9. Entraînement MLP ──────────────────────────────────────────────────
    print("\n9) Entrainement MLP (300 epochs)...")
    mlp = ScoringMLP()
    optimizer = torch.optim.AdamW(mlp.parameters(), lr=8e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=300)
    best_val, best_state = float("inf"), None

    for epoch in range(300):
        mlp.train()
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = F.mse_loss(mlp(xb) / 100, yb)
            loss.backward()
            optimizer.step()
        scheduler.step()
        if (epoch + 1) % 60 == 0:
            mlp.eval()
            with torch.no_grad():
                val_loss = F.mse_loss(mlp(X_val) / 100, y_val).item()
            print(f"   Epoch {epoch+1:3d}/300 | Val Loss: {val_loss:.5f}")
            if val_loss < best_val:
                best_val = val_loss
                best_state = {k: v.clone() for k, v in mlp.state_dict().items()}

    mlp.load_state_dict(best_state)
    mlp.eval()

    # ── 10. Vérification ─────────────────────────────────────────────────────
    print("\n10) Verification sur cas de reference...")
    print("-" * 65)
    VERIF = [
        ([0.90, 1.00, 1.00, 1.00, 1.00], "Excellent parfait"),
        ([0.72, 1.00, 1.00, 1.00, 0.60], "Excellent (sem=0.72)"),
        ([0.65, 0.80, 0.85, 0.85, 0.50], "Bon profil (sem=0.65, sk=80%)"),
        ([0.55, 0.65, 0.75, 0.75, 0.40], "Bon profil limite (sem=0.55)"),
        ([0.48, 0.55, 0.65, 0.65, 0.30], "A evaluer (sem=0.48, sk=55%)"),
        ([0.38, 0.30, 0.40, 0.40, 0.10], "A evaluer bas (sem=0.38, sk=30%)"),
        ([0.22, 0.08, 0.25, 0.30, 0.00], "Non adapte (sem=0.22, sk=8%)"),
        ([0.08, 0.00, 0.20, 0.20, 0.00], "Hors domaine total"),
        ([0.62, 0.78, 0.15, 1.00, 0.50], "Stage/Junior (exp faible)"),
        ([0.78, 0.85, 1.00, 1.00, 0.80], "Senior confirme"),
    ]
    with torch.no_grad():
        for features, label in VERIF:
            score = float(mlp(torch.tensor([features], dtype=torch.float32)))
            decision = ("Excellent" if score >= 80 else "Bon profil" if score >= 65
                        else "A evaluer" if score >= 50 else "Non adapte")
            print(f"  {label:<40} -> {score:5.1f}%  [{decision}]")

    # ── 11. Sauvegarde ───────────────────────────────────────────────────────
    print("\n11) Sauvegarde...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(mlp.state_dict(), os.path.join(MODEL_DIR, "scoring_mlp.pt"))

    config = {
        "version": "TalentMatch-BERT v2.0 — MLP minage triplets Kaggle/ESCO",
        "mlp_input": ["sem_sim", "skill_rate", "exp_score", "formation_score", "appreciated_rate"],
        "mlp_dims": [5, 128, 64, 32, 1],
        "thresholds": {"excellent": 80, "bon_profil": 65, "a_evaluer": 50, "non_adapte": 0},
        "decisions": {
            "excellent":  "Excellent candidat",
            "bon_profil": "Bon profil - Entretien recommande",
            "a_evaluer":  "Profil partiel - A evaluer",
            "non_adapte": "Profil non adapte",
        },
        "training": {
            "n_programmatic": len(prog_rows),
            "n_triplets_mined": len(triplet_rows),
            "n_triplets_source": len(all_triplets),
            "n_total_real": len(all_rows),
            "n_augmented": len(augmented),
            "val_loss_finale": round(best_val, 6),
        },
    }
    with open(os.path.join(MODEL_DIR, "scoring_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"   scoring_mlp.pt sauvegarde dans {MODEL_DIR}")
    print(f"\n   Recap final :")
    print(f"     Exemples programmatiques  : {len(prog_rows):>5}")
    print(f"     Paires minées (triplets)  : {len(triplet_rows):>5}")
    print(f"     Total réel                : {len(all_rows):>5}")
    print(f"     Après augmentation        : {len(augmented):>5}")
    print(f"     Val Loss finale           : {best_val:.5f}")
    print("\nMinage et calibration termines avec succes!")


if __name__ == "__main__":
    main()
