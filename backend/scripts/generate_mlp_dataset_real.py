#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère les 9 features BGE-M3 sur le dataset réel job_resume_fit (2385 paires).
Label = ai_match_score / 100 (score validé par IA sur vraies paires CV/offre).

Sortie : data/mlp_training_fusion/dataset_fusion_real.csv
"""
import sys, os, csv, time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",   "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import pandas as pd
import numpy as np
from app.services.matching_sandbox.bert_scorer import (
    BERTMatchingScorer, _detect_edu_domain, _edu_domain_compatibility,
    _normalize_accents
)

REPO_ROOT = Path(__file__).resolve().parents[2]
IN_CSV    = REPO_ROOT / "data" / "mlp_training_fusion" / "job_resume_fit_raw.csv"
OUT_CSV   = REPO_ROOT / "data" / "mlp_training_fusion" / "dataset_fusion_real.csv"

FEATURES = [
    "sem_bge", "comp_bge", "exp_bge", "form_bge",
    "sem_v2", "skills_raw", "edu_gap",
    "edu_domain_compat", "exp_domain_ratio",
]

def skill_overlap(skills_a_str: str, skills_b_str: str) -> float:
    """Calcule le chevauchement de compétences depuis des strings JSON-like."""
    try:
        import ast
        a = set(s.lower().strip() for s in ast.literal_eval(skills_a_str))
        b = set(s.lower().strip() for s in ast.literal_eval(skills_b_str))
        if not a: return 0.0
        return round(len(a & b) / len(a), 4)
    except Exception:
        return 0.0

def main():
    print("=" * 65)
    print("  Generation features BGE-M3 sur dataset réel (2385 paires)")
    print("=" * 65)

    if not IN_CSV.exists():
        print(f"[ERREUR] Dataset introuvable : {IN_CSV}")
        print("Lancez d'abord : python scripts/download_job_resume_fit.py")
        sys.exit(1)

    df = pd.read_csv(IN_CSV)
    print(f"[OK] {len(df)} paires chargées — colonnes: {list(df.columns)}")

    print("\n[1/2] Chargement BGE-M3...")
    scorer = BERTMatchingScorer()
    scorer._ensure_loaded()
    scorer._ensure_reranker_loaded()
    if not scorer.ready:
        print("[ERREUR] BGE-M3 non disponible.")
        sys.exit(1)
    print("      BGE-M3 OK\n")

    rows = []
    total = len(df)
    t0 = time.time()

    # Encodage en BATCH — beaucoup plus rapide que paire par paire
    print(f"[2/2] Encodage batch BGE-M3 de {total} paires...")
    print("      (sans cross-encoder : trop lent sur CPU — sem_v2 = sem_bge)")

    # Préparer tous les textes tronqués
    CLIP = 512  # tokens max pour BGE-M3 (raisonnable sur CPU)
    offer_texts  = [str(r.get("job_text", "") or "")[:CLIP] for _, r in df.iterrows()]
    resume_texts = [str(r.get("resume_text", "") or "")[:CLIP] for _, r in df.iterrows()]

    print("      Encodage offres...", flush=True)
    embs_offer  = scorer._encode(offer_texts)
    print("      Encodage CVs...", flush=True)
    embs_resume = scorer._encode(resume_texts)
    print("      Calcul similarités...", flush=True)

    from app.services.matching_sandbox.bert_scorer import _cosine

    for i, row in df.iterrows():
        req_skills = str(row.get("job_required_skills", "") or "")
        cv_skills  = str(row.get("resume_skill_list", "")   or "")
        score_raw  = float(row.get("ai_match_score", 50) or 50)
        label      = round(min(1.0, max(0.0, score_raw / 100.0)), 4)

        # Similarité sémantique BGE-M3
        cos = float(_cosine(
            np.asarray(embs_offer[i], dtype=float),
            np.asarray(embs_resume[i], dtype=float),
        ))
        sem_bge = round(max(0.0, min(1.0, (cos + 1.0) / 2.0)), 6)
        sem_v2  = sem_bge  # proxy : cross-encoder trop lent sur CPU

        # Skills features
        skills_raw       = skill_overlap(req_skills, cv_skills)
        comp_bge         = round(skills_raw, 4)
        exp_bge          = 0.5
        form_bge         = 0.5
        edu_gap          = 0.0

        # Domaine
        cand_dom          = _detect_edu_domain(resume_texts[i][:300])
        offer_dom         = _detect_edu_domain(offer_texts[i][:300])
        edu_domain_compat = _edu_domain_compatibility(cand_dom, offer_dom)
        exp_domain_ratio  = round(min(1.0, skills_raw * 1.5), 4)

        rows.append({
            "sem_bge":          sem_bge,
            "comp_bge":         round(comp_bge, 6),
            "exp_bge":          exp_bge,
            "form_bge":         form_bge,
            "sem_v2":           sem_v2,
            "skills_raw":       round(skills_raw, 4),
            "edu_gap":          edu_gap,
            "edu_domain_compat":round(edu_domain_compat, 4),
            "exp_domain_ratio": round(exp_domain_ratio, 4),
            "label":            label,
        })

        if (i + 1) % 200 == 0 or i == 0:
            elapsed = time.time() - t0
            print(f"  [{i+1:4d}/{total}] sem={sem_bge:.2f} sk={skills_raw:.2f} lbl={label:.2f}  ({elapsed:.0f}s)", flush=True)

    fieldnames = FEATURES + ["label"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[OK] {len(rows)} paires -> {OUT_CSV}")
    print("Lancez maintenant : python backend/scripts/train_mlp_v3.py --dataset real")

if __name__ == "__main__":
    main()
