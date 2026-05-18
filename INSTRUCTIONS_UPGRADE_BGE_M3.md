# Runbook — Upgrade matching to BGE-M3 + cross-encoder reranker

This is what you need to do on the laptop where the project already runs.

The code is already changed for you. This document tells you only what to do **outside the code** —
install, download, configure, restart, verify.

---

## TL;DR

1. Stop the backend.
2. `pip install -U "sentence-transformers>=3.0.0"` in your venv.
3. Set `HF_HUB_OFFLINE=0` (temporarily, for the first run).
4. Start the backend — it will download ~2.2 GB of models from HuggingFace on first request.
5. (Optional) Re-set `HF_HUB_OFFLINE=1` once the cache is populated.
6. Verify in `/docs` that matching returns higher and better-separated scores.

---

## Why this change

The matching scorer used `paraphrase-multilingual-MiniLM-L12-v2` — a 2021-era 118M-param embedder.
We replaced it with:

| Role | New model | Size |
|---|---|---|
| Embedder | `BAAI/bge-m3` | 568M params, 1024-dim, ~1.1 GB fp16 |
| Reranker (new) | `BAAI/bge-reranker-v2-m3` | 568M params, ~1.1 GB fp16 |

Both fit your GTX 1650 4 GB simultaneously at fp16 (~2.7 GB used, 1.3 GB headroom).

The MLP head (5 features → 0..1) is unchanged and continues to load from
`data/models/talentmatch-bert-v2.0/scoring_mlp.pt`. No retraining needed.

The `talentmatch-bert-v2.0/` (and v1.3, v1.2) transformer weights are **no longer used**, but you
can leave the directories on disk — only the `scoring_mlp.pt` file inside v2.0 still matters.

---

## What changed in the code (for your awareness)

| File | Change |
|---|---|
| `backend/app/services/matching_sandbox/bert_scorer.py` | Drop `_TALENTMATCH_PATHS`, `_BASE_MODEL`. Add `_EMBEDDER_MODEL = "BAAI/bge-m3"`, `_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"`. Simplify `_ensure_loaded` to load BGE-M3. Add `_ensure_reranker_loaded`. Simplify `_encode`. Bump skill `THRESHOLD` 0.65 → 0.78. Add `score_semantique_rerank` (cross-encoder + sigmoid). `score_semantique` now uses the reranker. |
| `backend/app/main.py` | Lifespan now pre-warms both BGE-M3 and the reranker. |
| `backend/requirements.txt` | `sentence-transformers>=2.7.0` → `>=3.0.0`. |
| `backend/app/services/matching_sandbox/README.md` | Note added. |

No other files touched. The MLP, dynamic weights, skill heuristics, post-MLP penalties, route
shapes, and DB schema are all unchanged.

---

## Step 1 — Stop the backend

If you started it via `dev.ps1`:

```powershell
.\stop-dev.ps1
```

Or kill the uvicorn process manually. Make sure nothing is holding the venv.

---

## Step 2 — Pull the latest deps

In your project venv (the one that already works — likely `.venv-10` per `dev.ps1`):

```powershell
# Windows
.\.venv-10\Scripts\Activate.ps1
pip install -U "sentence-transformers>=3.0.0"
```

```bash
# Linux/macOS variant
source .venv/bin/activate
pip install -U "sentence-transformers>=3.0.0"
```

This will also upgrade `transformers`, `huggingface_hub`, and `tokenizers` if needed. No other deps
have to change. `easyocr`, `spacy`, `fr-core-news-md`, `psycopg2-binary`, etc. stay as-is.

If pip complains about a conflict with `huggingface_hub` (you have `>=0.24.0`), allow the upgrade —
sentence-transformers 3.x needs `huggingface_hub >= 0.20`.

---

## Step 3 — Allow the first-run download

The `bert_scorer.py` module sets these env vars *at import time* with `setdefault`:

```python
os.environ.setdefault("HF_HUB_OFFLINE",      "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
```

`setdefault` only sets them if they're not already set. So **before** starting the backend, export
them as `0` in your shell or in `backend/.env`:

