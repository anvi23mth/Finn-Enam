# Deploying FINN

Frontend (static, Vercel) and backend (FastAPI, Render) deploy separately. **Order: Render → Vercel → back to Render.**
Repo: `https://github.com/anvi23mth/Finn-Enam` · branch: `main`.

The app works with the backend asleep or down: Today, Network and the four seeded Research results (INFY, DEEPAKNTR, TITAN, TMPV) are static files
in `public/`. The backend only adds *new analyses* and the live results list.

## 1. Backend on Render (free web service)

**Blueprint route (reads `render.yaml`):**
1. https://dashboard.render.com → sign in with GitHub.
2. **New +** → **Blueprint** → connect `anvi23mth/Finn-Enam` (allow Render to access it) → branch **main** → **Apply**.
3. Fill the three secrets it asks for:
   - `GEMINI_API_KEY` — your key from https://aistudio.google.com/apikey
   - `ACCESS_CODE` — a long random string you choose (`openssl rand -hex 12`). Save it in a password manager.
   - `ALLOWED_ORIGINS` — `http://localhost:5173` for now (you set the real value in step 3 below).
4. Wait for the deploy to finish (Logs show `Application startup complete`). Copy the service URL, e.g. `https://finn-backend-xxxx.onrender.com`.
5. Open `<that URL>/health` — expect `{"ok":true,"seeds":4,...}` — and `<that URL>/research` — expect INFY, DEEPAKNTR, TITAN and TMPV.

**Manual route (no Blueprint):** New + → Web Service → connect the repo → Name `finn-backend` · Region Singapore · Branch `main` ·
Root Directory *(blank)* · Runtime **Python 3** · Build Command `pip install -r backend/requirements.txt` ·
Start Command `uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir backend` · Instance Type **Free** ·
Advanced → Health Check Path `/health` → add the environment variables below → Create Web Service.

### Environment variables (Render → service → Environment)

| Variable | Set to | Required | Why |
|---|---|---|---|
| `PYTHON_VERSION` | `3.9.6` | yes | the exact version the code and `requirements.txt` were tested on (Render needs full `x.y.z`) |
| `GEMINI_API_KEY` | your key | for new analyses | without it the API still serves seeds; new analyses return `llm_not_configured` |
| `ACCESS_CODE` | long random string | **yes, set it** | new analyses and re-runs need it (header `X-Access-Code`). If empty, re-runs are disabled and anyone can start a new analysis up to the daily cap |
| `ALLOWED_ORIGINS` | your Vercel URL, e.g. `https://finn-enam.vercel.app` (no trailing slash; comma-separate more) | yes | CORS: only this site may call the API |
| `STRONG_MODEL` | `gemini-3.5-flash-lite` | recommended | the larger Gemini models returned 503/timeouts in testing; this one answered every time |
| `CHEAP_MODEL` | `gemini-3.5-flash-lite` | recommended | extraction model |
| `STRONG_MODEL_FALLBACKS` | *(empty)* | no | comma-separated fallback chain; unnecessary when the strong model is already the cheap one |
| `STRONG_RETRIES` | `1` | recommended | retries per model before moving on; keeps one stuck call from holding the single worker |
| `LLM_TIMEOUT` | `60` | recommended | seconds per Gemini request |
| `MAX_NEW_ANALYSES_PER_DAY` | `3` | recommended | cap on new analyses per UTC day |
| `MAX_QUEUED_JOBS` | `3` (default) | no | queue length |
| `REFRESH_COOLDOWN_MINUTES` | `30` (default) | no | a result younger than this is never re-run |
| `LLM_MIN_INTERVAL` / `LLM_MAX_RETRIES` / `LLM_MAX_WAIT` | `4` / `6` / `120` (defaults) | no | Gemini pacing and backoff |
| `CHUNK_PAGES` / `AR_MAX_PAGES` / `S2_MAX_CHARS` | `8` / `48` / `48000` (defaults) | no | analysis size limits |
| `CONCALL_COUNT` / `REQUEST_DELAY` / `REQUEST_TIMEOUT` / `USER_AGENT` | defaults | no | document fetching |

Do not set `PORT` (Render injects it). `DOCS_DIR` can stay default.

## 2. Frontend on Vercel

1. https://vercel.com → sign in with GitHub → **Add New…** → **Project**.
2. Import `anvi23mth/Finn-Enam` (install the Vercel GitHub app if asked) → **Import**.
3. Configure Project: Framework Preset **Vite** (auto-detected) · Root Directory `./` · Build Command `npm run build` · Output Directory `dist` · Install Command default. (`vercel.json` already sets these and the SPA rewrite.)
4. Open **Environment Variables** → Name `VITE_API_BASE` · Value = your Render URL, e.g. `https://finn-backend-xxxx.onrender.com` (**no trailing slash**) · tick Production (and Preview) → Add.
5. **Deploy.** Copy the production URL, e.g. `https://finn-enam.vercel.app`.
6. Project → Settings → Git → confirm **Production Branch = `main`**.

`VITE_API_BASE` is read at build time: if you change it, redeploy (Deployments → ⋯ → Redeploy).

## 3. Connect them

1. Render → `finn-backend` → **Environment** → edit `ALLOWED_ORIGINS` to the Vercel URL (no trailing slash) → Save (Render redeploys).
2. Open the Vercel URL on your phone → Research tab shows INFY, DEEPAKNTR, TITAN and TMPV.
3. To analyse a new ticker: Research → search a ticker → Analyse → enter the access code when asked. Expect 3–10 minutes.

## What to know

- **Sleeping backend:** the free instance sleeps after ~15 minutes idle and takes up to about a minute to wake. The app gives the API 6 seconds, then shows the static seeds; Analyse shows "Could not reach the backend… try again in a minute".
- **Ephemeral disk:** new analyses, job files and the daily-cap counter live on the instance disk and are lost on restart, redeploy or spin-down. Seeds (committed) always survive. The cap is best-effort on the free tier; **`ACCESS_CODE` is the real protection** of your Gemini key.
- **Memory:** the free instance has 512 MB. Reading the largest annual report (462 pages) peaks at about 244 MB after the batching fix in `backend/app/extract.py` (it was 3.8 GB before).
- **Untested from Render:** whether screener.in / BSE serve their PDFs to a cloud IP. If a new analysis fails with "documents not found" on Render but works locally, that is the likely cause.
- **Refreshing the seeds:** run `backend/.venv/bin/python backend/scripts/make_seed.py INFY DEEPAKNTR TITAN TMPV` locally, then commit `backend/seed/research` and `public/seed/research`.
