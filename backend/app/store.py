"""Result storage: live results (data/research) override committed seeds (backend/seed/research); daily cap on new analyses."""
from __future__ import annotations
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from . import config

TICKER_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")
_lock = threading.Lock()


def _path(ticker: str) -> tuple[Path, str] | None:
    live = config.RESEARCH_DIR / f"{ticker}.json"
    if live.exists():
        return live, "live"
    seed = config.SEED_DIR / f"{ticker}.json"
    return (seed, "seed") if seed.exists() else None


def load(ticker: str, full: bool = False) -> dict | None:
    hit = _path(ticker)
    if not hit:
        return None
    data = json.loads(hit[0].read_text())
    data["source"] = hit[1]
    data.setdefault("generated_at", datetime.fromtimestamp(hit[0].stat().st_mtime, timezone.utc).isoformat(timespec="seconds"))
    if not full:      # trim bulky provenance; ?full=true returns everything
        data.pop("ingest", None)
        data.pop("facts_flagged", None)
        for d in data.get("stage1", []):
            d.pop("dropped", None)
    return data


def summaries() -> list[dict]:
    out = {}
    for d, src in ((config.SEED_DIR, "seed"), (config.RESEARCH_DIR, "live")):   # live overrides seed
        for p in sorted(d.glob("*.json")) if d.exists() else []:
            try:
                j = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            m = j.get("models", {})
            prev = out.get(p.stem) or {}
            out[p.stem] = {"ticker": p.stem, "company": j.get("company") or prev.get("company"),
                           "generated_at": j.get("generated_at") or datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                           "model_used": m.get("strong_used"), "used_fallback": bool(m.get("used_fallback")), "source": src}
    return sorted(out.values(), key=lambda x: x["ticker"])


# ---- daily cap -------------------------------------------------------------------------
def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _read() -> dict:
    try:
        u = json.loads(config.USAGE_FILE.read_text())
        return u if u.get("date") == _today() else {"date": _today(), "count": 0}
    except (OSError, json.JSONDecodeError):
        return {"date": _today(), "count": 0}


def cap_status() -> dict:
    with _lock:
        u = _read()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return {"limit": config.MAX_NEW_ANALYSES_PER_DAY, "used": u["count"], "resets_at": tomorrow.isoformat(timespec="seconds")}


def reserve() -> bool:
    """Atomically take one slot of today's budget. False if the cap is reached."""
    with _lock:
        u = _read()
        if u["count"] >= config.MAX_NEW_ANALYSES_PER_DAY:
            return False
        u["count"] += 1
        config.USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.USAGE_FILE.write_text(json.dumps(u))
        return True


def refund() -> None:
    """Give a slot back when a job failed before spending anything (e.g. documents not found)."""
    with _lock:
        u = _read()
        u["count"] = max(0, u["count"] - 1)
        config.USAGE_FILE.write_text(json.dumps(u))