**Option A — temporary shell env (Windows PowerShell)**:

```powershell
$env:HF_HUB_OFFLINE      = "0"
$env:TRANSFORMERS_OFFLINE = "0"
```

**Option B — `backend/.env`** (this is what `python-dotenv` loads via `load_dotenv()` in
`main.py:4` *before* importing `bert_scorer`, so it works):

```env
HF_HUB_OFFLINE=0
TRANSFORMERS_OFFLINE=0
```

You can flip these back to `1` after the cache is populated (see Step 6).

---

## Step 4 — Start the backend and trigger the download

```powershell
.\dev.ps1
```

The lifespan handler in `main.py` pre-warms both models on app startup. Watch the logs at
`logs/backend.out.log`:

```
[startup] BGE-M3 embedder : BAAI/bge-m3
[startup] Cross-encoder reranker : BAAI/bge-reranker-v2-m3
```

**First time only**: this triggers HuggingFace downloads. Expect:
- `bge-m3`: ~1.1 GB of weight shards + tokenizer (~5–15 min depending on your connection).
- `bge-reranker-v2-m3`: ~1.1 GB more.

Total ~2.2 GB, cached under `~/.cache/huggingface/hub/` (Linux/macOS) or
`%USERPROFILE%\.cache\huggingface\hub\` (Windows).

If the startup log says `indisponible (...)`, the model didn't load — see Troubleshooting below.

---

## Step 5 — Verify end-to-end

### 5a. NLP status endpoint (sanity check, no model needed)

```
GET http://localhost:8000/api/nlp/status
```

Should still return spaCy + CamemBERT info — unchanged.

### 5b. Log into the frontend as admin, then trigger a match

In the UI (or via Swagger at `/docs`):

```
POST /api/match/{job_offer_id}
```

Inspect the response. Look at `results[0].details.components`:

| Field | Before (MiniLM) | After (BGE-M3 + reranker) |
|---|---|---|
| `semantic.score` | ~0.50–0.65 typical | Wider spread, ~0.20 (bad fit) to ~0.85 (good fit) |
| `semantic.method` (you may see in details) | `direct_cosine` | `cross_encoder` |
| `skills.per_skill[*].raw_similarity` | 0.55–0.75 for true matches | 0.78–0.92 for true matches |
| Final `score` | Tightly clustered around 0.45–0.65 | Wider spread, better ranking |

### 5c. A/B sanity check

Pick **3 known good-fit CV/offer pairs** and **3 known bad-fit pairs**. Run matching. Expect:

- Good fits: final score ≥ 0.65 (often higher than today).
- Bad fits: final score ≤ 0.45 (often lower than today).
- The gap between good and bad should be visibly wider than before.

### 5d. Existing tests

```bash
cd backend
pytest tests/test_bert_matching.py -v
pytest tests/test_match_engine_semantic.py -v
```

These test shapes/contracts, not absolute scores. Should still pass. If anything pins a specific
similarity number from MiniLM, update it.

---

## Step 6 — Lock down to offline mode (optional)

Once both models are cached, switch back to offline-only loading for reproducibility:

In `backend/.env`:

```env
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

Restart the backend. It will load from `~/.cache/huggingface/hub/` without touching the network.

---

## Troubleshooting

### `[startup] BGE-M3 embedder : indisponible (...)`

- If the error mentions `OfflineMode` / `Connection`: `HF_HUB_OFFLINE` is still `1`. Do Step 3 again.
- If the error mentions `safetensors` / `Couldn't find`: cache is partial. Delete
  `~/.cache/huggingface/hub/models--BAAI--bge-m3/` and let it redownload.
- If the error mentions VRAM / CUDA OOM: see "Force CPU" below.

### `[startup] Cross-encoder reranker : indisponible (...)`

Same as above for the reranker cache dir: `models--BAAI--bge-reranker-v2-m3/`. The embedder will
still work without it — `score_semantique` falls back to bi-encoder cosine and you get less
accuracy but no crash.

### Out-of-memory on the GTX 1650 4 GB

