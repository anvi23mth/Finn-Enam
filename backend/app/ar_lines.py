"""Deterministic table-row extraction from annual-report cash-flow statements (no LLM).
Used where a guided metric (capex) is a literal row in the statements but the LLM extraction did not pick it up.
Every fact's quote is the row text copied from the page, so it passes the quote check by construction."""
from __future__ import annotations
import re

ROWS = [("capex", re.compile(r"^\s*(?:\d+\.\s*)?Purchase of Property,? Plant (?:and|&) Equipment[^\n(]*?\(?\s*([\d,]+\.?\d*)\s*\)?\s+\(?\s*[\d,]+\.?\d*\s*\)?\s*$", re.I | re.M))]


def cashflow_facts(doc, start_n: int) -> list:
    m = re.search(r"(\d{4})", doc.label)
    if doc.kind != "annual_report" or not m:
        return []
    year = int(m.group(1))
    yy = f"FY{year % 100:02d}"
    out = []
    for page, text in sorted(doc.pages.items()):
        head = text[:400].lower()
        if "cash flow statement" not in head:
            continue
        if not re.search(rf"(31(st)?\s+march,?\s+{year}|march\s+31,?\s+{year})", text, re.I):
            continue
        scope = "consolidated" if "consolidated" in head else "standalone" if "standalone" in head else "unspecified"
        unit = "INR crore" if re.search(r"crore", text[:1500], re.I) else None
        if not unit:
            continue
        for metric, rx in ROWS:
            for row in rx.finditer(text):
                line = row.group(0).strip()
                out.append({"fid": f"F{start_n + len(out) + 1}", "doc": doc.id, "doc_kind": "annual_report", "quarter": None, "page": page,
                            "type": "table_row", "topic": "cash_flow", "kind": "actual", "metric": metric,
                            "value": float(row.group(1).replace(",", "")), "unit": unit, "scope": scope, "period": yy,
                            "text": f"{scope.title()} {yy} purchase of property, plant and equipment (cash flow statement row)",
                            "quote": line, "verified": "table_row", "flags": ["deterministic table-row parse (cash-flow statement)"]})
    return out
