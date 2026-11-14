"""Announcement intelligence: batch classification + results-table extraction.
Uses the cheap model from .env via the existing LLM wrapper (cache, throttling, retry, fallback chain).
Calls are strictly sequential."""
from __future__ import annotations
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
import httpx
import pdfplumber
from . import config, llm
from .log import log
from .verify import verify_cite, values_in_quote

ANN_DIR = config.DOCS_DIR.parent / "announcements"
RESULTS_DIR = config.DOCS_DIR.parent / "results"
PUBLIC = config.BACKEND_DIR.parent / "public"
CLASSIFY_V, RESULTS_V = "ann-cls-v3", "ann-res-v1"
BATCH = 25

# Categories + definitions from the challenge reference PDF ("Announcement Categories & Financial Glossary").
CATEGORIES = {
    "results": "Quarterly/annual results, the board meeting approving them, results decks and shareholder letters, and ads confirming results were published.",
    "M&A": "Any acquisition, merger, demerger, or joint venture — including investing in a subsidiary, or selling a stake in one.",
    "fund_raise": "Raising money from outside investors — rights issues, QIPs, preferential allotments, buybacks, or debt like commercial paper.",
    "management_change": "Any change at the top — a CEO, CFO, MD, or director joining, resigning, or retiring.",
    "litigation": "Lawsuits, regulatory orders, fines, warnings, or insolvency/restructuring proceedings.",
    "insider_trading": "A promoter or insider buying/selling their own personal shareholding.",
    "earnings_call": "Anything about the investor conference call — the notice, the transcript, or the recording link.",
    "investor_meetings": "One-on-one or small-group meetings with specific investors/funds, or attending an investor conference.",
    "credit_rating": "A rating agency assigning, upgrading, downgrading, or reaffirming a credit rating.",
    "dividend": "A cash dividend being declared, with its record date.",
    "bonus_split": "A bonus issue or stock split — share count changes but no cash comes to you.",
    "capex": "Approving spend on a new plant, facility, or capacity expansion.",
    "press_release": "General news — order wins, new products, partnerships, rumour clarifications — not covered by another category.",
    "postal_ballot": "Shareholders voting by postal ballot — the notice and the result.",
    "agm_egm": "Annual or Extraordinary General Meeting — the notice and the result.",
    "pledging": "A promoter pledging, releasing, or changing the pledge status of shares.",
    "unclassified": "Routine, low-relevance paperwork — ESOP allotments, compliance certificates, ESG reports, auditor appointments — that doesn't materially move the stock.",
}
PRIORITIES = ("high", "medium", "low")
SYSTEM_CLS = f"""You classify Indian stock-exchange corporate announcements for an equity investor.
Categories (use EXACTLY these keys):
{chr(10).join(f'- {k}: {v}' for k, v in CATEGORIES.items())}

Priority:
- high: likely to move the stock or change the thesis — results, M&A, fund_raise beyond routine commercial paper, management_change at CEO/CFO/MD level, litigation/regulatory action, pledging, large capex, insider selling.
- medium: informative but rarely thesis-changing — earnings_call, investor_meetings tied to results, credit_rating, dividend, bonus_split, press_release with substance (orders, launches), director changes, routine commercial-paper or debt repayment.
- low: routine paperwork — ESOP allotments, compliance certificates, newspaper publications, AGM/postal-ballot procedure, trading-window notices.
Category rules:
- Classify by what the HEADLINE (subject) is about. Use the detail line only to disambiguate; never let an incidental mention in the detail line override the headline (e.g. an "Analyst / Investor Meet - Outcome" filing that merely mentions a transcript or a capital raise is earnings_call/investor_meetings, not fund_raise).
- "Analyst / Investor Meet" filings: earnings_call if it is the results call (notice, transcript, audio recording); investor_meetings if it is meetings with investors or an investor conference.
- management_change means someone NEW joining, or someone leaving, resigning or retiring at CEO/CFO/MD/director level. The REAPPOINTMENT of an existing director or executive for a further term (including regulator approval of a reappointment) is NOT a management change: classify it unclassified with priority low.
- A newspaper publication/advertisement of results is category results (the reference lists ads confirming results) but priority low: it duplicates a results filing already made.
- fund_raise needs the filing itself to be about raising money; a mention of one inside another filing does not count.
Rules: judge from the headline and the one-line detail only; do not invent facts. For high and medium items write a one-line "summary" (max 25 words) that states what happened using only the given text; for low items set "summary" to null.
Return JSON: {{"items": [{{"id": str, "category": str, "priority": "high"|"medium"|"low", "summary": str|null}}]}} — one entry per input id, no extras."""


