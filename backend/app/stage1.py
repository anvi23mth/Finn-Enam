"""Stage 1 (cheap model): per-document, chunked extraction of quote-backed facts."""
from __future__ import annotations
from collections import Counter
from . import config, llm
from .log import log
from .docs import Doc, chunk_pages, render, select_ar_pages
from .verify import verify_cite

V_CONCALL = "concall-v1"
V_AR = "ar-v1"

SYS = ("You extract facts from ONE company document for an investment analyst. Use ONLY the text given. "
       "Never use outside knowledge. Every item needs a verbatim quote copied exactly from the page text "
       "(under 25 words, no paraphrase, no ellipses) and the page number from the <<<PAGE n>>> marker it appears under. "
       "If nothing relevant is on these pages return empty lists. Output JSON only.")

CONCALL_PROMPT = """Document: earnings-call transcript (file label: "{label}"). Pages below.
Ignore front matter: attendee/participant lists, safe-harbour disclaimers, operator instructions, moderator intros.
Return JSON: {{"fiscal_quarter": "<e.g. Q2 FY27 if you can tell from the text, else null>",
 "items": [{{"type": "guidance"|"number"|"analyst_question",
   "topic": "growth"|"margin"|"capex"|"demand"|"other",
   "text": "<one-line restatement; for guidance include metric, target/direction and time horizon>",
   "quote": "<verbatim, <25 words>", "page": <int>}}]}}
- guidance: ONLY explicit forward-looking management statements on growth, margins, capex or demand (a target, range, expectation or direction).
- number: headline figures management states for the quarter/year (revenue, growth %, margin %, deal wins, headcount, capex).
- analyst_question: the main topics analysts pressed management on (one item per distinct question).
PAGES:
{pages}"""

AR_PROMPT = """Document: annual report. Selected pages below (not the whole report).
Return JSON: {{"items": [{{"topic": "business"|"segments"|"multiyear"|"debt"|"working_capital"|"cash_flow"|"contingent"|"auditor",
 "text": "<one-line fact; for numbers include the metric, period and value with units>",
 "quote": "<verbatim, <25 words, ideally containing the number>", "page": <int>}}]}}
Targets: business description; segment and revenue mix; multi-year Revenue, EBITDA, PAT and margins; debt/borrowings; working-capital days
(receivable/inventory/payable); cash from operations and capex; contingent liabilities; auditor remarks (qualifications, emphasis of matter, key audit matters).
Prefer rows with numbers. Do not guess missing values.
PAGES:
{pages}"""


def _verify_items(items: list, doc: Doc) -> tuple[list, list]:
    ok, bad = [], []
    for it in items:
        try:
            page = int(it.get("page"))
        except (TypeError, ValueError):
            bad.append({**it, "reason": "bad page"}); continue
        status, found, score = verify_cite(str(it.get("quote", "")), page, doc.pages)
        if status == "failed":
            bad.append({**it, "doc": doc.id, "reason": f"quote not found on p{page} (best match {score:.2f})"})
        else:
            ok.append({**it, "doc": doc.id, "page": found, "verified": status})
    return ok, bad


def run_concall(doc: Doc, usage: llm.Usage) -> dict:
    items, bad, quarters = [], [], []
    log(f"stage 1 · {doc.id}: {len(doc.pages)} pages")
    for i, nums in enumerate(chunk_pages(doc.pages, config.CHUNK_PAGES)):
        res = llm.call_json(model=config.CHEAP_MODEL, system=SYS, version=V_CONCALL, doc_hash=doc.sha, part=f"c{i}",
                            stage="stage1_concall", usage=usage,
                            prompt=CONCALL_PROMPT.format(label=doc.label, pages=render(doc.pages, nums)))
        if res.get("fiscal_quarter"):
            quarters.append(str(res["fiscal_quarter"]).strip())
        ok, b = _verify_items(res.get("items", []), doc)
        items += ok; bad += b
    q = Counter(quarters).most_common(1)[0][0] if quarters else "unknown"
    return {"doc": doc.id, "kind": "concall", "label": doc.label, "quarter": q, "items": items, "dropped": bad}


def run_ar(doc: Doc, usage: llm.Usage) -> dict:
    sel = select_ar_pages(doc.pages, config.AR_MAX_PAGES)
    log(f"stage 1 · {doc.id}: sending {len(sel)} of {len(doc.pages)} pages")
    sub = {p: doc.pages[p] for p in sel}
    items, bad = [], []
    for i, nums in enumerate(chunk_pages(sub, config.CHUNK_PAGES)):
        res = llm.call_json(model=config.CHEAP_MODEL, system=SYS, version=V_AR, doc_hash=doc.sha, part=f"a{i}",
                            stage="stage1_annual_report", usage=usage, prompt=AR_PROMPT.format(pages=render(sub, nums)))
        ok, b = _verify_items(res.get("items", []), doc)
        items += ok; bad += b
    return {"doc": doc.id, "kind": "annual_report", "label": doc.label, "pages_sent": len(sel), "items": items, "dropped": bad}
