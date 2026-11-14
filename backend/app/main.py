from __future__ import annotations
import hmac
import queue
from dataclasses import asdict
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from . import config, jobs, store
from .ingest import ingest

app = FastAPI(title="FINN backend")
jobs.recover()   # jobs that were queued/running when the previous process died are marked interrupted
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["Content-Type", "X-Access-Code"])


def err(status: int, code: str, message: str, **extra) -> JSONResponse:
    """Uniform error body: {error, message, detail} — `detail` mirrors `message` for simple clients."""
    return JSONResponse(status_code=status, content={"error": code, "message": message, "detail": message, **extra})


@app.get("/health")
def health():
    return {"ok": True, "seeds": len(list(config.SEED_DIR.glob("*.json"))) if config.SEED_DIR.exists() else 0,
            "llm_configured": bool(config.GEMINI_API_KEY), "access_code_required": bool(config.ACCESS_CODE), "cap": store.cap_status()}


@app.post("/ingest/{ticker}")
def ingest_ticker(ticker: str):
    return asdict(ingest(ticker))


@app.get("/research")
def list_research():
    return {"items": store.summaries(), "cap": store.cap_status(), "access_code_required": bool(config.ACCESS_CODE)}


@app.get("/research/jobs/{job_id}")
def job_status(job_id: str):
    j = jobs.get(job_id)
    if not j:   # unknown id (lost with a restart / expired): report it as interrupted, not as an error
        return {"id": job_id, "ticker": None, "status": "interrupted", "message": jobs.INTERRUPTED_MSG, "error": jobs.INTERRUPTED_MSG,
                "error_code": "interrupted", "created_at": None, "started_at": None, "finished_at": None, "result_ready": False}
    return {**{k: j.get(k) for k in ("id", "ticker", "status", "message", "error", "error_code", "created_at", "started_at", "finished_at")},
            "result_ready": j.get("status") == "done"}


@app.get("/research/{ticker}")
def get_research(ticker: str, full: bool = False):
    t = ticker.upper()
    if not store.TICKER_RE.match(t):
        return err(400, "bad_ticker", "Ticker must be an NSE symbol: letters, digits, & or -, up to 20 characters.")
    r = store.load(t, full=full)
    if not r:
        return err(404, "not_analysed", f"No research for {t} yet. POST /research/{t} to analyse it.")
    return r


@app.post("/research/{ticker}")
def start_research(ticker: str, refresh: bool = False, x_access_code: Optional[str] = Header(default=None)):
    t = ticker.upper()
    if not store.TICKER_RE.match(t):
        return err(400, "bad_ticker", "Ticker must be an NSE symbol: letters, digits, & or -, up to 20 characters.")
    exists = store.load(t)
    if exists and not refresh:   # viewing an existing result (seed or live) is free and never starts a job
        return JSONResponse(status_code=200, content={"status": "ready", "ticker": t, "source": exists["source"]})
    if refresh and not config.ACCESS_CODE:   # an unprotected server never re-runs anything (a replayed request cannot spend the key)
        return err(403, "refresh_disabled", "Re-running an existing analysis is disabled on this server (no access code is configured).")
    if config.ACCESS_CODE:
        if not x_access_code:
            return err(401, "access_code_required", "An access code is required to analyse a new ticker. Enter the code you were given.")
        if not hmac.compare_digest(x_access_code.encode(), config.ACCESS_CODE.encode()):
            return err(403, "access_code_invalid", "That access code is not valid.")
    if exists and refresh:       # cooldown: a recent result is returned as-is, so a replayed request costs nothing
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(exists["generated_at"])
        except (KeyError, ValueError):
            age = timedelta(days=999)
        if age < timedelta(minutes=config.REFRESH_COOLDOWN_MINUTES):
            return JSONResponse(status_code=200, content={"status": "ready", "ticker": t, "source": exists["source"], "note": "analysed recently; not re-run"})
    if not config.GEMINI_API_KEY:
        return err(503, "llm_not_configured", "This server has no language-model key configured, so it can only serve existing research.")
    if not store.reserve():
        c = store.cap_status()
        return err(429, "daily_cap_reached", f"Today's limit of {c['limit']} new analyses has been reached. Existing research is still free to view. "
                   f"Try again after {c['resets_at']} (UTC).", **c)
    try:
        job = jobs.submit(t)
    except queue.Full:
        store.refund()
        return err(429, "busy", "The analysis queue is full. Please try again in a few minutes.")
    return JSONResponse(status_code=202, content={"job_id": job["id"], "ticker": t, "status": job["status"], "message": job["message"]})
