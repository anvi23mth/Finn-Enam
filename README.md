# FINN — financial investment agent (prototype)

**Live demo:** https://finn-enam-eta.vercel.app · [Architecture](docs/ARCHITECTURE.md) · [Deployment guide](DEPLOY.md)

A mobile-first web app for an investor with a portfolio of 19 NSE names. One idea: **filter hard, and always say who in your network can help.**

| Tab | What it does | Data |
|---|---|---|
| **Today** | Live feed of corporate announcements, classified (category + priority + one-line summary), grouped High / Medium / Routine, with a 24h–30d window; extracted Revenue/EBITDA/PBT/PAT tables for results filings; price/volume alerts; network matching on every card. A separate **Demo scenarios** toggle shows invented filings that showcase the network. | Real (screener.in, Yahoo) + LLM classification |
| **Research** | Cited, primary-source research on a company: business, financials, promised-vs-delivered, cash quality, bull/bear. INFY, DEEPAKNTR, TITAN and TMPV ship as seeds; any other NSE ticker can be analysed through the backend (job queue, daily cap, optional access code). | Real (annual report + last 4 concalls) + LLM |
| **Network** | Who to call, second-degree reach, expertise map, keep-warm, "quiet advantages". Each filing/card shows a visible matching step: entities recognised → contacts matched, with the reason. | **Synthetic** |

Every card and section carries a **Real** or **Demo** badge. Architecture, security and LLM notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it locally

Needs Node 18+ and Python 3.9+.

**Frontend** (works on its own — it falls back to the committed data and the four research seeds):

```bash
npm install
npm run dev          # http://localhost:5173 (also on your LAN for phone testing)
```

**Backend** (only needed to analyse new tickers, or to re-run the data scripts):

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then edit .env; never commit it
.venv/bin/uvicorn app.main:app --port 8000
```

In dev, Vite proxies `/research/*` to `localhost:8000`. For a separately hosted API, set `VITE_API_BASE` when building the frontend.

### `backend/.env.example`

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Required for classification, results extraction and analysing new tickers. Viewing existing research and the feed needs no key. |
| `CHEAP_MODEL`, `STRONG_MODEL`, `STRONG_MODEL_FALLBACKS`, `STRONG_RETRIES` | Model routing (see ARCHITECTURE → LLMs). |
| `LLM_MIN_INTERVAL`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT`, `LLM_MAX_WAIT` | Pacing, retries and fail-fast limits for Gemini calls. |
| `DOCS_DIR`, `CONCALL_COUNT`, `REQUEST_DELAY`, `USER_AGENT`, `REQUEST_TIMEOUT` | Document ingestion from screener.in. |
| `ALLOWED_ORIGINS` | CORS allow-list for the API. |
| `ACCESS_CODE` | If set, analysing a **new** ticker needs the header `X-Access-Code`. Re-running an existing analysis is refused unless a code is configured and supplied. |
| `MAX_NEW_ANALYSES_PER_DAY`, `MAX_QUEUED_JOBS`, `REFRESH_COOLDOWN_MINUTES` | Spend protection. |

`backend/.env.deploy.example` lists the settings used for the hosted deployment: the frontend is on Vercel (https://finn-enam-eta.vercel.app) and the FastAPI backend on Render's free tier (https://finn-backend-2lby.onrender.com). The free tier sleeps after idle, so the first load can take about a minute; until the backend wakes, the app falls back to the committed research seeds. State is file-based and not durable on the free tier (it can reset on restart or redeploy). See [DEPLOY.md](DEPLOY.md) and the "Cloud" section of the architecture doc.

### Refreshing the data

```bash
npm run prices                                                          # EOD prices -> public/prices.json (Yahoo; failures become "no data")
cd backend
.venv/bin/python -m scripts.fetch_announcements                         # screener.in -> data/announcements/<TICKER>.json + all.json
.venv/bin/python -I scripts/classify_announcements.py                   # classify -> data/announcements/classified.json (+ public/ copy)
.venv/bin/python -I scripts/classify_announcements.py --skip-classify --results TMPV ITC   # extract results tables -> data/results/<TICKER>.json
.venv/bin/python scripts/ingest.py INFY                                 # fetch annual report + concalls for a ticker
.venv/bin/python scripts/research.py INFY                               # full research pipeline for a ticker
.venv/bin/python scripts/make_seed.py INFY DEEPAKNTR TITAN TMPV                    # publish finished research as seeds
```

After changing `public/` data, rebuild or reload the frontend. Nothing runs on a schedule yet; every refresh is a manual run.

## Data sources

| Data | Source | How |
|---|---|---|
| Prices & volume | Yahoo Finance chart API (`<TICKER>.NS`, 3 months daily) | `scripts/fetch-prices.mjs`. A ticker that fails is written as `no_data`; synthetic data exists only behind `--demo` and is labelled. |
| Announcements | screener.in company page ("Announcements" box; PDF links point to BSE) | `backend/app/announcements.py`. NSE/BSE clients exist but are opt-in (`--exchanges`) and skipped on 403. |
| Announcement categories | The challenge reference PDF's category definitions | Used as the classifier's rules. |
| Results tables | The results filing PDF itself | Downloaded, text extracted, figures verified against the page. |
| Fundamentals / research | Latest annual report + last 4 concall transcripts (screener.in links) | Primary documents only. |
| Network & filing-person profiles | **Invented** (`src/data/network.ts`, `src/data/graph.ts`) | Synthetic. |

The portfolio is `src/data/portfolio.ts` (19 tickers; `TATAMOTORS` was replaced by `TMPV` and `TMCV` after the demerger).

## Known limitations

- **screener.in shows only the latest 5 announcements per company** to anonymous users (its "Important" and "Search" tabs need a login). The live feed is therefore complete for a few days at most; the 7d/30d windows are incomplete, and the files only grow if you re-run the fetch regularly.
- **NSE and BSE block scripted requests** (HTTP 403 "Access Denied", including the cookie warm-up page). The code for both is kept but is optional and skipped; nothing works around the block.
- **The network is synthetic**: 36 invented people and a made-up supplier/rival graph, labelled as such in the UI. It is bundled into the frontend, so a real network must never be loaded this way (see ARCHITECTURE → security).
- **Gemini capacity errors (503s/timeouts) on the larger models** led to the cheap model, `gemini-3.5-flash-lite`, being the working default: it runs classification, extraction and, in the deploy settings, Stage 2 of research. The four committed research seeds were generated with Stage 2 forced onto it (`--fast-stage2`). Synthesis quality on the lite model is lower than the strong chain intends.
- **LLM output can be wrong.** Research claims and results figures are checked against the source page text, and unverifiable ones are dropped or flagged, but classification (category/priority/summary) is unchecked model output — spot-check it.
- **Results extraction** covers TMPV and ITC only; DEEPAKNTR's filing is a scanned image and was not OCR'd. EBITDA is derived (not stated) and flagged; year-over-year changes distorted by discontinued operations (TMPV) are flagged, not corrected.
- **Research coverage** is four seeded tickers (INFY, DEEPAKNTR, TITAN, TMPV) plus whatever has been analysed live; analysing a new ticker takes minutes and is capped per day.
- **Operations are prototype-grade**: one in-process worker, file-based state, no scheduler, a single shared access code, no user accounts.
