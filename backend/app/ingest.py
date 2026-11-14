from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup
from . import screener, downloader, extract


@dataclass
class DocResult:
    kind: str
    label: str
    url: str
    pdf: str | None = None
    json: str | None = None
    pages: int | None = None
    empty_pages: int | None = None
    download_status: str | None = None
    extract_status: str | None = None
    error: str | None = None


@dataclass
class IngestReport:
    ticker: str
    page_url: str | None = None
    docs: list[DocResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    company: str | None = None


def ingest(ticker: str, progress=None) -> IngestReport:
    say = progress or (lambda m: None)
    rep = IngestReport(ticker=ticker.upper())
    say("looking up documents on screener.in")
    try:
        html, rep.page_url = screener.fetch_page(ticker)
    except screener.ScreenerError as e:
        rep.errors.append(f"screener.in fetch failed: {e}")
        return rep
    annual, concalls = screener.parse_docs(html)
    h1 = BeautifulSoup(html, "html.parser").find("h1")
    rep.company = h1.get_text(strip=True) if h1 else None
    if not annual:
        rep.errors.append("no annual report link found on page")
    if len(concalls) < 4:
        rep.errors.append(f"only {len(concalls)} concall transcript link(s) found (wanted 4)")
    refs = ([annual] if annual else []) + concalls
    for i, ref in enumerate(refs, 1):
        say(f"downloading and reading documents ({i} of {len(refs)})")
        r = DocResult(kind=ref.kind, label=ref.label, url=ref.url)
        rep.docs.append(r)
        try:
            path, r.download_status = downloader.download(ticker, ref)
            r.pdf = path.name
            jpath, r.pages, r.extract_status = extract.extract_pdf(path)
            r.json = jpath.name
            data = json.loads(jpath.read_text())
            r.empty_pages = sum(1 for p in data["pages"] if not p["text"].strip())
        except Exception as e:
            r.error = f"{type(e).__name__}: {e}"
    return rep
