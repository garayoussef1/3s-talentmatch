# Matching Sandbox

Ce dossier sert a tester un modele IA de matching sans toucher au moteur principal.

Contenu:
- `datasets/`: exports CSV/JSON utilises pour entrainement.
- `models/`: artefacts modeles entraines localement.
- `reports/`: metriques et comparaisons (heuristique vs IA).

Regle:
- Le pipeline officiel reste dans `app/services/matching/`.
- Toute integration en production passe d'abord par validation metrique.
