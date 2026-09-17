<div align="center">

# MOVICO

**A hybrid film recommender that explains its own picks.**

Implicit-ALS collaborative filtering + a shrunk item-item neighbourhood + weighted
multi-channel content similarity, fused and diversity re-ranked, over 33.1M
MovieLens ratings and a 95k-title catalogue enriched from TMDB.

FastAPI · SQLite · NumPy/SciPy · React · Vite · Tailwind

</div>

---

## Why this exists

Most portfolio recommenders stop at "I trained an SVD and printed the top 10". The
interesting problems start after that:

- A latent factor model can't rank a film released last week — it has no
  interactions. A content model can, but only badly.
- Ranking purely by predicted relevance returns ten near-identical films. Correct,
  and useless.
- A new user has no embedding at all, and retraining per signup is not an option.
- "90% accuracy" is not a meaningful claim about a top-N recommender, and the
  metrics that *are* meaningful need a stated evaluation protocol to mean anything.

MOVICO is built around those four problems.

---

## Results

Measured under a **strong-generalisation** protocol (definition below), 4,981 held-out users, full 43,853-item catalogue, no negative sampling:

| Model | HR@10 | HR@50 | NDCG@10 | Recall@20 | AUC | Coverage |
|---|---|---|---|---|---|---|
| Popularity baseline | 0.295 | 0.539 | 0.065 | 0.083 | 0.970 | 0.005 |
| Item-item kNN | 0.393 | 0.652 | 0.098 | 0.120 | 0.990 | 0.043 |
| Implicit ALS | 0.454 | 0.768 | 0.109 | 0.160 | 0.912 | 0.074 |
| **Hybrid (fused)** | **0.454** | 0.755 | **0.116** | **0.163** | 0.950 | 0.059 |

**Lift over the popularity baseline: 1.54x HR@10, 1.78x NDCG@10, 1.97x Recall@20, 12.1x catalogue coverage.**

### A note on "accuracy"

Ranking AUC is the number that looks best here, and it is the one worth trusting
least. The popularity baseline scores **0.970** on it — because over a 95k-title
catalogue, almost every pair a model is asked to order is trivially easy. Any model
clears 90% AUC on this task, so "94% accurate" would be true and say nothing.

Hit rate and NDCG are the metrics that separate a recommender from a bestseller
list, which is why the baseline is reported beside every number rather than omitted.
A recommender is only as good as the margin by which it beats "just show what's
popular".

### The evaluation protocol, precisely

Weak protocols inflate these numbers by 2-5×, so this one is stated in full:

1. **Held-out users, not held-out ratings.** Evaluation users are removed from the
   training matrix entirely. Their embeddings are produced by the same fold-in path
   that serves a real signup, so the measurement reflects the live experience.
2. **Chronological split.** Each user's history is cut by time — earliest 80% is the
   visible profile, most recent 20% is the target. The task is predicting the
   future, not interpolating a random hole.
3. **Full-catalogue ranking.** Every unseen title competes. Sampling 100 negatives
   (very common, rarely disclosed) inflates hit rate several-fold.
4. **Baseline always reported.** Including coverage and Gini, because a model that
   only ever surfaces the same 200 blockbusters can post good accuracy while being
   worthless.

Regenerate with `python -m app.ml.train`; the report lands in
`models_checkpoint/evaluation_metrics.json` and is served at `/api/system/metrics`.

---

## How the engine works

```
                    ratings.csv (33.1M)          catalogue (96k titles, TMDB)
                           │                                │
                    ┌──────┴──────┐                         │
                    ▼             ▼                         ▼
              implicit ALS    item-item kNN          multi-channel TF-IDF
              (f=128, CG)     (top-200, shrunk)      (8 weighted channels)
                    │             │                         │
                    └─────┬───────┴────────────┬────────────┘
                          ▼                    ▼
                    z-score fusion  +  quality prior (shrunk mean)
                                   │
                                   ▼
                     MMR diversity + novelty re-rank
                                   │
                                   ▼
                     ranked list + per-item attribution
```

