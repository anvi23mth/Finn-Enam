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


NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers(s: str) -> set:
    out = set()
    for x in NUM_RE.findall(s or ""):
        try:
            out.add(round(float(x.replace(",", "")), 6))
        except ValueError:
            pass
    return out


def numbers_on_page(quote: str, page_text: str) -> bool:
    """Table-style quotes: accept when every number in the quote (>=2 of them) appears on the page and most
    of the quote's words do too. Used when a long row/paragraph can't be fuzzy-matched verbatim."""
    qn = numbers(quote)
    if len(qn) < 2 or not qn <= numbers(page_text):
        return False
    words = [w for w in norm(quote).split() if len(w) >= 4 and not w[0].isdigit()]
    if not words:
        return True
    pw = set(norm(page_text).split())
    return sum(w in pw for w in words) / len(words) >= 0.5


def values_in_quote(vals: list, quote: str) -> bool:
    qn = numbers(quote)
    return all(round(float(v), 6) in qn for v in vals if v is not None)


def verify_cite(quote: str, page: int, pages: dict[int, str]) -> tuple[str, int | None, float]:
    """Returns (status, page_found, score). status: verified | numbers_verified | page_corrected | failed."""
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
    for q in (page, page - 1, page + 1):
        if q in pages and numbers_on_page(quote, pages[q]):
            return "numbers_verified", q, 0.9
    return "failed", None, s
