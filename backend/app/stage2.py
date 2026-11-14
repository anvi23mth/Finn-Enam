"""Stage 2 (strong model): one synthesis call over structured facts + the code-built guidance ledger, then code-level
citation verification and scope/period consistency checks. Verdicts come from ledger.py, not from this model."""
from __future__ import annotations
from . import config, llm
from .docs import Doc
from .log import log
from .verify import verify_cite

V = "synth-v2"

SYS = ("You are an equity research analyst writing from PRIMARY SOURCES ONLY. Use ONLY the facts supplied below. "
       "Do not use any outside knowledge about the company, its industry, news or analyst views. "
       "If something is not supported by the supplied facts, write exactly \"not found in documents\" as the claim text with empty cites and fact_ids. "
       "Every claim carries cites: [{\"doc\": <doc id>, \"page\": <int>, \"quote\": <verbatim quote copied from a supplied fact>}] and fact_ids: [<F ids used>]. "
       "Copy quotes exactly; never invent or alter them. "
       "SCOPE AND PERIOD DISCIPLINE: every number you state must name its scope (consolidated/standalone) and period (e.g. FY26, Q2 FY27, as of 31 Mar 2026) in the text. "
       "Prefer consolidated. NEVER combine, subtract or compare numbers whose scope or period differ, and never put them in one 'point' or 'ratio' claim. "
       "If the facts conflict (different scope, period or definition), do not pick one silently: write a claim whose text starts with \"SCOPE MISMATCH:\" that lists both facts. "
       "Do not assign delivered/missed verdicts anywhere; those are computed elsewhere. Be concise and specific; no filler. Output JSON only.")

SPEC = """Return JSON with exactly these keys. A "claim" is {"text": str, "kind": "point"|"ratio"|"trend"|"text", "fact_ids": [str], "cites": [{"doc": str, "page": int, "quote": str}]}.
 kind: point = one figure; ratio = derived from facts of the SAME scope and period; trend = same scope, different periods allowed; text = no numbers.
{
 "business_snapshot": [claim],     // what it does, segments, revenue mix (2-4)
 "financial_snapshot": [claim],    // latest headline numbers, one scope and period per claim
 "trajectory": [claim],            // multi-year direction (kind trend)
 "balance_sheet": [claim],         // debt, leverage, working capital; reconcile conflicting borrowing/debt facts explicitly
 "cash_quality": [claim],          // operating cash flow vs profit, capex, FCF - ONLY when scope and period match
 "reconciliation": [claim],        // one claim per KNOWN CONFLICT below: explain the difference if the facts show why (scope/period/definition), else start with "SCOPE MISMATCH:"
 "narrative_vs_numbers": [claim],  // where management's story and the reported numbers agree or diverge
 "guidance_explanations": [{"pair_id": "G1", "text": str, "cites": [{"doc","page","quote"}]}],  // one short sentence per ledger pair explaining the situation; do NOT state a verdict
 "bull_case": [claim], "bear_case": [claim]   // 3 tight points each
}
Keep each claim under 40 words."""


def _fmt_fact(f: dict) -> str:
    tags = [f["doc"].split("__")[-1], f"p{f['page']}"]
    if f.get("scope"):
        tags.append(f["scope"])
    if f.get("period"):
        tags.append(f["period"])
    elif f.get("quarter") and f["doc_kind"] == "concall":
        tags.append(f"call:{f['quarter']}")
    st = f" {f['metric']}={f['value']:g} {f.get('unit') or ''}".rstrip() if f.get("value") is not None and f.get("metric") else ""
    return f"{f['fid']} [{' | '.join(tags)}]{st} {f.get('text', '')} | \"{f.get('quote', '')}\""


