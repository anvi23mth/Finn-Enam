"""Stage 2 (strong model): one synthesis call over compact Stage-1 facts, then code-level citation verification."""
from __future__ import annotations
from . import config, llm
from .log import log
from .docs import Doc
from .verify import verify_cite

V = "synth-v1"

SYS = ("You are an equity research analyst writing from PRIMARY SOURCES ONLY. Use ONLY the facts supplied below. "
       "Do not use any outside knowledge about the company, its industry, news or analyst views. "
       "If something is not supported by the supplied facts, write exactly \"not found in documents\" as the claim text with an empty cites list. "
       "Every claim must carry cites: [{\"doc\": <doc id>, \"page\": <int>, \"quote\": <verbatim quote copied from the supplied fact>}]. "
       "Copy quotes exactly as supplied; never invent or alter quotes. Be concise and specific; no filler. Output JSON only.")

SPEC = """Return JSON with exactly these keys. A "claim" is {"text": str, "cites": [{"doc": str, "page": int, "quote": str}]}.
{
 "business_snapshot": [claim],            // what it does, segments, revenue mix (2-4 claims)
 "financial_snapshot": [claim],           // latest headline numbers: revenue, EBITDA/EBIT, PAT, margins, key ratios
 "trajectory": [claim],                   // multi-year direction: what is growing, what is compressing
 "balance_sheet": [claim],                // debt, leverage, working-capital cycle, funding
 "cash_quality": [claim],                 // CFO vs profit, capex, free cash flow
 "promised_vs_delivered": [               // last 4 quarters of concalls: each explicit guidance item
   {"topic": str, "quarter_promised": str, "promised": claim, "delivered": claim,
    "verdict": "delivered"|"partly"|"missed"|"not_yet_testable"}],   // delivered claim = what later calls/annual report show actually happened
 "narrative_vs_numbers": [claim],         // where the management story and the numbers agree or diverge
 "bull_case": [claim],                    // 3 tight points
 "bear_case": [claim]                     // 3 tight points
}
Rules: quarters are given per document; guidance from the most recent call cannot be tested yet -> verdict "not_yet_testable" and delivered.text "not found in documents".
Judge a verdict only from supplied facts. Keep each claim text under 40 words."""


def compact(stage1: list[dict]) -> str:
    lines = []
    for d in stage1:
        head = f"## DOC {d['doc']} ({d['kind']}" + (f", quarter {d['quarter']}" if d.get("quarter") else "") + ")"
        lines.append(head)
        for it in d["items"]:
            t = it.get("type") or ""
            lines.append(f"- p{it['page']} [{t}/{it.get('topic','')}] {it.get('text','')} | \"{it.get('quote','')}\"")
    return "\n".join(lines)


def trim(stage1: list[dict], max_chars: int) -> list[dict]:
    """If the compact input is too big, keep fewer items per doc: analyst questions first, then numbers, then the rest."""
    caps = [None, 12, 8, 5, 3]
    for cap in caps:
        out = []
        for d in stage1:
            items = d["items"]
            if cap is not None:
                rank = {"guidance": 0, "number": 1, "analyst_question": 2}
                items = sorted(items, key=lambda x: rank.get(x.get("type"), 1) if d["kind"] == "concall" else 0)
                if d["kind"] == "concall":
                    g = [i for i in items if i.get("type") == "guidance"]
                    rest = [i for i in items if i.get("type") != "guidance"][:cap]
                    items = g + rest
                else:
                    items = items[: cap * 6]
            out.append({**d, "items": items})
        if len(compact(out)) <= max_chars:
            return out
    return out


def run(ticker: str, stage1: list[dict], usage: llm.Usage, doc_hash: str, models: list | None = None) -> tuple:
    full = len(compact(stage1))
    stage1 = trim(stage1, config.S2_MAX_CHARS)
    sent = len(compact(stage1))
    log(f"stage 2 input: {full:,} chars (~{full // 4:,} tokens) full -> {sent:,} chars (~{sent // 4:,} tokens) after trim "
        f"(cap {config.S2_MAX_CHARS:,}); items {sum(len(d['items']) for d in stage1)}")
    prompt = f"Company ticker: {ticker}\nFACTS (each line: page, tags, restatement | verbatim quote):\n{compact(stage1)}\n\n{SPEC}"
    chain = models or config.strong_chain()
    log(f"stage 2 model chain: {' -> '.join(chain)}")
    return llm.call_chain(models=chain, system=SYS, version=V, doc_hash=doc_hash, part="synth",
                          stage="stage2_synthesis", usage=usage, prompt=prompt)


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


def _verify_claim(c: dict, docs: dict[str, Doc], failed: list, path: str):
    cites = c.get("cites") or []
    if not cites:
        if str(c.get("text", "")).strip().lower().startswith("not found in documents"):
            return {**c, "verified": True}
        failed.append({"path": path, "text": c.get("text"), "reason": "no citation"})
        return None
    checked, bad = [], []
    for ct in cites:
        d = docs.get(str(ct.get("doc")))
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
            checked.append({**ct, "page": found, "status": st})
    if bad:
        failed.append({"path": path, "text": c.get("text"), "failed_cites": bad})
    if not checked:
        return None
    return {**c, "cites": checked, "verified": not bad}
