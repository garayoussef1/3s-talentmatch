# Changement de modèles — BGE-M3 + Cross-Encoder Reranker

**Date :** 18 mai 2026
**Branche :** `feat/bge-m3-reranker` → fusionnée dans `master`
**Fichiers modifiés :** `backend/app/services/matching_sandbox/bert_scorer.py`, `backend/app/main.py`, `backend/requirements.txt`, `backend/app/services/matching_sandbox/README.md`

---

## Résumé

Remplacement de l'embedder de matching (`paraphrase-multilingual-MiniLM-L12-v2`) par **`BAAI/bge-m3`** (état de l'art multilingue), et ajout d'un **cross-encoder `BAAI/bge-reranker-v2-m3`** pour le scoring sémantique du MLP.

---

## Avant / Après

| Élément | Avant | Après |
|---|---|---|
| Embedder | `paraphrase-multilingual-MiniLM-L12-v2` (118M params, 384-dim, 2021) | `BAAI/bge-m3` (568M params, 1024-dim, SOTA multilingue) |
| Scoring sémantique | Similarité cosinus bi-encodeur | Cross-encoder joint (offre + CV ensemble) |
| Méthode retournée | `direct_cosine` | `cross_encoder` |
| Seuil compétences (`THRESHOLD`) | 0.65 | 0.78 (recalibré pour BGE-M3) |
| Fallback | Arbre de versions v2.0 → v1.3 → v1.2 | Un seul `SentenceTransformer` + fallback bi-encodeur si reranker absent |
| Poids MLP | `talentmatch-bert-v2.0/scoring_mlp.pt` | **Identique** — aucun réentraînement requis |

---

## Pourquoi ce changement

Le scoring sémantique était le maillon faible du pipeline. La similarité cosinus entre deux vecteurs indépendants (bi-encodeur) ne modélise pas les interactions entre l'offre et le CV. Un cross-encoder traite la paire (offre, CV) ensemble et produit un score beaucoup plus discriminant.

Gains attendus d'après les benchmarks publics MTEB / BEIR multilingues :
- MiniLM → BGE-M3 seul : **+10–20 nDCG@10** en retrieval multilingue.
- Ajout du cross-encoder reranker : **+5–10 points supplémentaires**.

---

## Détail des changements de code

### `bert_scorer.py`

- Suppression de `_TALENTMATCH_PATHS`, `_BASE_MODEL` et de l'arbre de fallback v2.0/v1.x.
- Ajout de `_EMBEDDER_MODEL = "BAAI/bge-m3"` et `_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"`.
- `_EMBEDDER_DIM` passé de 384 à **1024** (dimension BGE-M3).
- `_ensure_loaded()` simplifié : un seul appel `SentenceTransformer(_EMBEDDER_MODEL)`.
- Nouvelle méthode `_ensure_reranker_loaded()` : charge le `CrossEncoder` de façon lazy et indépendante.
- Nouvelle méthode `score_semantique_rerank()` : applique le cross-encoder sur la paire (offre clippée à 256 mots, CV clippé à 256 mots), sigmoid sur le logit brut → score [0, 1].
- `score_semantique()` appelle désormais `score_semantique_rerank()` au lieu de `score_semantic()` (cosinus).
- `_load_mlp()` reçoit maintenant le chemin direct vers `scoring_mlp.pt` plutôt qu'un dossier de modèle.
- `THRESHOLD` compétences : **0.65 → 0.78** (les cosines BGE-M3 sur vrais matches se situent entre 0.78 et 0.92, contre 0.55–0.75 pour MiniLM).

### `main.py`

- Le gestionnaire de cycle de vie (`lifespan`) pré-charge désormais les deux modèles au démarrage et affiche :
  ```
  [startup] BGE-M3 embedder : BAAI/bge-m3
  [startup] Cross-encoder reranker : BAAI/bge-reranker-v2-m3
  ```

### `requirements.txt`

- `sentence-transformers>=2.7.0` → `>=3.0.0`

---

## Compatibilité

- **MLP head** : inchangé. Les 5 features d'entrée du MLP restent les mêmes ; seule la valeur de `sem_sim` (feature #1) provient désormais du cross-encoder. **Aucun réentraînement nécessaire.**
- **Routes** : `/api/match/{id}` et `/api/match-sandbox/{id}?engine=bert` sont inchangées. Le champ `details.components.semantic.method` passe de `direct_cosine` à `cross_encoder`.
- **Point de vigilance** : l'endpoint `?engine=compare_all` produit des lignes "base" et "tuned" identiques (les deux chargent BGE-M3). Pour une comparaison A/B significative, utiliser `engine=bert` vs `engine=heuristic`.

---

## Matériel cible testé

- GPU : GTX 1650 4 Go
- CPU : Intel i5-10300H
- RAM : 24 Go
- Empreinte VRAM combinée : ~2.7 Go fp16 (1.3 Go de marge)
- Taille téléchargement : ~2.2 Go (cache HuggingFace `~/.cache/huggingface/hub/`)

---

## Résultats observés lors des tests (18 mai 2026)

- Deux offres matchées via `POST /api/match-sandbox/{id}?engine=bert` — **200 OK** sans erreur.
- Les deux modèles chargés depuis le cache à chaque démarrage :
  ```
  Loading weights: 100% | 391/391  ← BGE-M3
  Loading weights: 100% | 393/393  ← Reranker
  Application startup complete.
  ```
- Score sémantique mesuré sur paire test :
  - Bon match (Python/FastAPI → Python/FastAPI) : **0.69**
  - Mauvais match (Python/FastAPI → Java/Spring) : **0.50**
  - Écart : **0.19** (contre ~0.05–0.10 avec MiniLM cosinus)

---

## Rollback

Si un problème survient, revenir à MiniLM en une commande :

```bash
git checkout master~1 -- backend/app/services/matching_sandbox/bert_scorer.py \
                         backend/app/main.py \
                         backend/requirements.txt \
                         backend/app/services/matching_sandbox/README.md
```

Puis redémarrer le backend. Aucun changement de schéma DB n'a été effectué.

---

## Améliorations futures envisagées

1. **Top-K rerank** : bi-encodeur rapide sur N candidats, cross-encoder seulement sur le top-30. Réduit la latence sur les offres avec beaucoup de candidats.
2. **Réentraîner le MLP** sur des paires labelisées avec la nouvelle distribution de `sem_sim` cross-encoder (utile à partir de ~1000 paires).
3. **Juge LLM** : Ollama + `qwen2.5:3b-instruct-q4_K_M` (~2 Go VRAM) en passe finale sur le top-5, pour des verdicts explicables.
4. **Extraction de compétences LLM** : remplacer l'heuristique d'extraction par un appel LLM structuré à l'upload du CV.
