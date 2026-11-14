"""Find the latest annual report + last N concall transcripts on a screener.in company page."""
from __future__ import annotations
import re
import time
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup
from . import config

BASE = "https://www.screener.in/company/{ticker}/{variant}"


class ScreenerError(Exception):
    """Raised with the exact HTTP status / network error so callers can report it verbatim."""


@dataclass
class DocRef:
    kind: str          # "annual_report" | "concall"
    label: str         # e.g. "Annual Report 2026", "Oct 2026"
    url: str
    source: str = ""   # e.g. "bse"


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": config.USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                        timeout=config.REQUEST_TIMEOUT, follow_redirects=True)


def fetch_page(ticker: str) -> tuple[str, str]:
    """Return (html, url_used). Tries consolidated, then standalone."""
    errors = []
    with _client() as c:
        for variant in ("consolidated/", ""):
            url = BASE.format(ticker=ticker.upper(), variant=variant)
            try:
                r = c.get(url)
            except httpx.HTTPError as e:
                errors.append(f"{url} -> {type(e).__name__}: {e}")
                continue
            if r.status_code == 200 and "list-links" in r.text:
                return r.text, url
            errors.append(f"{url} -> HTTP {r.status_code}" + (" (page has no documents section)" if r.status_code == 200 else ""))
            time.sleep(config.REQUEST_DELAY)
    raise ScreenerError("; ".join(errors))


def parse_docs(html: str, n_concalls: int | None = None) -> tuple[DocRef | None, list[DocRef]]:
    n = n_concalls or config.CONCALL_COUNT
    soup = BeautifulSoup(html, "html.parser")

    annual: DocRef | None = None
    h = soup.find("h3", string=re.compile(r"Annual reports", re.I))
    if h:
        box = h.find_next("ul", class_="list-links")
        for a in box.select("li > a[href]") if box else []:
            href = a["href"].strip()
            if href.lower().split("#")[0].endswith(".pdf") or "AnnualReport" in href:
                src = a.find_next("span", class_="ink-600")
                annual = DocRef("annual_report", a.get_text(strip=True), href.split("#")[0],
                                src.get_text(strip=True).replace("from ", "") if src else "")
                break  # list is newest-first

    concalls: list[DocRef] = []
    h = soup.find("h3", string=re.compile(r"Concalls", re.I))
    if h:
        box = h.find_next("ul", class_="list-links")
        for li in box.find_all("li", recursive=False) if box else []:
            date = li.find("div", class_=re.compile("ink-600"))
            t = li.find("a", title=re.compile("transcript", re.I)) or li.find("a", string=re.compile("Transcript", re.I))
            if t and t.get("href"):
                concalls.append(DocRef("concall", date.get_text(strip=True) if date else "?", t["href"].strip()))
            if len(concalls) >= n:
                break
    return annual, concalls