def item_id(a: dict) -> str:
    return hashlib.sha1(f"{a['ticker']}|{a['datetime']}|{a['subject']}".encode()).hexdigest()[:10]


def models_chain() -> list:
    """Cheap model first; the existing fallbacks only if it keeps failing (e.g. persistent 503s)."""
    out = []
    for m in [config.CHEAP_MODEL, *config.STRONG_MODEL_FALLBACKS]:
        if m not in out:
            out.append(m)
    return out


def _classify_batch(batch: list[dict], usage: llm.Usage) -> tuple[dict, str]:
    lines = [{"id": a["id"], "ticker": a["ticker"], "date": a["datetime"][:10], "headline": a["subject"], "detail": a.get("details") or ""} for a in batch]
    prompt = "Classify these announcements:\n" + json.dumps(lines, ensure_ascii=False)
    res, used = llm.call_chain(models=models_chain(), system=SYSTEM_CLS, prompt=prompt, version=CLASSIFY_V,
                               doc_hash="announcements", part=f"cls-{batch[0]['id']}-{len(batch)}", stage="classify", usage=usage)
    out = {}
    for r in (res.get("items") if isinstance(res, dict) else res) or []:
        if isinstance(r, dict) and r.get("id") in {a["id"] for a in batch}:
            out[r["id"]] = r
    return out, used


def classify_all(force: bool = False) -> dict:
    src = json.loads((ANN_DIR / "all.json").read_text())["announcements"]
    for a in src:
        a["id"] = item_id(a)
    path = ANN_DIR / "classified.json"
    prev = {} if force or not path.exists() else {x["id"]: x for x in json.loads(path.read_text())["items"]}
    todo = [a for a in src if a["id"] not in prev]
    log(f"classify: {len(src)} announcements, {len(prev)} already classified, {len(todo)} to do")
    usage, used_models, problems = llm.Usage(), Counter(), []
    done = dict(prev)
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        got, used = _classify_batch(batch, usage)
        missing = [a for a in batch if a["id"] not in got]
        if missing:                         # one retry of just the missing ids
            got2, used = _classify_batch(missing, usage)
            got.update(got2)
        for a in batch:
            r = got.get(a["id"])
            cat = (r or {}).get("category")
            pri = (r or {}).get("priority")
            ok = cat in CATEGORIES and pri in PRIORITIES
            if not ok:
                problems.append({"id": a["id"], "ticker": a["ticker"], "subject": a["subject"], "got": r})
            summary = (r or {}).get("summary") if ok and pri in ("high", "medium") else None
            done[a["id"]] = {**a, "category": cat if ok else "unclassified", "priority": pri if ok else "low",
                             "summary": (summary or None), "classified_by": used if ok else None, "classified_ok": ok}
            used_models[used] += 1
    items = sorted(done.values(), key=lambda x: x["datetime"], reverse=True)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "count": len(items),
           "models": {**{m: n for m, n in used_models.items()}}, "unvalidated": problems,
           "counts": {"category": dict(Counter(x["category"] for x in items)), "priority": dict(Counter(x["priority"] for x in items))},
           "items": items}
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    pub = PUBLIC / "announcements"
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "classified.json").write_text(path.read_text())
    return out


