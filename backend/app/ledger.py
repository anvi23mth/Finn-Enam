"""Guidance ledger + actuals ledger, paired in code. Verdicts are assigned here, never by the LLM, and never by
comparing two guidance statements. delivered | partly | missed | revised | not_yet_testable (or None = cannot be scored)."""
from __future__ import annotations
from collections import defaultdict
from .periods import period_end, prev_quarter, yoy_period

SCORABLE = {"revenue", "revenue_growth_yoy", "revenue_growth_cc", "ebitda", "ebitda_margin", "ebit", "operating_margin", "pbt", "pat", "capex", "tax_rate"}
PCT_METRICS = {"revenue_growth_yoy", "revenue_growth_cc", "ebitda_margin", "operating_margin", "tax_rate"}


def _canon(g: dict):
    """(metric, unit class) with growth variants merged; revenue stated in % is revenue growth."""
    m, uc = g["metric"], _unit_class(g.get("unit"))
    if m in PCT_METRICS or (m == "revenue" and uc == "pct"):
        uc = "pct"
        if m in ("revenue_growth_yoy", "revenue_growth_cc", "revenue"):
            m = "revenue_growth"
    return m, uc


SCOPE_RANK = {"consolidated": 0, "unspecified": 1, "standalone": 2, "segment": 3}


from .ledger_units import unit_class as _unit_class


def _qkey(q: str):
    e = period_end(q or "")
    return e.toordinal() if e else 0


def data_through(facts: list) -> str | None:
    """End of the latest reported quarter among the concalls."""
    qs = [f["quarter"] for f in facts if f.get("doc_kind") == "concall" and f.get("quarter")]
    qs = [q for q in set(qs) if period_end(q)]
    return max(qs, key=_qkey) if qs else None


def _actuals(facts: list) -> list:
    return [f for f in facts if f["kind"] == "actual" and f.get("value") is not None and f.get("period") and f.get("metric") not in (None, "other")]


def _find_actual(actuals: list, metric: str, period: str, uclass):
    cands = [a for a in actuals if a["metric"] == metric and a["period"] == period and (uclass is None or _unit_class(a.get("unit")) == uclass)]
    cands.sort(key=lambda a: SCOPE_RANK.get(a["scope"], 9))
    return cands[0] if cands else None


def _cite(f):
    return {"fid": f["fid"], "doc": f["doc"], "page": f["page"], "quote": f["quote"], "text": f.get("text")}


def _compare(g: dict, actual: dict):
    v, lo, hi = actual["value"], g.get("low"), g.get("high")
    if lo is None and hi is None:
        return None, "no numeric target"
    lo = lo if lo is not None else hi
    hi = hi if hi is not None else lo
    if lo <= v <= hi:
        return "delivered", f"actual {v:g} within {lo:g}–{hi:g}"
    if v > hi:
        return "delivered", f"actual {v:g} above guided {lo:g}–{hi:g}"
    gap = (lo - v) / abs(lo) if lo else 1
    return ("partly", f"actual {v:g} below guided {lo:g}–{hi:g} by {gap:.0%}") if gap <= 0.05 else ("missed", f"actual {v:g} below guided {lo:g}–{hi:g} by {gap:.0%}")


