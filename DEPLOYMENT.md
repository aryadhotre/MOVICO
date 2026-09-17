# Deploying MOVICO

Three free services. Nothing here requires a card.

| | Service | Free tier limits that shaped the design |
|---|---|---|
| Frontend | Vercel | 100 GB bandwidth/month |
| API | Render | 512 MB RAM, **no persistent disk**, sleeps after 15 min idle |
| User database | Supabase | 500 MB, pauses after 1 week idle, 60 direct / 200 pooled connections |

Work through the phases in order. Each one ends in a state you can check.

---

## Phase 0 — What you need before starting

- The repository pushed to GitHub (it is).
- A TMDB API key — free, no card: <https://www.themoviedb.org/settings/api>.
  You already have one in your local `.env`; you will paste the same value into
  Render.
- Accounts on [Supabase](https://supabase.com), [Render](https://render.com) and
  [Vercel](https://vercel.com). Sign in to all three with **GitHub** so the
  repository connection works without extra steps.

---

## Phase 1 — Supabase (the user database)

This holds accounts, password hashes, ratings and watchlists. Nothing else.

1. **New project.** Dashboard → *New project*.
   - Name: `movico`
   - Database password: generate a strong one and **save it in your password
     manager now**. Supabase shows it once and you cannot recover it later — only
     reset it, which invalidates the connection string you are about to copy.
   - Region: pick the one nearest you.
   - Wait ~2 minutes for provisioning.

2. **Copy the connection string.** *Project Settings → Database → Connection
   string → URI*, and switch the mode selector to **Transaction pooler**. It looks
   like:

   ```
   postgresql://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
   ```

   Replace `[YOUR-PASSWORD]` with the password from step 1.

   > **Use the pooler on port 6543, not the direct connection on 5432.** A free
   > project allows only 60 direct sessions, and the API opens a connection per
   > request by design (`NullPool`) because the pooler multiplexes them
   > server-side. Pointing at 5432 works until it suddenly does not.

   If your password contains `@ : / ? # [ ] %`, percent-encode it — `@` becomes
   `%40`, `#` becomes `%23`. Otherwise the URL parses wrongly and you get an
   authentication error that looks like a bad password.

3. **Nothing else.** Do not create tables. The API creates its own schema on first
   boot.

**Check:** you have a URI beginning `postgresql://postgres.` and containing `:6543/`.

---

## Phase 2 — The artifact bundle

The catalogue and trained models are too large for Git (215 MB and 127 MB; GitHub
rejects any file over 100 MB). They ship as a release asset instead.

1. **Build it** — already done, but to rebuild after retraining:

   ```bash
   python -m scripts.package_artifacts
   ```

   This compacts the database, packs everything into
   `dist/movico-artifacts.tar.gz` (~172 MB) and prints a **sha256**. Keep that
   hash.

2. **Create a GitHub release.**
   - Go to <https://github.com/aryadhotre/MOVICO/releases/new>
   - Tag: `artifacts-v1` → *Create new tag on publish*
   - Title: `Catalogue and model artifacts v1`
   - Drag `dist/movico-artifacts.tar.gz` into the attachment box and wait for the
     upload to finish (172 MB — several minutes on a home connection).
   - *Publish release*.

3. **Copy the asset URL.** Right-click the uploaded file → *Copy link address*:

   ```
   https://github.com/aryadhotre/MOVICO/releases/download/artifacts-v1/movico-artifacts.tar.gz
   ```

**Check:** opening that URL in a browser starts a download.

---

## Phase 3 — Render (the API)

1. **New Web Service.** Dashboard → *New* → *Web Service* → connect the `MOVICO`
   repository.
   - Language/Runtime: **Docker** (it should detect this from the `Dockerfile`)
   - Branch: `main`
   - Instance type: **Free**
   - Name: `movico-api`
   - Health check path: `/api/system/health`

2. **Environment variables.** Add these under *Environment* before the first
   deploy. Anything marked *generate* uses Render's own generator.

   | Key | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `DEBUG` | `false` |
   | `SECRET_KEY` | click **Generate** |
   | `DATABASE_URL` | the Supabase pooler URI from Phase 1 |
   | `TMDB_API_KEY` | your TMDB key |
   | `ARTIFACTS_URL` | the release asset URL from Phase 2 |
   | `ARTIFACTS_SHA256` | the hash printed by `package_artifacts` |
   | `CORS_ORIGINS` | *leave blank for now — Phase 4 fills it in* |
   | `VERCEL_PROJECT` | `movico` |
   | `SQLITE_MMAP_MB` | `64` |
   | `REDIS_ENABLED` | `false` |
   | `DATA_DIR` | `/workspace/data` |
   | `MODELS_DIR` | `/workspace/models_checkpoint` |
   | `ADMIN_TOKEN` | leave blank (disables the retrain/reimport endpoints) |

   > `CORS_ORIGINS` blank means the API will refuse to boot, because
   > `APP_ENV=production` requires it. That is deliberate and you will fix it in
   > Phase 4 — but if you want the first deploy to succeed on its own, put
   > `https://movico.vercel.app` in now and correct it later if Vercel assigns a
   > different name.

3. **Deploy.** The first build takes 10–15 minutes: it compiles NumPy and SciPy
   wheels and downloads the 172 MB bundle. Later deploys reuse both layers.

**Check:** `https://movico-api.onrender.com/api/system/health` returns

```json
{ "status": "healthy", "database": "up", "user_database": "up", "engine": "up" }
```

If `user_database` is `down`, the Supabase URI is wrong — check the password
encoding and that the port is 6543.
If `engine` is `untrained`, the artifact download failed — check the build log for
a checksum mismatch.

---

## Phase 4 — Vercel (the frontend)

1. **New Project** → import the `MOVICO` repository.
   - **Root Directory: `frontend`** ← this one matters; the build fails without it
   - Framework preset: Vite (detected)
   - Build command and output directory: leave as detected

2. **Environment variable:**

   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://movico-api.onrender.com` (no trailing slash) |

3. **Deploy.** Note the domain Vercel gives you, e.g. `https://movico.vercel.app`.

4. **Close the CORS loop.** Back in Render → *Environment*:
   - Set `CORS_ORIGINS` to your exact Vercel domain, e.g.
     `https://movico.vercel.app`
   - Set `VERCEL_PROJECT` to the project slug — the part before `.vercel.app`, so
     `movico`. This allows preview deployments of *your* project without allowing
     every `*.vercel.app` in existence.
   - Save; Render restarts automatically.

**Check:** open the Vercel URL. The landing page loads, posters appear, search
returns results. Sign up, rate ten films, and confirm recommendations come back
with explanations.

---

## Phase 5 — Verify it properly

Run these against the deployed API.

```bash
API=https://movico-api.onrender.com

# Both databases and the model engine
curl -s $API/api/system/health | python -m json.tool

# Catalogue size and coverage
curl -s $API/api/system/stats | python -m json.tool

# Search works (FTS5, not a LIKE fallback)
curl -s "$API/api/movies/search?q=oppenheim" | python -m json.tool | head -20

# Security headers are present
curl -sD - -o /dev/null $API/api/system/health | grep -i "content-security\|x-frame\|x-content-type"

# A foreign origin is refused — this must print nothing
curl -sD - -o /dev/null -X OPTIONS $API/api/movies/home \
  -H "Origin: https://evil.vercel.app" -H "Access-Control-Request-Method: GET" \
  | grep -i "access-control-allow-origin"

# Six bad logins: the sixth must be 429
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w "$i -> %{http_code}\n" -X POST $API/api/auth/login \
    -d "username=nobody&password=wrong"
done
```

Then in the Supabase dashboard → *Table Editor*: you should see `users`,
`ratings`, `watchlists` and `recommendation_history`, with your account in
`users` and a `password_hash` that starts with `$2b$` — a bcrypt hash, not the
password.

---

## Living with the free tiers

**Render sleeps after 15 minutes idle.** The first request afterwards takes ~50
seconds. The frontend shows a "warming the projector" cue with a counter instead
of an error, so this reads as a known cost rather than a bug. If you want to avoid
it for a demo, open the site a minute before.

**Supabase pauses a project after one week of inactivity.** Browsing, search and
recommendations keep working — they run entirely off the baked-in catalogue — but
sign-in fails until you resume the project from the dashboard (one click). The
health endpoint reports `"user_database": "down"` while this is the case, and
deliberately still returns HTTP 200, because restarting the API would not fix it
and would take the working half offline too. Visit the project once a week, or
before showing it to anyone.

**Render free gives 500 build minutes/month.** `render.yaml` only rebuilds the API
when `app/`, `scripts/`, `requirements.txt`, `Dockerfile` or `render.yaml` change,
so frontend commits do not spend them.

---

## Updating things later

**Frontend or backend code** — push to `main`. Vercel and Render both redeploy.

**The catalogue or the models** (after `python -m app.pipeline.enrich` or
`python -m app.ml.train`):

```bash
python -m scripts.package_artifacts
```

Upload the new `dist/movico-artifacts.tar.gz` to a **new** release tag
(`artifacts-v2`), then update `ARTIFACTS_URL` and `ARTIFACTS_SHA256` on Render. Use
a new tag rather than replacing the asset in place — Docker caches the download
layer by URL, so a same-URL replacement may not be picked up.

**Never** put `SECRET_KEY`, `DATABASE_URL`, `TMDB_API_KEY` or `ADMIN_TOKEN` in the
repository, in `render.yaml`, or in a Dockerfile `ARG`. Render turns every
environment variable into a build argument, and anything a Dockerfile declares an
`ARG` for is recorded in the image's build history. Only `ARTIFACTS_URL` and
`ARTIFACTS_SHA256` are declared there, and both are public by nature.

Regenerating `SECRET_KEY` invalidates every issued token and signs out every user.
