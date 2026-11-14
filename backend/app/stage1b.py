"""Stage 1b (cheap model, compact input): turn verified Stage-1 items into structured facts with scope + period + value.
Operates on already-verified items (not PDFs), so it is a handful of small calls. Code then re-checks every number."""
from __future__ import annotations
import re
from . import config, llm
from .log import log
from .periods import norm_period
from .ar_lines import cashflow_facts
from .ledger_units import unit_class
from .verify import numbers, values_in_quote

V = "struct-v1"
METRICS = ("revenue, revenue_growth_yoy, revenue_growth_cc, ebitda, ebitda_margin, ebit, operating_margin, pbt, pat, eps, "
           "borrowings, net_debt, debt_equity, cfo, capex, fcf, working_capital, receivable_days, inventory_days, tax_rate, "
           "large_deal_tcv, headcount, other")

SYS = ("You convert extracted facts into structured records. Use ONLY the given quote/text; never use outside knowledge. "
       "Numbers must be copied exactly as they appear in the quote (no unit conversion, no rounding); percentages as plain numbers (21 not 0.21). "
       "If something is not stated, use null. Output JSON only.")

PROMPT = """Each line: id | type/topic | page | restatement | "quote" [| page_header: first words of the page, to tell standalone from consolidated]
Return {{"facts":[...]}} with one record per id, in one of two shapes:
GUIDANCE (type=guidance): {{"id":str,"kind":"guidance","metric":<one of: {metrics}>,"low":num|null,"high":num|null,"unit":"%"|"INR crore"|"USD million"|"USD billion"|"days"|"x"|null,
  "direction":"up_qoq"|"up_yoy"|"down_qoq"|"down_yoy"|"flat"|null,"covers_period":<period the guidance is ABOUT, e.g. "FY27","Q4 FY26","H2 FY27">|null,"scope":"consolidated"|"standalone"|"unspecified"}}
  - range -> low/high; single target -> low=high; purely directional ("better than last quarter") -> direction only; qualitative/no number/direction -> metric "other".
ACTUAL (everything else): {{"id":str,"kind":"actual","metric":<one of: {metrics}>,"value":num|null,"unit":str|null,
  "scope":"consolidated"|"standalone"|"segment"|"unspecified","period":<period the number is FOR: "FY26","Q2 FY27","as of 31 Mar 2026">|null}}
  - scope: consolidated/standalone ONLY if the quote or the page header says so; otherwise "unspecified". Never guess.
  - one value per record: the main figure of the quote.
LINES:
{lines}"""

ANNUAL_METRICS = {"revenue_growth_yoy", "revenue_growth_cc", "operating_margin", "ebitda_margin", "tax_rate", "capex", "revenue", "ebitda", "pat"}
ELIGIBLE_AR = {"segments", "multiyear", "debt", "working_capital", "cash_flow", "contingent"}


def _lines(items: list, doc) -> str:
    out = []
    for it in items:
        head = ""
        if doc.kind == "annual_report":
            head = " | page_header: " + re.sub(r"\s+", " ", doc.pages.get(it["page"], "")[:300])
        out.append(f'{it["fid"]} | {it.get("type") or ""}/{it.get("topic", "")} | p{it["page"]} | {it.get("text", "")} | "{it.get("quote", "")}"{head}')
    return "\n".join(out)


def _page_scope(doc, page: int) -> str | None:
    t = doc.pages.get(page, "")[:700].lower()
    c, s = "consolidated" in t, "standalone" in t
    return "consolidated" if c and not s else "standalone" if s and not c else None


def run(docs_by_id: dict, s1: list, usage: llm.Usage) -> list:
    """Returns the flat list of facts (every Stage-1 item), structured where possible. Each fact has a stable id F<n>."""
    facts, n = [], 0
    for d in s1:
        doc = docs_by_id[d["doc"]]
        items = []
        for it in d["items"]:
            n += 1
            f = {**it, "fid": f"F{n}", "doc": d["doc"], "doc_kind": d["kind"], "quarter": d.get("quarter"),
                 "kind": "guidance" if it.get("type") == "guidance" else "text", "metric": None, "scope": None, "period": None}
            facts.append(f)
            structurable = (d["kind"] == "concall" and it.get("type") in ("guidance", "number")) or \
                           (d["kind"] == "annual_report" and it.get("topic") in ELIGIBLE_AR)
            if structurable:
                items.append(f)
        for i in range(0, len(items), 40):
            chunk = items[i:i + 40]
            res = llm.call_json(model=config.CHEAP_MODEL, system=SYS, version=V, doc_hash=doc.sha, part=f"s{i // 40}",
                                stage="stage1b_structure", usage=usage,
                                prompt=PROMPT.format(metrics=METRICS, lines=_lines(chunk, doc)))
            recs = res.get("facts") if isinstance(res, dict) else res
            by = {str(r.get("id")): r for r in (recs or []) if isinstance(r, dict)}
            for f in chunk:
                r = by.get(f["fid"])
                if r:
                    _apply(f, r, doc)
    for d in s1:
        extra = cashflow_facts(docs_by_id[d["doc"]], len(facts))
        facts += extra
        if extra:
            log(f"stage 1b: +{len(extra)} deterministic table-row facts from {d['doc']} (" + ", ".join(f"{e['metric']} {e['scope']} {e['period']}={e['value']:g} p{e['page']}" for e in extra) + ")")
    log(f"stage 1b: {sum(1 for f in facts if f['metric'] and f['metric'] != 'other')} structured of {len(facts)} facts")
    return facts


