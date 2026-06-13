"""
compare_ranking_before_after.py
================================
Compare le classement du modèle avant et après réentraînement
sur les labels humains. Utilise les 3 scénarios de test_ranking.py.

Usage :
  python scripts/compare_ranking_before_after.py

Le script charge successivement :
  1. MLP v3b1 (avant — labels formule)
  2. MLP human (après — labels mixtes humains)
Et compare le Spearman rho + inversions critiques sur chaque scénario.
"""
from __future__ import annotations
import sys, os, warnings
warnings.filterwarnings("ignore")

REPO    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from pathlib import Path
from app.services.matching_sandbox.bert_scorer import BERTMatchingScorer
from test_ranking import SCENARIOS, spearman_rho, rank_order   # réutilise les scénarios

MODEL_DIR  = Path(REPO) / "data" / "models" / "fusion_mlp"
V3B1_PATH  = MODEL_DIR / "fusion_mlp_v3b1.pt"
HUMAN_PATH = MODEL_DIR / "fusion_mlp_human.pt"


def run_scenarios(scorer, label=""):
    results = {}
    for titre, offer, cands, expected_order, critical_pairs in SCENARIOS:
        scores = []
        for c in cands:
            s, _ = scorer.score(offer, c)
            scores.append(s)
        model_order = [cands[i].nom for i in sorted(range(len(cands)), key=lambda x: -scores[x])]
        name_to_exp = {n: i for i, n in enumerate(expected_order)}
        name_to_mdl = {n: i for i, n in enumerate(model_order)}
        exp_ranks   = [name_to_exp[c.nom] for c in cands]
        mdl_ranks   = [name_to_mdl[c.nom] for c in cands]
        rho         = spearman_rho(exp_ranks, mdl_ranks)
        inversions  = sum(1 for (b, w) in critical_pairs
                          if scores[next(i for i,c in enumerate(cands) if c.nom==b)] <=
                             scores[next(i for i,c in enumerate(cands) if c.nom==w)])
        results[titre] = {"rho": rho, "inversions": inversions,
                          "order": model_order, "scores": scores}
    return results


def load_scorer_with_mlp(mlp_path: Path | None) -> BERTMatchingScorer:
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    if mlp_path and mlp_path.exists():
        scorer._load_mlp(str(mlp_path).replace(mlp_path.name, "fusion_mlp.pt"))
        # Charger directement le fichier voulu
        try:
            import torch, torch.nn as nn
            class _MLP(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.net = nn.Sequential(
                        nn.Linear(10, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.20),
                        nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.10),
                        nn.Linear(32, 1),  nn.Sigmoid(),
                    )
                    self.n_features = 10
                def forward(self, x):
                    return self.net(x).squeeze(-1)
            mlp = _MLP()
            mlp.load_state_dict(torch.load(mlp_path, map_location="cpu", weights_only=True))
            mlp.eval()
            scorer._mlp         = mlp
            scorer._mlp_version = 4
            print(f"  MLP chargé : {mlp_path.name}")
        except Exception as e:
            print(f"  MLP non chargé ({e}) — fallback")
    else:
        scorer._mlp = None
        scorer._mlp_version = 0
        print(f"  Pas de MLP (formule seule)")
    return scorer


def main():
    print("=" * 70)
    print("  Comparaison classement AVANT vs APRÈS labels humains")
    print("=" * 70)

    print("\nChargement du scorer BGE-M3...")
    base_scorer = BERTMatchingScorer()
    base_scorer._ensure_loaded()

    versions = []

    if V3B1_PATH.exists():
        print(f"\n[AVANT] MLP v3b1 (labels formule uniquement)")
        scorer_before = load_scorer_with_mlp(V3B1_PATH)
        before = run_scenarios(scorer_before, "AVANT")
        versions.append(("AVANT  (formule)", before))
    else:
        print(f"[AVANT] fusion_mlp_v3b1.pt introuvable — test sans MLP avant")
        scorer_none = load_scorer_with_mlp(None)
        before = run_scenarios(scorer_none, "sans MLP")
        versions.append(("AVANT  (sans MLP)", before))

    if HUMAN_PATH.exists():
        print(f"\n[APRÈS] MLP human (labels mixtes formule+humains)")
        scorer_after = load_scorer_with_mlp(HUMAN_PATH)
        after = run_scenarios(scorer_after, "APRÈS")
        versions.append(("APRÈS  (humains)", after))
    else:
        print(f"\n[APRÈS] fusion_mlp_human.pt introuvable.")
        print(f"  → Lancez d'abord :")
        print(f"     python scripts/label_pairs.py")
        print(f"     python backend/scripts/train_mlp_human_labels.py")
        versions.append(("APRÈS  (non dispo)", None))

    # ── Tableau comparatif ────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  Résultats comparatifs")
    print(f"{'='*70}")
    print(f"  {'Scénario':35s} | {'AVANT rho':9s} | {'APRÈS rho':9s} | {'Δrho':6s} | {'Inv. avant':10s} | {'Inv. après'}")
    print(f"  {'-'*35}-+-{'-'*9}-+-{'-'*9}-+-{'-'*6}-+-{'-'*10}-+-{'-'*10}")

    for titre, _, cands, expected_order, critical_pairs in SCENARIOS:
        rho_b = versions[0][1][titre]["rho"] if versions[0][1] else 0.0
        inv_b = versions[0][1][titre]["inversions"] if versions[0][1] else 0

        if len(versions) > 1 and versions[1][1]:
            rho_a = versions[1][1][titre]["rho"]
            inv_a = versions[1][1][titre]["inversions"]
            delta = rho_a - rho_b
            inv_a_str = str(inv_a)
        else:
            rho_a = None
            inv_a = None
            delta = None
            inv_a_str = "N/A"

        rho_a_str = f"{rho_a:.3f}" if rho_a is not None else "N/A"
        delta_str = f"{delta:+.3f}" if delta is not None else "N/A"
        better = "↑ MIEUX" if delta and delta > 0.01 else ("= PAREIL" if delta and abs(delta) <= 0.01 else ("↓ MOINS" if delta else ""))

        print(f"  {titre[:35]:35s} | {rho_b:.3f}     | {rho_a_str:9s} | {delta_str:6s} | {inv_b:<10d} | {inv_a_str:<10s}  {better}")

    # Détail ordres si les deux versions existent
    if len(versions) > 1 and versions[1][1]:
        print(f"\n  Ordres détaillés :")
        for titre, _, cands, expected_order, _ in SCENARIOS:
            ob = versions[0][1][titre]["order"]
            oa = versions[1][1][titre]["order"]
            changed = any(a != b for a, b in zip(ob, oa))
            print(f"\n  {titre}")
            print(f"    Attendu : {expected_order}")
            print(f"    AVANT   : {ob}" + ("  ✓" if ob == expected_order else ""))
            print(f"    APRÈS   : {oa}" + ("  ✓" if oa == expected_order else "") + ("  (changé)" if changed else ""))

    print(f"\n{'='*70}")

    if len(versions) < 2 or not versions[1][1]:
        print("  Annotez des paires et réentraînez pour voir la comparaison :")
        print("    python scripts/label_pairs.py")
        print("    python backend/scripts/train_mlp_human_labels.py")
        print("    python scripts/compare_ranking_before_after.py")


if __name__ == "__main__":
    main()