def compact(facts: list, ledger: dict, max_chars: int) -> str:
    keep = [f for f in facts if f["kind"] != "guidance" and f.get("type") != "analyst_question"]
    structured = [f for f in keep if f.get("metric") and f["metric"] != "other"]
    rest = [f for f in keep if f not in structured]
    lines = [_fmt_fact(f) for f in structured]
    budget = max_chars - sum(len(x) for x in lines) - 6000
    for f in rest:                       # unstructured facts: business text, auditor remarks, qualitative numbers
        x = _fmt_fact(f)
        if budget - len(x) < 0:
            break
        budget -= len(x)
        lines.append(x)
    return "\n".join(lines)


def ledger_text(ledger: dict) -> str:
    out = [f"Reported data runs through {ledger['data_through']}."]
    for p in ledger["pairs"]:
        rng = p["direction"] if p["low"] is None and p["high"] is None else (f"{p['low']:g}" if p["low"] == p["high"] else f"{p['low']:g}-{p['high']:g}")
        act = f" ACTUAL [{p['actual']['doc'].split('__')[-1]} p{p['actual']['page']}] \"{p['actual']['quote']}\"" if p.get("actual") else ""
        out.append(f"{p['id']}: {p['metric']} for {p['covers']} guided {rng} {p.get('unit') or ''} in {p['quarter_said']} "
                   f"[{p['promised']['doc'].split('__')[-1]} p{p['promised']['page']}] \"{p['promised']['quote']}\" "
                   f"-> CODE VERDICT {p['verdict'] or 'unscored'}: {p['detail']}{act}")
    return "\n".join(out)


def conflicts_text(ledger: dict) -> str:
    def fmt(c):
        return f"- {c['metric']} {c['period']}: " + "; ".join(f"{x['fid']}={x['value']:g} {x.get('unit') or ''} ({x['scope']}, {x['doc'].split('__')[-1]} p{x['page']})" for x in c["facts"])
    out = [f"SAME SCOPE, DIFFERENT VALUES (genuine inconsistency):\n" + "\n".join(fmt(c) for c in ledger["conflicts"])] if ledger["conflicts"] else []
    out += ["DIFFERENT SCOPES (do not merge; state each with its scope):\n" + "\n".join(fmt(c) for c in ledger["scope_variants"])] if ledger["scope_variants"] else []
    out.append("Also reconcile any borrowing/debt statements that look inconsistent (gross borrowings vs net debt vs debt-equity; current vs total; scope; date).")
    return "\n".join(out)


def run(ticker: str, facts: list, ledger: dict, usage: llm.Usage, doc_hash: str, models: list | None = None) -> tuple:
    body = compact(facts, ledger, config.S2_MAX_CHARS)
    prompt = (f"Company ticker: {ticker}\nFACTS (id [doc | page | scope | period] metric=value text | quote):\n{body}\n\n"
              f"GUIDANCE LEDGER (verdicts are computed by code; explain only):\n{ledger_text(ledger)}\n\n"
              f"KNOWN CONFLICTS :\n{conflicts_text(ledger)}\n\n{SPEC}")
    log(f"stage 2 input: ~{len(prompt) // 4:,} tokens ({len(prompt):,} chars); {len(ledger['pairs'])} ledger pairs, {len(ledger['conflicts'])} conflicts, {len(ledger['scope_variants'])} scope variants")
    chain = models or config.strong_chain()
    log(f"stage 2 model chain: {' -> '.join(chain)}")
    return llm.call_chain(models=chain, system=SYS, version=V, doc_hash=doc_hash, part="synth",
                          stage="stage2_synthesis", usage=usage, prompt=prompt)


def _ptype(p: str) -> str:
    return "asof" if p.startswith("as of") else p.split(" ")[0] if p[:1] in "QH" else "FY"