### 1. Implicit ALS with a batched conjugate-gradient solver

The Hu/Koren/Volinsky objective, with two refinements that matter:

**Conjugate-gradient inner solve** (Takács et al., 2011). The exact ridge solve is
`O(f³ + n_u f²)` per user. CG reaches effectively the same point in three iterations
at `O(n_u f)` per step.

**A batched solver.** This was the actual bottleneck. Solving each user's system in
a Python loop spent nearly all its time on interpreter and NumPy dispatch overhead —
an average profile touches only a few dozen items, so every call was overhead-bound.
Advancing the *whole batch* together turns the solve into four BLAS and sparse
kernels (`P @ YtY`, a chunked sampled dense-dense product, and a sparse-dense
scatter):

| Solver | Per iteration (20.6M observations, f=128) |
|---|---|
| Per-user Python loop | 474 s |
| Batched CG (this) | **71 s** |

Numerically identical — both report observed-RMSE 0.5302 after iteration 1 — but
6.7× faster, and it scales with cores instead of with interpreter speed.

**Frequency-scaled regularisation** (Rendle et al., 2022): penalising every
embedding equally over-regularises long profiles and under-regularises the tail.
Scaling by `(count)^ν` closes much of the reported gap to far costlier models.

### 2. Item-item neighbourhood

Cosine similarity over co-occurrence, with two corrections that decide whether this
model is useful or noise:

- **Shrinkage.** Raw cosine on sparse data is dominated by coincidence — two obscure
  films sharing their only two viewers score 1.0. Damping by `n/(n+h)` pushes those
  to zero while leaving well-supported pairs alone.
- **Popularity damping.** Normalising by `‖x‖^α` with α<1 stops blockbusters from
  being everyone's nearest neighbour, which is what otherwise collapses
  neighbourhood recommendations onto the head of the catalogue.

It also supplies the **attribution**: "because you liked X" is a read-out of which
profile items actually contributed the most score, not a plausible-looking match
found after the fact.

### 3. Multi-channel content model

The naive approach — concatenate all metadata into one string, run one TF-IDF — has
a structural flaw: a 60-word plot summary contributes ~60 terms while the genre list
contributes three, so genre agreement is drowned out no matter how often you repeat
it.

Here each field is vectorised in its own space, **L2-normalised within that space**,
then scaled by an explicit weight. Every channel contributes a bounded, tunable
share independent of its verbosity:

| Channel | Weight | Signal |
|---|---|---|
| genres | 1.00 | strongest single predictor of taste agreement |
| keywords | 0.85 | TMDB plot keywords — themes, not words |
| tags | 0.85 | MovieLens folk tags ("mindfuck", "based on a book") |
| director | 0.75 | authorship; a strong stylistic fingerprint |
| cast | 0.60 | shared leads, damped so ensembles don't dominate |
| overview | 0.55 | free text, the noisiest channel |
| era | 0.30 | release decade |
| language | 0.25 | mostly separates non-English cinema |

Names become single tokens (`christopher_nolan`), so two films match on one strong
token rather than on "Christopher" matching every other Christopher.

This is what makes cold start and new releases work: a film released last week has
no collaborative signal, but it has genres, a director and a plot.

### 4. Fold-in serving

Application users are **never in the training matrix**. Their embedding is solved on
demand from the frozen item factors — one exact Cholesky solve, `O(f³)`,
microseconds at f=128. A brand-new account gets real recommendations from its first
ten ratings with no retraining, and it's the same code path the evaluation measures.

### 5. Diversity and novelty re-ranking

Relevance alone produces ten films from one cluster. A maximal-marginal-relevance
pass trades a little relevance for spread, and a novelty term shifts weight toward
the tail. Both are exposed as API parameters and as sliders in the UI, because the
right balance is a matter of taste rather than a single correct value.