def build(facts: list) -> dict:
    dt = data_through(facts)
    dt_end = period_end(dt) if dt else None
    actuals = _actuals(facts)
    guid = [f for f in facts if f["kind"] == "guidance" and f.get("metric") in SCORABLE
            and f.get("covers") and (f.get("low") is not None or f.get("high") is not None or f.get("direction"))]
    gid = {id(f) for f in guid}
    unscored = [_cite(f) | {"quarter_said": f.get("quarter")} for f in facts
                if f["kind"] == "guidance" and id(f) not in gid]

    chains = defaultdict(list)
    for g in guid:
        m, uc = _canon(g)
        directional = g.get("low") is None and g.get("high") is None
        chains[(m, g["covers"], uc, g.get("direction") if directional else None)].append(g)
    pairs = []
    for (metric, covers, uc, direction), items in chains.items():
        items.sort(key=lambda g: _qkey(g.get("quarter")))
        # one statement per quarter: the most frequently stated range wins (ties -> a full low-high range)
        per_q = defaultdict(list)
        for g in items:
            per_q[g.get("quarter")].append(g)
        picked = []
        for q, gs in per_q.items():
            cnt = defaultdict(list)
            for g in gs:
                cnt[(g.get("low"), g.get("high"), g.get("direction"))].append(g)
            best = max(cnt.values(), key=lambda v: (len(v), v[0].get("low") != v[0].get("high")))
            picked.append(best[0])
        items = sorted(picked, key=lambda g: _qkey(g.get("quarter")))
        # collapse reiterations (same range) into the first statement; ranges that change = revisions
        steps = []
        for g in items:
            rng = (g.get("low"), g.get("high"), g.get("direction"))
            if steps and steps[-1]["rng"] == rng:
                steps[-1]["reiterated"].append(g.get("quarter"))
            else:
                steps.append({"g": g, "rng": rng, "reiterated": []})
        end = period_end(covers)
        finished = bool(end and dt_end and end <= dt_end)
        for i, st in enumerate(steps):
            g, last = st["g"], i == len(steps) - 1
            p = {"id": f"G{len(pairs) + 1}", "metric": metric, "covers": covers, "unit": g.get("unit"), "scope": g["scope"],
                 "quarter_said": g.get("quarter"), "low": g.get("low"), "high": g.get("high"), "direction": g.get("direction"),
                 "reiterated_in": st["reiterated"], "covers_inferred": bool(g.get("covers_inferred")), "promised": _cite(g), "actual": None, "verdict": None, "detail": ""}
            if not last:
                nxt = steps[i + 1]["g"]
                p["verdict"] = "revised"
                p["detail"] = _delta(g, nxt)
                p["revised_to"] = _cite(nxt)
            elif not finished:
                p["verdict"] = "not_yet_testable"
                p["detail"] = f"{covers} ends {end}; reported data runs through {dt}" if end else "unknown period end"
            else:
                _score(p, g, actuals, metric, covers, uc)
            if p["covers_inferred"]:
                p["detail"] += " (period inferred from call date)"
            pairs.append(p)
    pairs.sort(key=lambda p: (_qkey(p["quarter_said"]), p["covers"]))
    for i, p in enumerate(pairs, 1):
        p["id"] = f"G{i}"
    return {"data_through": dt, "pairs": pairs, "unscored_guidance": unscored, "actuals": [_cite(a) | {k: a[k] for k in ("metric", "value", "unit", "scope", "period")} for a in actuals],
            **conflicts(facts)}


def _delta(old: dict, new: dict) -> str:
    q, uc = new.get("quarter"), _unit_class(new.get("unit") or old.get("unit"))
    sym = {"pct": "%", "inr_cr": " cr", "usd_m": " $m", "usd_b": " $bn"}.get(uc, "")
    pp = " pp" if uc == "pct" else sym
    if None not in (old.get("low"), old.get("high"), new.get("low"), new.get("high")):
        mo, mn = (old["low"] + old["high"]) / 2, (new["low"] + new["high"]) / 2
        d = mn - mo
        rel = f" ({d / mo:+.0%})" if uc != "pct" and mo else ""
        return (f"Revised in {q}: {_rng(old)}{sym} -> {_rng(new)}{sym}; low end {new['low'] - old['low']:+g}{pp}, "
                f"high end {new['high'] - old['high']:+g}{pp}; midpoint {mo:g} -> {mn:g} ({d:+g}{pp}){rel}")
    return f"Revised in {q}: {_rng(old)} -> {_rng(new)}"


def _rng(g):
    if g.get("low") is None and g.get("high") is None:
        return str(g.get("direction"))
    return f"{g['low']:g}" if g.get("low") == g.get("high") else f"{g.get('low'):g}–{g.get('high'):g}"


def _score(p: dict, g: dict, actuals: list, metric: str, covers: str, uc):
    if g.get("low") is None and g.get("high") is None:               # directional guidance, e.g. "Q4 better than Q3"
        d = g.get("direction") or ""
        base = prev_quarter(covers) if d.endswith("qoq") else yoy_period(covers) if d.endswith("yoy") else None
        cur, old = _find_actual(actuals, metric, covers, None), None
        if cur and base:
            old = next((a for a in sorted((a for a in actuals if a["metric"] == metric and a["period"] == base and a["unit"] == cur["unit"]),
                                          key=lambda a: SCOPE_RANK.get(a["scope"], 9)) if a["scope"] == cur["scope"]), None)
        if not base:
            p["detail"] = f"directional guidance ('{d or 'unspecified'}') has no quarter/year comparison basis -> not scored"
            return
        if not (cur and old):
            p["detail"] = f"period finished but no like-for-like reported figures found for {covers} and {base}"
            return
        chg = (cur["value"] / old["value"] - 1) * 100
        want_up = d.startswith("up")
        p["actual"], p["baseline"] = _cite(cur), _cite(old)
        p["scope"] = cur["scope"]
        ok = chg > 0 if want_up else chg < 0
        p["verdict"] = "delivered" if ok else ("partly" if abs(chg) < 1 else "missed")
        p["detail"] = f"{metric} {old['value']:g} ({base}) -> {cur['value']:g} ({covers}), {chg:+.1f}% [{cur['scope']}]"
        return
    a = _find_actual(actuals, metric, covers, uc)
    if not a:
        p["detail"] = f"period finished but no reported {metric} for {covers} in the documents"
        return
    if a["scope"] not in ("consolidated", "unspecified") and g["scope"] in ("consolidated", "unspecified"):
        p["actual"] = _cite(a)
        p["detail"] = f"scope mismatch: guidance is {g['scope']}, only a {a['scope']} figure found -> not scored"
        return
    v, d = _compare(g, a)
    p["actual"], p["verdict"], p["detail"] = _cite(a), v, f"{d} [{a['scope']}]"


