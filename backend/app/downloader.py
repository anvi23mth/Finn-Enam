from __future__ import annotations
import re
import time
from pathlib import Path
import httpx
from . import config
from .screener import DocRef


def ticker_dir(ticker: str) -> Path:
    d = config.DOCS_DIR / ticker.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def filename(ref: DocRef) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ref.label).strip("-").lower()
    return f"{ref.kind}__{slug}.pdf"


def download(ticker: str, ref: DocRef) -> tuple[Path, str]:
    """Returns (path, status) where status is 'cached' or 'downloaded'. Raises on failure."""
    path = ticker_dir(ticker) / filename(ref)
    if path.exists() and path.stat().st_size > 1024:
        return path, "cached"
    headers = {"User-Agent": config.USER_AGENT, "Referer": "https://www.screener.in/",
               "Accept": "application/pdf,*/*"}
    with httpx.Client(headers=headers, timeout=config.REQUEST_TIMEOUT, follow_redirects=True) as c:
        r = c.get(ref.url)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from {r.url}")
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"not a PDF (content-type={r.headers.get('content-type')}, first bytes={r.content[:40]!r}) from {r.url}")
    tmp = path.with_suffix(".part")
    tmp.write_bytes(r.content)
    tmp.rename(path)
    time.sleep(config.REQUEST_DELAY)
    return path, "downloaded"
