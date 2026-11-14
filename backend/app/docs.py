from __future__ import annotations
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from . import config


@dataclass
class Doc:
    id: str            # file stem, e.g. concall__oct-2026
    kind: str          # annual_report | concall
    label: str         # human label from the stem
    sha: str
    pages: dict        # {page_number: text}


def load_docs(ticker: str) -> list[Doc]:
    d = config.DOCS_DIR / ticker.upper()
    docs = []
    for jp in sorted(d.glob("*.json")):
        pdf = jp.with_suffix(".pdf")
        if not pdf.exists():
            continue
        data = json.loads(jp.read_text())
        kind = jp.stem.split("__")[0]
        docs.append(Doc(id=jp.stem, kind=kind, label=jp.stem.split("__", 1)[1].replace("-", " ").title(),
                        sha=hashlib.sha256(pdf.read_bytes()).hexdigest()[:16],
                        pages={p["page"]: p["text"] for p in data["pages"]}))
    return docs


def chunk_pages(pages: dict, n: int) -> list[list[int]]:
    nums = sorted(pages)
    return [nums[i:i + n] for i in range(0, len(nums), n)]


def render(pages: dict, nums: list[int]) -> str:
    return "\n".join(f"<<<PAGE {p}>>>\n{pages[p]}" for p in nums)


# Annual reports are 300-450 pages; send only the pages most likely to hold the financial facts we need.
TOPIC_KEYS = {
    "business": [("business overview", 3), ("our business", 2), ("segment", 2), ("revenue by", 3), ("management discussion", 3), ("business model", 2)],
    "multiyear": [("five year", 4), ("ten year", 4), ("decade", 3), ("financial highlights", 4), ("ebitda", 2), ("operating margin", 2), ("profit after tax", 2), ("key financial", 3)],
    "debt": [("borrowings", 3), ("net debt", 3), ("debt equity", 3), ("debt-equity", 3), ("gearing", 2), ("lease liabilit", 1)],
    "workingcap": [("working capital", 3), ("trade receivables", 2), ("inventor", 2), ("debtor days", 3), ("receivable days", 3), ("trade payables", 1)],
    "cashflow": [("cash flow from operating", 4), ("net cash generated from operating", 4), ("net cash from operating", 4), ("capital expenditure", 2), ("purchase of property", 3), ("free cash flow", 3)],
    "audit": [("contingent liabilit", 4), ("key audit matter", 4), ("emphasis of matter", 4), ("independent auditor", 2), ("qualified opinion", 4), ("related party", 1)],
}


def select_ar_pages(pages: dict, max_pages: int) -> list[int]:
    per = max(4, max_pages // len(TOPIC_KEYS))
    chosen: set[int] = set()
    for _, keys in TOPIC_KEYS.items():
        scored = []
        for p, t in pages.items():
            if len(t) < 600:
                continue
            tl = t.lower()
            s = sum(min(tl.count(k), 3) * w for k, w in keys)
            # statements full of numbers are what we want
            digits = sum(c.isdigit() for c in t) / max(len(t), 1)
            if s:
                scored.append((s * (1 + digits * 2), p))
        scored.sort(reverse=True)
        chosen.update(p for _, p in scored[:per])
    return sorted(chosen)[:max_pages]
