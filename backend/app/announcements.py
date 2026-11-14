"""Corporate-announcement fetcher: screener.in primary; NSE/BSE optional (skipped on 403). No LLM involved."""
from __future__ import annotations
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import httpx
from . import config

ANN_DIR = (config.DOCS_DIR.parent / "announcements")
PORTFOLIO_TS = config.BACKEND_DIR.parent / "src" / "data" / "portfolio.ts"
NSE_HOME = "https://www.nseindia.com"
NSE_API = NSE_HOME + "/api/corporate-announcements"
BSE_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
BSE_LOOKUP = "https://api.bseindia.com/BseIndiaAPI/api/fetchComp/w"
BSE_ATTACH = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"

BROWSER = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}


class FetchError(RuntimeError):
    pass


def load_portfolio() -> list[str]:
    text = PORTFOLIO_TS.read_text()
    tickers = re.findall(r"\bt:\s*'([A-Z0-9&\-]+)'", text)
    if not tickers:
        raise FetchError(f"no tickers parsed from {PORTFOLIO_TS}")
    return tickers


def _parse_dt(s: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


# ---------------------------------------------------------------- NSE
class NSEClient:
    def __init__(self) -> None:
        self.c = httpx.Client(headers={**BROWSER, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
                              timeout=config.REQUEST_TIMEOUT, follow_redirects=True)
        self._warm = False

    def _warmup(self) -> None:
        r = self.c.get(NSE_HOME + "/")
        if r.status_code != 200:
            raise FetchError(f"NSE homepage (cookie warm-up) returned HTTP {r.status_code}: {r.text[:200]!r}")
        self.c.get(NSE_HOME + "/companies-listing/corporate-filings-announcements")
        self._warm = True

    def fetch(self, ticker: str, start: datetime, end: datetime) -> list[dict]:
        if not self._warm:
            self._warmup()
        params = {"index": "equities", "symbol": ticker,
                  "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")}
        hdrs = {"Accept": "application/json, text/plain, */*",
                "Referer": NSE_HOME + "/companies-listing/corporate-filings-announcements",
                "X-Requested-With": "XMLHttpRequest"}
        r = self.c.get(NSE_API, params=params, headers=hdrs)
        if r.status_code in (401, 403):  # cookie may have expired: refresh once
            self._warmup()
            r = self.c.get(NSE_API, params=params, headers=hdrs)
        if r.status_code != 200:
            raise FetchError(f"NSE {r.status_code} for {r.url}: {r.text[:200]!r}")
        try:
            data = r.json()
        except ValueError:
            raise FetchError(f"NSE non-JSON response for {r.url}: {r.text[:200]!r}")
        if isinstance(data, dict):
            data = data.get("data", [])
        out = []
        for a in data:
            dt = _parse_dt(a.get("sort_date") or "") or _parse_dt(a.get("an_dt") or "")
            out.append({
                "ticker": ticker,
                "datetime": dt.isoformat() if dt else (a.get("an_dt") or ""),
                "subject": (a.get("desc") or "").strip(),
                "details": (a.get("attchmntText") or "").strip(),
                "category": (a.get("desc") or "").strip(),
                "attachment": a.get("attchmntFile") or None,
                "source": "NSE",
            })
        return out


# ---------------------------------------------------------------- BSE
class BSEClient:
    def __init__(self) -> None:
        self.c = httpx.Client(headers={**BROWSER, "Accept": "application/json, text/plain, */*",
                                       "Origin": "https://www.bseindia.com",
                                       "Referer": "https://www.bseindia.com/"},
                              timeout=config.REQUEST_TIMEOUT, follow_redirects=True)

    def _scrip(self, ticker: str) -> str:
        r = self.c.get(BSE_LOOKUP, params={"Group": "", "Scripcode": "", "Segment": "Equity", "flag": "0",
                                           "strSearch": ticker})
        if r.status_code != 200:
            raise FetchError(f"BSE scrip lookup {r.status_code} for {r.url}: {r.text[:200]!r}")
        m = re.search(r"liclass=\"quotemenu\"[^>]*>.*?<strong>(\d{6})", r.text, re.S) or re.search(r"\b(\d{6})\b", r.text)
        if not m:
            raise FetchError(f"BSE scrip lookup found no code for {ticker}: {r.text[:200]!r}")
        return m.group(1)

    def fetch(self, ticker: str, start: datetime, end: datetime) -> list[dict]:
        code = self._scrip(ticker)
        out: list[dict] = []
        page = 1
        while True:
            params = {"pageno": page, "strCat": "-1", "strPrevDate": start.strftime("%Y%m%d"),
                      "strScrip": code, "strSearch": "P", "strToDate": end.strftime("%Y%m%d"), "strType": "C"}
            r = self.c.get(BSE_API, params=params)
            if r.status_code != 200:
                raise FetchError(f"BSE {r.status_code} for {r.url}: {r.text[:200]!r}")
            try:
                data = r.json()
            except ValueError:
                raise FetchError(f"BSE non-JSON response for {r.url}: {r.text[:200]!r}")
            rows = data.get("Table") or []
            for a in rows:
                dt = _parse_dt((a.get("NEWS_DT") or a.get("DissemDT") or "").replace("T", " ").split(".")[0])
                att = a.get("ATTACHMENTNAME")
                out.append({
                    "ticker": ticker,
                    "datetime": dt.isoformat() if dt else (a.get("NEWS_DT") or ""),
                    "subject": (a.get("NEWSSUB") or a.get("HEADLINE") or "").strip(),
                    "details": (a.get("HEADLINE") or "").strip(),
                    "category": (a.get("CATEGORYNAME") or a.get("SUBCATNAME") or "").strip(),
                    "attachment": (BSE_ATTACH + att) if att else None,
                    "source": "BSE",
                })
            if len(rows) < 50:
                break
            page += 1
            time.sleep(config.REQUEST_DELAY)
        return out


# ---------------------------------------------------------------- cache / orchestration
def _key(a: dict) -> str:
    return "|".join([a["ticker"], a["datetime"], a["subject"], a.get("attachment") or ""])


def snapshot_path(ticker: str) -> Path:
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    return ANN_DIR / f"{ticker}.json"


def load_snapshot(ticker: str) -> dict:
    p = snapshot_path(ticker)
    if p.exists():
        return json.loads(p.read_text())
    return {"ticker": ticker, "fetched_through": None, "announcements": []}


def parse_screener(html: str, ticker: str) -> list[dict]:
    """Recent-announcements box on a screener.in company page (anonymous view shows only the latest 5)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    h = soup.find("h3", string=re.compile(r"^\s*Announcements\s*$"))
    box = h.find_next("ul", class_="list-links") if h else None
    out = []
    for a in (box.select("li > a[href]") if box else []):
        t = a.find("time")
        dt = None
        if t and t.get("datetime"):
            try:
                dt = datetime.fromisoformat(t["datetime"]).replace(tzinfo=None)
            except ValueError:
                dt = None
        sub = a.find(["div", "span"], class_=re.compile("ink-600"))
        details = ""
        if sub:
            details = sub.get_text(" ", strip=True)
            details = details.split(" - ", 1)[1] if " - " in details else ""
        headline = next((s.strip() for s in a.stripped_strings), "")
        out.append({"ticker": ticker, "datetime": dt.isoformat() if dt else "", "subject": headline,
                    "details": details, "category": "", "attachment": a["href"].strip(), "source": "screener.in"})
    return out


def fetch_screener(ticker: str) -> list[dict]:
    from . import screener
    try:
        html, _ = screener.fetch_page(ticker)
    except screener.ScreenerError as e:
        raise FetchError(f"screener.in: {e}")
    return parse_screener(html, ticker)


class Exchanges:
    """Optional NSE/BSE source. Disabled for the rest of the run after the first HTTP 403."""
    def __init__(self, enabled: bool) -> None:
        self.enabled, self.skip_reason = enabled, None
        self.nse, self.bse = (NSEClient(), BSEClient()) if enabled else (None, None)

    def fetch(self, ticker: str, start: datetime, end: datetime) -> list[dict]:
        if not self.enabled or self.skip_reason:
            return []
        errs = []
        for cl in (self.nse, self.bse):
            try:
                return cl.fetch(ticker, start, end)
            except FetchError as e:
                errs.append(str(e)[:120])
        self.skip_reason = "exchanges skipped (403/blocked): " + " | ".join(errs)
        return []


def fetch_ticker(ticker: str, ex: Exchanges, days: int = 30) -> dict:
    now = datetime.now()
    snap = load_snapshot(ticker)
    window_start = now - timedelta(days=days)
    rows = fetch_screener(ticker)
    rows += ex.fetch(ticker, window_start, now)
    known = {_key(a) for a in snap["announcements"]}
    new, seen = [], set(known)
    for a in rows:
        if a["datetime"] and a["datetime"] >= window_start.isoformat() and _key(a) not in seen:
            seen.add(_key(a)); new.append(a)
    cutoff = window_start.isoformat()
    merged = [a for a in snap["announcements"] + new if a["datetime"] >= cutoff]
    merged.sort(key=lambda a: a["datetime"], reverse=True)
    snap.update(ticker=ticker, fetched_through=now.isoformat(timespec="seconds"), announcements=merged)
    p = snapshot_path(ticker)
    tmp = p.with_suffix(".part")
    tmp.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    tmp.rename(p)
    return {"new": len(new), "total": len(merged),
            "span_days": ((now - datetime.fromisoformat(merged[-1]["datetime"])).days if merged else 0)}


def write_combined(tickers: list[str]) -> list[dict]:
    allr: list[dict] = []
    for t in tickers:
        allr += load_snapshot(t)["announcements"]
    allr.sort(key=lambda a: a["datetime"], reverse=True)
    (ANN_DIR / "all.json").write_text(json.dumps(
        {"generated_at": datetime.now().isoformat(timespec="seconds"), "count": len(allr), "announcements": allr},
        indent=2, ensure_ascii=False))
    return allr