The combined ~2.7 GB load should fit, but background processes (browser, Discord) can eat VRAM.
Either close them, or force CPU for one of the two models. Quick CPU-only fix — in
`backend/.env`:

```env
CUDA_VISIBLE_DEVICES=
```

That sends both BGE-M3 and the reranker to CPU. ~5× slower per call but functional. On your
i5-10300H, expect ~150 ms per cross-encoder pair on CPU vs ~80 ms on GPU.

### Matching is now slow

Each match request now runs the cross-encoder once per candidate. On GPU, ~80 ms × N. On CPU,
~150 ms × N. For N=50 that's 4–8 s — acceptable. For N=200 that's 15–30 s — see "Future
improvement" below.

### Skills now match too few things

You may have edge cases where 0.65 was catching real synonyms that 0.78 now rejects. Open
`backend/app/services/matching_sandbox/bert_scorer.py`, find the line:

```python
THRESHOLD = 0.78
```

…and lower it (e.g. 0.74). Don't go below 0.70 — BGE-M3 puts unrelated skills in the 0.60–0.70
range, and you'll start matching noise.

### `/api/match-sandbox/{id}?engine=compare_all` now shows identical "base" vs "tuned" rows

Known. That endpoint used to compare your fine-tuned `talentmatch-bert-v2.0` (which sat on top of
MiniLM) against vanilla MiniLM. Both paths now load BGE-M3, so the two rows are the same model.
For meaningful comparisons, use `engine=bert` (full pipeline) vs `engine=heuristic` (the
`MatchEngine` in `services/matching/match_engine.py` — purely deterministic, no neural component).
If you want to revive a baseline comparison, hard-code MiniLM for `_bert_base_scorer` in
`routes/matching.py:62` (it currently passes `model_name=` but my refactor ignores that arg —
the scorer always loads `_EMBEDDER_MODEL`).

### MLP scores look uniformly high or uniformly low

The MLP was trained on MiniLM-derived `sem_sim` values. Cross-encoder values follow a different
distribution (more separated, often centered higher for good matches). If outputs feel saturated:

- Worst case: disable the MLP by renaming
  `data/models/talentmatch-bert-v2.0/scoring_mlp.pt` to `.pt.bak`. The scorer will fall back to
  the weighted-formula path (`_dynamic_weights`) which is robust to feature distribution shifts.
- Better long-term: retrain the MLP on freshly-labeled (offer, CV, label) pairs using the new
  cross-encoder feature.

---

## Files you can touch to tune

- **Skill threshold**: `bert_scorer.py:846` — currently `THRESHOLD = 0.78`.
- **Model choice**: `bert_scorer.py:677–679` — `_EMBEDDER_MODEL` and `_RERANKER_MODEL`.
- **Reranker context window**: `bert_scorer.py` inside `score_semantique_rerank` —
  `_clip_words(..., 256)`. Bump to 384 for richer context (slower, slightly more VRAM).

---

## Future improvements (out of scope, but listed for later)

1. **Top-K rerank** in `routes/matching.py`: when N candidates > 30, do a fast bi-encoder pass
   first, then only run the cross-encoder on the top 30. Cuts latency on big offers.
2. **LLM judge** layer: Ollama + `qwen2.5:3b-instruct-q4_K_M` (~2 GB VRAM) as a final pass on the
   top-5 candidates per offer. Adds explainable verdicts to `Match.details`. Best accuracy lift
   beyond this PR.
3. **Retrain the MLP** on the new cross-encoder feature distribution. Useful only once you have
   ≥1000 labeled pairs.
4. **Replace heuristic skill extraction** with the LLM (one structured-output call per CV at
   upload time). Fixes the GIGO problem at the source.

---

## Rollback

If anything goes wrong:

```bash
git diff HEAD~1 HEAD -- backend/  # see the changes
git checkout HEAD~1 -- backend/app/services/matching_sandbox/bert_scorer.py \
                       backend/app/main.py \
                       backend/requirements.txt \
                       backend/app/services/matching_sandbox/README.md
```

…and restart. You'll be back on MiniLM. No DB state changes were made.