# ------------------------------------------------------------------ results extraction
PERIODS = ["current_quarter", "previous_quarter", "year_ago_quarter"]
SYSTEM_RES = """You extract headline financials from a company's quarterly results filing (text of each page is given, tagged [PAGE n]).
Find the table of financial results with quarterly columns. Use the CONSOLIDATED statement if present, otherwise standalone; say which in "basis".
Return JSON:
{"basis": "consolidated"|"standalone"|"unknown", "unit": str (exactly as stated, e.g. "₹ in crore" or "Rs. million"),
 "quarter_labels": {"current_quarter": str, "previous_quarter": str, "year_ago_quarter": str},   // e.g. "Quarter ended 30 Sep 2026"
 "metrics": {
   "revenue": {...}, "pbt": {...}, "pat": {...}, "ebitda": {...}, "finance_costs": {...}, "depreciation": {...}, "other_income": {...}}}
Each metric is an object with the three keys current_quarter / previous_quarter / year_ago_quarter, each either null (not found) or
{"value": number (as printed, in the stated unit, negative for losses), "page": int, "quote": str (the printed table row, copied verbatim from that page, containing the number)},
plus "label": the row label you used.
revenue = "Revenue from operations" (total income only if that row does not exist). pbt = "Profit/(loss) before tax" (before exceptional items only if no PBT row). pat = "Profit/(loss) for the period" (total, before the split between owners and minority interest).
ebitda: ONLY if the filing states EBITDA explicitly; otherwise all three null. finance_costs / depreciation (and amortisation) / other_income: the printed rows, used to derive EBITDA when it is not stated.
Never guess or compute values yourself; copy numbers exactly. If a number is not on the pages, use null."""
UNIT_TO_CRORE = [(r"crore|cr\b", 1.0), (r"million|mn\b", 0.1), (r"lakh|lac", 0.01), (r"billion|bn\b", 100.0)]


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1024:
        return
    hdr = {"User-Agent": config.USER_AGENT, "Referer": "https://www.bseindia.com/", "Accept": "application/pdf,*/*"}
    with httpx.Client(headers=hdr, timeout=config.REQUEST_TIMEOUT, follow_redirects=True) as c:
        r = c.get(url)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} downloading {url}")
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"not a PDF ({r.headers.get('content-type')}): {r.content[:60]!r} from {r.url}")
    dest.write_bytes(r.content)


def _pages(pdf_path: Path) -> dict[int, str]:
    with pdfplumber.open(pdf_path) as pdf:
        return {i + 1: (p.extract_text() or "") for i, p in enumerate(pdf.pages)}


def _to_crore(unit: str, v: float) -> float | None:
    for pat, f in UNIT_TO_CRORE:
        if re.search(pat, unit or "", re.I):
            return round(v * f, 2)
    return None