def check_consistency(view: dict, facts_by_id: dict, flags: list) -> dict:
    """Remove claims that mix scopes (always) or periods (point/ratio claims). They are listed in `flags`, not stated."""
    for sec in ("financial_snapshot", "balance_sheet", "cash_quality", "trajectory", "narrative_vs_numbers", "bull_case", "bear_case", "business_snapshot", "reconciliation"):
        keep = []
        for c in view.get(sec) or []:
            fs = [facts_by_id.get(i) for i in c.get("fact_ids") or []]
            unknown = [i for i, f in zip(c.get("fact_ids") or [], fs) if f is None]
            fs = [f for f in fs if f and f.get("value") is not None]
            scopes = {f["scope"] for f in fs if f.get("scope") not in (None, "unspecified")}
            periods = {f["period"] for f in fs if f.get("period")}
            is_flag = str(c.get("text", "")).startswith("SCOPE MISMATCH")
            if unknown:
                flags.append({"section": sec, "reason": f"unknown fact ids {unknown}", "text": c.get("text")})
            elif len(scopes) > 1 and not is_flag:
                flags.append({"section": sec, "reason": f"scope mismatch ({', '.join(sorted(scopes))}) mixed in one claim", "text": c.get("text")})
            elif len({_ptype(x) for x in periods}) > 1 and not is_flag:
                flags.append({"section": sec, "reason": f"period-type mismatch ({', '.join(sorted(periods))}): full-year, half-year, quarter and point-in-time figures are not comparable", "text": c.get("text")})
            elif len(periods) > 1 and c.get("kind") in ("point", "ratio") and not is_flag:
                flags.append({"section": sec, "reason": f"period mismatch ({', '.join(sorted(periods))}) in a {c.get('kind')} claim", "text": c.get("text")})
            else:
                keep.append(c)
        view[sec] = keep
    return view


# ---- verification -------------------------------------------------------------------------
def verify_tree(node, docs: dict[str, Doc], failed: list, path: str = ""):
    """Verify every {text, cites} claim. Failing claims are removed and recorded in `failed`."""
    if isinstance(node, list):
        out = []
        for i, x in enumerate(node):
            y = verify_tree(x, docs, failed, f"{path}[{i}]")
            if y is not None:
                out.append(y)
        return out
    if isinstance(node, dict):
        if "cites" in node and "text" in node:
            return _verify_claim(node, docs, failed, path)
        out = {}
        for k, v in node.items():
            out[k] = verify_tree(v, docs, failed, f"{path}.{k}")
        if "promised" in out and out["promised"] is None:
            failed.append({"path": path, "reason": "dropped entry: promised claim failed verification"})
            return None
        if "delivered" in out and out["delivered"] is None:
            out["verdict"] = "unverified"   # evidence for the outcome failed the quote check
        return out
    return node


def _resolve_doc(docs: dict, name: str):
    """The facts show short doc tags (e.g. 'annual-report-2026'); accept full ids or unique short tags."""
    if name in docs:
        return docs[name]
    hits = [d for k, d in docs.items() if k.split("__")[-1] == name or k.endswith(name)]
    return hits[0] if len(hits) == 1 else None


def _verify_claim(c: dict, docs: dict[str, Doc], failed: list, path: str):
    cites = c.get("cites") or []
    if not cites:
        if str(c.get("text", "")).strip().lower().startswith("not found in documents"):
            return {**c, "verified": True}
        failed.append({"path": path, "text": c.get("text"), "reason": "no citation"})
        return None
    checked, bad = [], []
    for ct in cites:
        d = _resolve_doc(docs, str(ct.get("doc")))
        if not d:
            bad.append({**ct, "reason": "unknown doc"}); continue
        try:
            page = int(ct.get("page"))
        except (TypeError, ValueError):
            bad.append({**ct, "reason": "bad page"}); continue
        st, found, score = verify_cite(str(ct.get("quote", "")), page, d.pages)
        if st == "failed":
            bad.append({**ct, "reason": f"quote not on p{page} (best match {score:.2f})"})
        else:
            checked.append({**ct, "doc": d.id, "page": found, "status": st})
    if bad:
        failed.append({"path": path, "text": c.get("text"), "failed_cites": bad})
    if not checked:
        return None
    return {**c, "cites": checked, "verified": not bad}
