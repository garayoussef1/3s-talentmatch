# Matching - Resume de la partie IA

## 1) Objectif defini
Construire ton propre modele IA de matching, de facon solide et progressive, sans casser le moteur existant.

Principes retenus:
- Travailler en sandbox isolee.
- Garder le moteur officiel intact tant que la version IA n'est pas validee.
- Comparer heuristique vs IA avec des metriques de ranking.

## 2) Ce qui a ete propose
Approche en etapes:
1. Creer un espace sandbox separe.
2. Construire un dataset d'entrainement depuis la base.
3. Entrainer un modele local baseline (Logistic Regression).
4. Ajouter un endpoint de comparaison non destructif.
5. Evaluer et calibrer avant toute integration officielle.

## 3) Ce qui a ete implemente jusqu'a maintenant
### 3.1 Structure sandbox creee
- app/services/matching_sandbox/
- app/services/matching_sandbox/datasets/
- app/services/matching_sandbox/models/
- app/services/matching_sandbox/reports/

Fichiers ajoutes:
- app/services/matching_sandbox/__init__.py
- app/services/matching_sandbox/README.md
- app/services/matching_sandbox/ml_scorer.py

### 3.2 Scripts sandbox ajoutes
- scripts/sandbox_build_dataset.py
  - Extrait les exemples labels depuis Match.
  - Labels utilises:
    - accepted = 1
    - rejected = 0
    - pending/reviewed exclus du train.
  - Ajout d'un mode bootstrap pour creer des negatifs synthetiques si la base manque de rejected (utile pour demo/PoC).

- scripts/sandbox_train_model.py
  - Entraine un Logistic Regression local.
  - Sauvegarde le modele dans matching_sandbox/models/logreg_v1.joblib.
  - Ecrit un fichier de metriques .metrics.json.
  - Gere le cas petit dataset avec fallback de split.

- scripts/sandbox_eval_model.py
  - Charge le modele et evalue sur dataset CSV.
  - Calcule Precision@5 et NDCG@10.

### 3.3 Endpoint de comparaison ajoute (non destructif)
Dans app/routes/matching.py:
- Nouveau endpoint: POST /api/match-sandbox/{job_offer_id}
- Parametre: alpha (par defaut 0.6)
- Retourne:
  - heuristic_score
  - ml_score
  - hybrid_score = alpha * ml + (1-alpha) * heuristique
- Important: aucune persistance en base (persisted = false).

## 4) Execution et resultats observes
### 4.1 Dataset genere
Fichier:
- app/services/matching_sandbox/datasets/matching_dataset_v1.csv

Etat observe pendant les tests:
- 1 label reel accepted
- 0 label reel rejected
- 5 rejected synthetiques ajoutes (bootstrap)
- total 6 lignes

### 4.2 Entrainement et evaluation
Artefacts generes:
- app/services/matching_sandbox/models/logreg_v1.joblib
- app/services/matching_sandbox/models/logreg_v1.metrics.json
- app/services/matching_sandbox/models/logreg_v1.eval.json

Metriques obtenues (etat actuel demo):
- AUC: 1.0
- AP: 1.0
- Precision@5: 0.2
- NDCG@10: 1.0

Interpretation correcte:
- Ces metriques ne representent pas encore une performance "reelle production".
- Le dataset est trop petit et contient des negatifs synthetiques.
- Le resultat valide surtout le pipeline technique de bout en bout.

## 5) Ce qui reste a faire (priorites)
1. Collecter de vrais labels rejected (decisions recruteur) pour remplacer les synthetiques.
2. Rebuilder le dataset avec plus de donnees reelles.
3. Re-entrainer et re-evaluer avec split plus robuste.
4. Calibrer alpha sur cas reels offre-candidats.
5. Enrichir l'explicabilite (importance features, raison du score).

## 6) Conclusion
Le socle de ton propre modele IA de matching est en place:
- environnement sandbox isole,
- dataset builder,
- training/eval scripts,
- endpoint de comparaison sans risque.

La prochaine valeur metier majeure est d'augmenter la quantite de labels reels pour passer d'un PoC technique a un modele solide et defensable en PFE.