def extract_results(ticker: str, filing: dict, usage: llm.Usage) -> dict:
    """Download one results filing and extract the metrics with page+quote verification."""
    t = ticker.upper()
    pdf = RESULTS_DIR / "pdfs" / t / f"{filing['id']}.pdf"
    out: dict = {"ticker": t, "filing": {k: filing.get(k) for k in ("id", "datetime", "subject", "attachment", "category")}, "status": "ok"}
    try:
        _download(filing["attachment"], pdf)
        pages = _pages(pdf)
    except Exception as e:
        return {**out, "status": "failed", "error": f"{type(e).__name__}: {e}"}
    out["pages"] = len(pages)
    texty = [n for n, x in pages.items() if len(x) > 300]
    if len(texty) < 2:
        return {**out, "status": "not_found", "error": f"PDF is a scanned image: only {len(texty)} of {len(pages)} pages have a text layer; OCR was not attempted"}
    # pick the pages that hold the results tables / summaries (standalone AND consolidated), not just the first pages
    hits = [re.compile(x, re.I) for x in (r"revenue from operations|total income", r"ebitda", r"before (exceptional|tax)", r"profit after tax|profit/\(loss\) for the (period|quarter)", r"finance costs?", r"depreciation", r"quarter ended|3 months ended|three months ended", r"consolidated")]
    score = {n: sum(bool(h.search(pages[n])) for h in hits) for n in pages}
    ranked = sorted((n for n in pages if score[n] >= 4), key=lambda n: (-score[n], n))
    chosen = sorted(ranked[:8]) if ranked else sorted(pages)[:8]
    out["pages_sent"] = chosen
    body = "\n\n".join(f"[PAGE {n}]\n{pages[n][:6000]}" for n in chosen)
    res, used = llm.call_chain(models=models_chain(), system=SYSTEM_RES, prompt=body, version=RESULTS_V,
                               doc_hash=hashlib.sha1(pdf.read_bytes()).hexdigest()[:16], part="results", stage="results", usage=usage)
    out["model"] = used
    unit = res.get("unit") or ""
    out.update(basis=res.get("basis", "unknown"), unit=unit, quarter_labels=res.get("quarter_labels") or {})
    metrics: dict = {}
    for name, row in (res.get("metrics") or {}).items():
        cells = {}
        for per in PERIODS:
            c = (row or {}).get(per)
            if not c or c.get("value") is None:
                cells[per] = None
                continue
            status, page, score = verify_cite(c.get("quote", ""), int(c.get("page") or 0), pages)
            val_ok = values_in_quote([abs(float(c["value"]))], c.get("quote", ""))
            ok = status != "failed" and val_ok
            cells[per] = {"value": float(c["value"]), "value_crore": _to_crore(unit, float(c["value"])), "page": page if ok else c.get("page"),
                          "quote": c.get("quote"), "verified": ok, "verify_status": status if val_ok else f"{status}+value_not_in_quote"}
        metrics[name] = {"label": (row or {}).get("label"), **cells}
    # derive EBITDA from verified components when the filing does not state it
    e = metrics.get("ebitda") or {}
    if not any((e.get(p) or {}).get("verified") for p in PERIODS):
        d: dict = {"label": "EBITDA (derived: PBT + finance costs + depreciation − other income; exceptional items not adjusted)", "derived": True}
        for per in PERIODS:
            comp = [(metrics.get(k) or {}).get(per) for k in ("pbt", "finance_costs", "depreciation", "other_income")]
            if all(c and c["verified"] for c in comp):
                v = comp[0]["value"] + comp[1]["value"] + comp[2]["value"] - comp[3]["value"]
                d[per] = {"value": round(v, 2), "value_crore": _to_crore(unit, v), "verified": True, "derived": True,
                          "from": {"pbt": comp[0]["value"], "finance_costs": comp[1]["value"], "depreciation": comp[2]["value"], "other_income": comp[3]["value"]}}
            else:
                d[per] = None
        metrics["ebitda"] = d
    out["metrics"] = metrics
    table = {}
    for k in ("revenue", "ebitda", "pbt", "pat"):
        m = metrics.get(k) or {}
        cur, prev, yoy = (m.get(p) for p in PERIODS)
        g = lambda a, b: round((a["value"] / b["value"] - 1) * 100, 1) if a and b and a.get("verified") and b.get("verified") and b["value"] > 0 else None
        table[k] = {"current": cur and cur.get("value_crore"), "previous": prev and prev.get("value_crore"), "year_ago": yoy and yoy.get("value_crore"),
                    "qoq_pct": g(cur, prev), "yoy_pct": g(cur, yoy),
                    "verified": all(c and c.get("verified") for c in (cur, prev, yoy)), "derived": bool(m.get("derived"))}
    out["table_crore"] = table
    flags = []
    for k, v in table.items():
        for lab, g in (("QoQ", v["qoq_pct"]), ("YoY", v["yoy_pct"])):
            if g is not None and abs(g) >= 300:
                flags.append(f"{k} {lab} change of {g}% is unusually large — check for discontinued operations or one-offs in the filing before relying on it")
    if table["ebitda"]["derived"] and table["ebitda"]["current"] is not None:
        flags.append("EBITDA is derived from PBT (after any exceptional items), not stated by the company — treat as indicative")
    if out.get("basis") != "consolidated":
        flags.append(f"basis is {out.get('basis')}: the consolidated statement was not used")
    out["flags"] = flags
    missing = [f"{k}/{p}" for k in ("revenue", "ebitda", "pbt", "pat") for p in PERIODS if not (metrics.get(k) or {}).get(p) or not (metrics[k][p] or {}).get("verified")]
    if missing:
        out["status"] = "partial" if len(missing) < 12 else "not_found"
        out["not_found_or_unverified"] = missing
    return out


def run_results(tickers: list[str], classified: dict) -> list[dict]:
    usage, outs = llm.Usage(), []
    for t in tickers:
        # newest results filing that has a PDF and looks like the results themselves (not just a deck / notice)
        cands = [x for x in classified["items"] if x["ticker"] == t and x["category"] == "results" and x.get("attachment")]
        pref = [x for x in cands if re.search(r"financial result|outcome of board|board meeting outcome|unaudited|audited", x["subject"], re.I)] or cands
        if not pref:
            outs.append({"ticker": t, "status": "not_found", "error": "no results filing in the announcements feed"}); continue
        res = None
        for filing in pref[:3]:             # if one filing is only a cover letter, try the next
            res = extract_results(t, filing, usage)
            if res["status"] in ("ok", "partial"):
                break
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / f"{t}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        pub = PUBLIC / "results"
        pub.mkdir(parents=True, exist_ok=True)
        (pub / f"{t}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        outs.append(res)
    return outs
