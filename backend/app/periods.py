"""Fiscal-period helpers (Indian FY: April-March). Periods are normalised to 'FY26', 'Q2 FY27', 'H1 FY27' or 'as of 31 Mar 2026'."""
from __future__ import annotations
import re
from datetime import date

MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MON_NAME = {v: k.title() for k, v in MON.items()}


def _yy(s: str) -> int:
    return int(s[-2:])


def quarter_from_call(label: str) -> str | None:
    """Call held in <month year> -> the fiscal quarter it reports. 'Oct 2026' -> 'Q2 FY27'."""
    m = re.match(r"\s*([A-Za-z]{3})[a-z]*\s+(\d{4})", label)
    if not m or m.group(1).lower() not in MON:
        return None
    mon, y = MON[m.group(1).lower()], int(m.group(2))
    if 4 <= mon <= 6:
        q, fy = 4, y
    elif 7 <= mon <= 9:
        q, fy = 1, y + 1
    elif 10 <= mon <= 12:
        q, fy = 2, y + 1
    else:
        q, fy = 3, y
    return f"Q{q} FY{fy % 100:02d}"


def norm_period(s) -> str | None:
    if not s:
        return None
    t = str(s).strip().lower().replace("’", "'")
    m = re.search(r"\bq([1-4])\s*(?:fy|f\.y\.)?\s*'?(\d{2,4})\b", t)
    if m:
        return f"Q{m.group(1)} FY{_yy(m.group(2))}"
    m = re.search(r"\b9m\s*(?:fy|f\.y\.)?\s*'?(\d{2,4})\b", t)
    if m:
        return f"9M FY{_yy(m.group(1))}"
    m = re.search(r"\bh([12])\s*(?:fy|f\.y\.)?\s*'?(\d{2,4})\b", t)
    if m:
        return f"H{m.group(1)} FY{_yy(m.group(2))}"
    m = re.search(r"(?:\bfy|financial year|fiscal(?: year)?)\s*'?\s*(\d{4})\s*[-–/]\s*'?(\d{2,4})", t) or re.search(r"\b(\d{4})\s*[-–]\s*(\d{2})\b", t)
    if m:
        return f"FY{_yy(m.group(2))}"
    m = re.search(r"(?:\bfy|financial year|fiscal(?: year)?)\s*'?\s*(\d{2,4})\b", t)
    if m:
        return f"FY{_yy(m.group(1))}"
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*,?\s+(\d{4})", t) or None
    if m and m.group(2) in MON:
        return f"as of {int(m.group(1))} {MON_NAME[MON[m.group(2)]]} {m.group(3)}"
    m = re.search(r"([a-z]{3})[a-z]*\s+(\d{1,2}),?\s+(\d{4})", t)
    if m and m.group(1) in MON:
        return f"as of {int(m.group(2))} {MON_NAME[MON[m.group(1)]]} {m.group(3)}"
    return None


def period_end(p: str) -> date | None:
    if not p:
        return None
    m = re.fullmatch(r"FY(\d{2})", p)
    if m:
        return date(2000 + int(m.group(1)), 3, 31)
    m = re.fullmatch(r"Q([1-4]) FY(\d{2})", p)
    if m:
        q, yy = int(m.group(1)), 2000 + int(m.group(2))
        return {1: date(yy - 1, 6, 30), 2: date(yy - 1, 9, 30), 3: date(yy - 1, 12, 31), 4: date(yy, 3, 31)}[q]
    m = re.fullmatch(r"9M FY(\d{2})", p)
    if m:
        return date(2000 + int(m.group(1)) - 1, 12, 31)
    m = re.fullmatch(r"H([12]) FY(\d{2})", p)
    if m:
        yy = 2000 + int(m.group(2))
        return date(yy - 1, 9, 30) if m.group(1) == "1" else date(yy, 3, 31)
    m = re.fullmatch(r"as of (\d{1,2}) ([A-Za-z]{3}) (\d{4})", p)
    if m:
        return date(int(m.group(3)), MON[m.group(2).lower()], int(m.group(1)))
    return None


def prev_quarter(p: str) -> str | None:
    m = re.fullmatch(r"Q([1-4]) FY(\d{2})", p or "")
    if not m:
        return None
    q, yy = int(m.group(1)), int(m.group(2))
    return f"Q4 FY{yy - 1:02d}" if q == 1 else f"Q{q - 1} FY{yy:02d}"


def yoy_period(p: str) -> str | None:
    m = re.fullmatch(r"(Q[1-4]|H[12])? ?FY(\d{2})", p or "")
    return f"{(m.group(1) + ' ') if m.group(1) else ''}FY{int(m.group(2)) - 1:02d}" if m else None
