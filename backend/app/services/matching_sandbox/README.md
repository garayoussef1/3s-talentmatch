# Matching Sandbox

Ce dossier sert a tester un modele IA de matching sans toucher au moteur principal.

Contenu:
- `datasets/`: exports CSV/JSON utilises pour entrainement.
- `models/`: artefacts modeles entraines localement.
- `reports/`: metriques et comparaisons (heuristique vs IA).

Regle:
- Le pipeline officiel reste dans `app/services/matching/`.
- Toute integration en production passe d'abord par validation metrique.

## Stack ML (depuis 2026-05)

- **Embedder** : `BAAI/bge-m3` (SOTA multilingue, 568M params, 1024-dim, ~1.1 GB fp16).
- **Reranker** : `BAAI/bge-reranker-v2-m3` (cross-encoder, ~1.1 GB fp16).
  Alimente la dimension semantique du MLP avec un score (offre + CV) joint.
- **MLP head** : `data/models/talentmatch-bert-v2.0/scoring_mlp.pt` (5 features -> 0..1).

Les deux modeles sont telecharges au premier demarrage depuis HuggingFace (~2.2 GB total).
Voir `INSTRUCTIONS_UPGRADE_BGE_M3.md` a la racine pour les etapes a executer sur ta machine.
