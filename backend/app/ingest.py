from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
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


def ingest(ticker: str) -> IngestReport:
    rep = IngestReport(ticker=ticker.upper())
    try:
        html, rep.page_url = screener.fetch_page(ticker)
    except screener.ScreenerError as e:
        rep.errors.append(f"screener.in fetch failed: {e}")
        return rep
    annual, concalls = screener.parse_docs(html)
    if not annual:
        rep.errors.append("no annual report link found on page")
    if len(concalls) < 4:
        rep.errors.append(f"only {len(concalls)} concall transcript link(s) found (wanted 4)")
    for ref in ([annual] if annual else []) + concalls:
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
