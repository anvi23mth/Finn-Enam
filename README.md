# FINN — Financial Investment Agent (prototype)

Mobile-first web app (React + Vite + TS). Three tabs, one idea: **filter hard, and always say who in your network can help.**

```bash
npm install
npm run prices   # refresh EOD prices (Yahoo chart API, synthetic fallback)
npm run dev      # open on your phone via the LAN URL
```

## What works today
- **Push (Today):** selectable window (24h/3d/7d); filings ranked by priority with routine ones collapsed; configurable price/volume alerts computed from real EOD data; result cards with Revenue/EBITDA/PBT/PAT QoQ & YoY; management-change card with the person's bio and overlaps with your network; "worth a call" reconnect nudges.
- **Pull (Research):** structured primary-source view incl. promised-vs-delivered, cash quality, bull/bear (INFY, DEEPAKNTR sample).
- **Network:** ask by company or theme; ranked by relevance × relationship strength. Also woven into Push and Pull cards.

## Honest status
- Prices: live from Yahoo where reachable; otherwise synthetic.
- Announcements, network profiles and research content are **mock/synthetic** (`src/data/`), shaped like the real feeds. Labelled "demo data" in the UI.
- Not built yet: NSE/BSE announcement poller, LLM extraction pipeline for any ticker, backend, auth.

## Architecture (target)
Pipelines: scheduled workers poll NSE/BSE announcements → classify (cheap model/rules) → store; EOD prices nightly; annual reports + concalls fetched from screener.in, chunked, extracted to JSON by a small model, cached by document hash; strong model only for narrative-vs-numbers and bull/bear. Names in filings are matched to network people by employer/school overlap.
Privacy: network data is per-user, encrypted at rest, row-level access control, consented imports only, deletable; no third-party profile scraping.