def _num(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _apply(f: dict, r: dict, doc) -> None:
    metric = str(r.get("metric") or "other").strip().lower()
    f["metric"], f["unit"] = metric, r.get("unit")
    quote = f.get("quote", "")
    flags = []
    scope = str(r.get("scope") or "unspecified").lower()
    hint = _page_scope(doc, f["page"]) if doc.kind == "annual_report" else None
    if scope in ("consolidated", "standalone") and hint and hint != scope:
        flags.append(f"scope tag '{scope}' contradicts page header ('{hint}'); using page header")
        scope = hint
    if scope == "unspecified" and hint:
        scope = hint
    if doc.kind == "concall" and scope == "unspecified":
        scope = "consolidated" if "standalone" not in quote.lower() else "standalone"
    if doc.kind == "annual_report" and f.get("topic") == "segments":
        scope = "segment"
    f["scope"] = scope
    UNIT_FOR = {"receivable_days": "days", "inventory_days": "days", "operating_margin": "pct", "ebitda_margin": "pct",
                "revenue_growth_yoy": "pct", "revenue_growth_cc": "pct", "tax_rate": "pct"}
    uc = unit_class(r.get("unit"))
    if metric in UNIT_FOR and uc and uc != UNIT_FOR[metric]:
        flags.append(f"metric {metric} but unit '{r.get('unit')}' -> metric set to other")
        f["metric"] = metric = "other"
    if f["kind"] == "guidance":
        f["low"], f["high"] = _num(r.get("low")), _num(r.get("high"))
        f["direction"] = r.get("direction")
        f["covers"] = norm_period(r.get("covers_period"))
        if not f["covers"] and metric in ANNUAL_METRICS and (f["low"] is not None or f["high"] is not None or f["direction"]) \
                and "quarter" not in quote.lower() and not re.search(r"\bq[1-4]\b", quote.lower()) and f.get("quarter"):
            m = re.fullmatch(r"Q([1-4]) FY(\d{2})", f["quarter"])
            if m:   # an April-ish Q4 call is already in the new fiscal year; Q1-Q3 calls sit in the year they report
                base = int(m.group(2)) + (1 if m.group(1) == "4" else 0)
                if re.search(r"\bnext (financial |fiscal )?year\b", quote.lower()):
                    base += 1
                f["covers"] = f"FY{base:02d}"
                f["covers_inferred"] = True
                flags.append(f"period not stated in quote; inferred {f['covers']} from the {f['quarter']} call")
        if not values_in_quote([f["low"], f["high"]], quote):
            flags.append("guidance range not found in quote -> range dropped")
            f["low"] = f["high"] = None
    else:
        f["kind"] = "actual"
        v = _num(r.get("value"))
        if v is not None and round(v, 6) not in numbers(quote):
            flags.append(f"value {v} not found in quote -> dropped")
            v = None
        f["value"] = v
        f["period"] = norm_period(r.get("period"))
    _fix_period(f, flags)
    _refine_metric(f, flags)
    f["flags"] = flags


def _fy_of(f: dict):
    for src in (f.get("period"), f.get("quarter")):
        m = re.search(r"FY(\d{2})", src or "")
        if m:
            return m.group(1)
    return None


def _fix_period(f: dict, flags: list) -> None:
    """Cumulative figures (nine months, half-year) are not full-year or quarterly figures: tag them as such."""
    if f["kind"] != "actual":
        return
    t = f"{f.get('quote', '')} {f.get('text', '')}".lower()
    yy = _fy_of(f)
    if not yy:
        return
    new = None
    if re.search(r"nine[- ]months?|\b9 ?m\b|9 months", t):
        new = f"9M FY{yy}"
    elif re.search(r"six[- ]months?|first half|half[- ]year|\bh1\b|\b6 ?m\b", t):
        new = f"H1 FY{yy}"
    if new and f.get("period") != new and (not f.get("period") or f["period"].startswith(("FY", "Q"))):
        flags.append(f"period '{f.get('period')}' -> '{new}' (cumulative figure per quote)")
        f["period"] = new


def _refine_metric(f: dict, flags: list) -> None:
    """Split look-alike metrics so they are never compared: lease vs borrowings, commitments vs capex, etc."""
    if f["kind"] != "actual" or not f.get("metric"):
        return
    t = f"{f.get('quote', '')} {f.get('text', '')}".lower()
    m, new = f["metric"], None
    if m in ("borrowings", "net_debt") and "lease" in t:
        new = "lease_liabilities"
    elif m == "borrowings" and re.search(r"non[- ]current", t):
        new = "borrowings_noncurrent"
    elif m == "borrowings" and re.search(r"\bcurrent (borrowings|maturities)|short[- ]term borrowings", t):
        new = "borrowings_current"
    elif m == "capex" and "commitment" in t:
        new = "capital_commitments"
    elif m == "revenue" and re.search(r"total income|total revenue", t) and "operations" not in t:
        new = "total_income"
    if new:
        flags.append(f"metric {m} -> {new}")
        f["metric"] = new