---

## Data pipeline

| Stage | What it does | Cost |
|---|---|---|
| `app.pipeline.ingest` | MovieLens → catalogue rows + rating aggregates | ~20 s |
| `app.pipeline.enrich enrich` | TMDB metadata for every title | ~45 min @ 33 req/s |
| `app.pipeline.enrich discover` | imports titles MovieLens doesn't have (2023+) | minutes |
| `app.pipeline.enrich scores` | rebuilds ranking columns on one scale | ~1 s |
| `app.ml.train` | trains, evaluates, writes artifacts | ~25 min |
| `app.ml.content` | builds the content matrix | ~1 min |

Two decisions worth calling out:

**Individual rating rows never enter the database.** There are 33.8M of them;
inserting those through an ORM is what exhausted memory in an earlier iteration and
left the database with a fully populated catalogue and *zero* ratings. Training
reads `ratings.csv` directly via Arrow — **891 MB in 1.1 s** — and the catalogue
stores only per-title aggregates. The serving path needs the item factors and the
current user's ratings, never the historical rows.

**MovieLens ends in July 2023.** It has 1,962 titles for 2022 and 79 for 2024, so
anything recent has to come from TMDB's discover feed. That's what
`enrich discover` is for. After running it the catalogue holds 95,947 titles, 93,641 with artwork (97.6%) and 56,458 with a trailer:

| Year | MovieLens only | After TMDB discover |
|---|---|---|
| 2023 | 556 | 3,159 |
| 2024 | 79 | 2,983 |
| 2025 | 119 | 2,775 |
| 2026 | 0 | 1,168 |

---

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/movies/home` | every home-page carousel in one response |
| `GET /api/movies/browse` | paginated browse; genre/era/rating/language filters |
| `GET /api/movies/search?q=` | FTS5 full-text over title, director, cast |
| `GET /api/movies/{id}` | full record incl. trailer, cast, keywords |
| `GET /api/movies/{id}/similar` | collaborative + content blend |
| `GET /api/recommendations` | personalised; `diversity`, `novelty`, `genres` |
| `POST /api/ratings` · `/batch` | rate one film, or a whole onboarding grid |
| `GET/POST/DELETE /api/ratings/watchlist` | watchlist |
| `GET /api/ratings/stats` | taste profile aggregates |
| `GET /api/system/metrics` | the evaluation report above |
| `GET /api/system/stats` | catalogue coverage and engine state |

Interactive docs at `/docs`.

### Performance work

- **Split card and detail payloads.** A 36-tile grid was shipping 36 plot summaries,
  cast lists and tag blobs — tens of KB that nothing rendered.
- **Image paths, not URLs.** The API returns the bare TMDB path; the client composes
  the width it will actually paint via `srcset`. Previously every image was
  requested at `w500`, so a 160px thumbnail pulled a 70KB poster.
- **FTS5 instead of `LIKE '%q%'`**, which cannot use an index and full-scanned 95k
  rows per keystroke.
- **Cached filter counts.** `COUNT(*)` over a filtered catalogue can't use a
  covering index and was re-run on every page change.
- **In-process TTL cache** replacing a Redis dependency that timed out on every
  startup and silently disabled caching — the dependency's cost without its benefit.
- **SQLite tuned for concurrent reads**: WAL, `mmap_size`, a 128MB page cache, and
  `foreign_keys=ON` (off by default, so none of the declared cascades were being
  enforced).
- **Non-blocking startup.** Ingestion and training are explicit offline steps, so a
  cold container answers its health check in under a second.

---

## Frontend

React 18 · Vite 5 · Tailwind · TanStack Query · Framer Motion

- Public landing page, public catalogue browse, public film pages — you can look
  before signing up, and a film URL is shareable.
- Onboarding grid that batch-submits ratings, so a new account is useful immediately.
- Blur-up responsive posters: a 2-4KB `w92` placeholder, `srcset` across six widths,
  lazy loading with a reserved aspect box so nothing reflows.
- Optimistic rating and watchlist mutations — the star fills before the round trip.
- ⌘K command palette with debounced instant search.
- Route-level code splitting: a first-time visitor downloads the landing chunk
  (~6.6KB gzipped) and nothing else.
- Honours `prefers-reduced-motion` throughout.

---

## Running it

### Requirements

Python 3.11+ · Node 18+ · a free [TMDB API key](https://www.themoviedb.org/settings/api)
· ~4GB disk for the dataset and artifacts

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env          # then set TMDB_API_KEY and SECRET_KEY

python -m app.pipeline.ingest              # catalogue + aggregates  (~20s, downloads 335MB on first run)
python -m app.pipeline.enrich enrich       # TMDB metadata           (~45min, resumable)
python -m app.pipeline.enrich discover     # 2023+ titles MovieLens lacks
python -m app.pipeline.enrich scores       # unify ranking columns
python -m app.ml.train                     # train + evaluate        (~25min)
python -m app.ml.content                   # content matrix

uvicorn app.main:app --reload --port 8005
```

