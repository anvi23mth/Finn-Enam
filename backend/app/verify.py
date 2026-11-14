"""Check that a quoted passage really appears on the cited page (normalised + fuzzy)."""
from __future__ import annotations
import re
from difflib import SequenceMatcher

THRESH = 0.88


def norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    s = re.sub(r"-\s*\n\s*", "", s)          # de-hyphenate line breaks
    s = re.sub(r"[^a-z0-9%.$₹ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def match_score(quote: str, page_text: str) -> float:
    q, p = norm(quote), norm(page_text)
    if not q or not p:
        return 0.0
    if q in p:
        return 1.0
    qt, pt = q.split(), p.split()
    n = len(qt)
    if n == 0 or len(pt) < max(3, n // 2):
        return 0.0
    best = 0.0
    for size in {n, max(1, n - 2), n + 2}:
        for i in range(0, max(1, len(pt) - size + 1)):
            s = SequenceMatcher(None, q, " ".join(pt[i:i + size])).ratio()
            if s > best:
                best = s
                if best >= 0.999:
                    return best
    return best


def verify_cite(quote: str, page: int, pages: dict[int, str]) -> tuple[str, int | None, float]:
    """Returns (status, page_found, score). status: verified | page_corrected | failed."""
    if not quote or len(norm(quote).split()) < 3:
        return "failed", None, 0.0
    s = match_score(quote, pages.get(page, ""))
    if s >= THRESH:
        return "verified", page, s
    for q in (page - 1, page + 1):
        if q in pages:
            s2 = match_score(quote, pages[q])
            if s2 >= THRESH:
                return "page_corrected", q, s2
    return "failed", None, s