import re as _re

_SEG_WORDS = _re.compile(r"\b(segment|segmental|division|vertical|subsidiar|business unit|geograph|domestic|export)\b", _re.I)
_PREFIX = _re.compile(r"^(?:(?:Q[1-4] |H[12] |9M )?FY ?\d{2,4} |Q[1-4] FY\d{2} )?(?:the )?([A-Z][A-Za-z&-]+(?: [A-Z][A-Za-z&-]+){0,3}) (?:(?:Q[1-4] |H[12] )?FY ?\d{2,4} |Q[1-4] FY\d{2} )?(?:revenue|EBITDA|PAT|margin)", _re.I)
_HEAD = {"consolidated", "total", "group", "overall", "company", "standalone", "net", "full", "quarterly", "annual", "operating", "revenue", "management", "reported"}


def _segmenty(f: dict) -> bool:
    t = f.get("text") or ""
    if _SEG_WORDS.search(t):
        return True
    m = _PREFIX.match(t.strip())
    return bool(m and m.group(1).split()[0].lower() not in _HEAD and not _re.search(r"consolidated|total|group|overall|company", t, _re.I))


def _same(a: float, b: float, tol=0.02) -> bool:
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-9)


def conflicts(facts: list) -> dict:
    """conflicts: same metric + period + scope with different values (genuine inconsistencies).
    scope_variants: same metric + period, different scopes (e.g. standalone vs consolidated) - listed, never merged."""
    grp = defaultdict(list)
    for f in _actuals(facts):
        if f["scope"] != "segment":
            grp[(f["metric"], f["period"])].append(f)
    conf, var = [], []
    for (m, per), fs in grp.items():
        if m in ("revenue", "ebitda", "pat", "ebit", "pbt"):   # a part is not a conflict with its whole
            top = max(f["value"] for f in fs)
            for f in fs:
                if f["value"] < 0.9 * top and f["scope"] != "unspecified" and f.get("doc_kind") == "concall" and _segmenty(f):
                    f["scope"] = "segment"
                    f.setdefault("flags", []).append("reclassified as segment figure (part of a larger same-metric figure)")
            fs = [f for f in fs if f["scope"] != "segment"]
        by_scope = defaultdict(list)
        for f in fs:
            by_scope[f["scope"]].append(f["value"])
        def distinct(vs):                                        # values within 2% are the same figure (rounding)
            out = []
            for v in vs:
                if not any(_same(v, o) for o in out):
                    out.append(v)
            return out
        by_scope = {k: set(distinct(v)) for k, v in by_scope.items()}
        # an 'unspecified' figure equal to a stated-scope figure is just the same number
        known = [x for k, v in by_scope.items() if k != "unspecified" for x in v]
        by_scope = {k: ({x for x in v if not any(_same(x, y) for y in known)} if k == "unspecified" else v) for k, v in by_scope.items()}
        by_scope = {k: v for k, v in by_scope.items() if v}
        row = lambda: [{"fid": f["fid"], "scope": f["scope"], "value": f["value"], "unit": f.get("unit"), "doc": f["doc"], "page": f["page"]} for f in fs]
        if len(fs) < 2:
            continue
        if any(len(v) > 1 for v in by_scope.values()):
            conf.append({"metric": m, "period": per, "facts": row()})
        elif len(by_scope) > 1:
            var.append({"metric": m, "period": per, "facts": row()})
    var += _debt_definition_variants(facts)
    return {"conflicts": conf, "scope_variants": var}


def _year_end(p: str):
    e = period_end(p or "")
    return e if e and (p.startswith("FY") or p.startswith("as of")) and (e.month, e.day) == (3, 31) else None


def _debt_definition_variants(facts: list) -> list:
    """'Debt-free' (D/E or net debt = 0) next to positive gross borrowings at the same year-end: different definitions and/or scopes.
    Listed for Stage 2 to explain or flag - never merged."""
    zero, pos = [], []
    for f in _actuals(facts):
        e = _year_end(f["period"])
        if not e or f["scope"] == "segment":
            continue
        if f["metric"] in ("debt_equity", "net_debt") and f["value"] == 0:
            zero.append((e, f))
        elif f["metric"] == "borrowings" and f["value"] > 0:
            pos.append((e, f))
    out = []
    for e, z in zero:
        for e2, b in pos:
            if e == e2:
                out.append({"metric": "debt-free (D/E or net debt = 0) vs gross borrowings > 0 (definitions/scope differ?)", "period": f"year-end {e}",
                            "facts": [{"fid": x["fid"], "scope": x["scope"], "value": x["value"], "unit": x.get("unit") or x["metric"], "doc": x["doc"], "page": x["page"]} for x in (z, b)]})
    return out