Every pipeline step is resumable and safe to re-run. `enrich` marks rows it has
attempted, so an interrupted run picks up where it stopped rather than restarting.

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The dev server proxies `/api` to `127.0.0.1:8005`, so the browser sees one origin and
never issues a CORS preflight. For a split deployment, set `VITE_API_URL`.

### Tests

```bash
pytest          # 54 tests: engine components + API contract
```

### Docker

```bash
docker compose up        # API on :8005, SQLite + in-process cache
```

---

## Deployment

- **Frontend → Vercel.** `frontend/vercel.json` handles SPA rewrites and immutable
  asset caching. Set `VITE_API_URL` to the API origin.
- **Backend → Render.** `render.yaml` is a single web service with a 2GB persistent
  disk for `movico.db` and the model artifacts.

Deliberately *not* Postgres + Redis: the catalogue is read-mostly and the models are
NumPy artifacts on disk, so SQLite on a mounted disk is faster and simpler than a
network database, and a local cache beats Redis for a single instance — no
serialisation, no network hop. Both choices keep this inside free tiers.

Set `ADMIN_TOKEN` to enable the maintenance endpoints, or leave it blank to disable
them entirely (the default, and the right setting for a public deployment).

---

## Project layout

```
app/
├── ml/                     the recommendation engine
│   ├── dataset.py          Arrow-based interaction artifacts
│   ├── ials.py             batched-CG implicit ALS
│   ├── itemknn.py          shrunk item-item neighbourhood
│   ├── content.py          weighted multi-channel TF-IDF
│   ├── ranker.py           fusion, fold-in, MMR, attribution
│   ├── evaluate.py         strong-generalisation metrics
│   └── train.py            offline orchestrator
├── pipeline/
│   ├── ingest.py           MovieLens → catalogue
│   ├── tmdb.py             async paced TMDB client
│   ├── enrich.py           bulk enrichment, discover, scoring
│   └── migrate.py          idempotent schema + FTS reconciliation
├── api/routes/             auth · movies · ratings · recommend · system
├── database/               ORM models, response schemas, engine
└── services/               cache, recommendation orchestration

frontend/src/
├── lib/                    api client, query hooks, auth, image URLs
├── components/             Poster, MovieCard, MovieRow, CommandPalette, …
└── pages/                  Landing, Home, Browse, MovieDetail, Onboarding, …
```

---

## Credits

Ratings and tags from the [MovieLens](https://grouplens.org/datasets/movielens/)
`ml-latest` dataset (GroupLens Research, University of Minnesota). Metadata, artwork
and trailers from [TMDB](https://www.themoviedb.org/) — this product uses the TMDB
API but is not endorsed or certified by TMDB.
