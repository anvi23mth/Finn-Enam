#!/usr/bin/env python3
"""Usage: python backend/scripts/research.py INFY [--no-ingest] [--fast-stage2]\n  --fast-stage2: run Stage 2 on CHEAP_MODEL only (use when the strong chain is overloaded); recorded as a fallback in the output"""
from __future__ import annotations
import sys, textwrap
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.research import run_research  # noqa: E402
from app.llm import LLMError  # noqa: E402

W = lambda s, i="    ": textwrap.fill(s, 100, initial_indent=i, subsequent_indent=i)


def cites(c):
    seen = dict.fromkeys(f"[{x['doc'].split('__')[-1]} p{x['page']}]" for x in c.get("cites", []))
    return " ".join(seen)


def claim(c, bullet="•"):
    if not c:
        return
    print(W(f"{bullet} {c['text']}  {cites(c)}", "  "))


def main(t: str, ingest: bool, fast: bool = False):
    from app import config
    try:
        r = run_research(t, do_ingest=ingest, stage2_models=[config.CHEAP_MODEL] if fast else None,
                         override_reason=f"manual --fast-stage2: Stage 2 forced onto {config.CHEAP_MODEL} because the strong chain was overloaded" if fast else None)
    except (LLMError, RuntimeError) as e:
        print(f"ERROR: {e}"); return 1
    v = r["view"]
    print(f"\n==== {r['ticker']}  (stage1 model={r['models']['cheap']}, stage2 model used={r['models']['strong_used']}{' — FALLBACK, requested ' + r['models']['strong_requested'] if r['models']['used_fallback'] else ''}) ====")
    for key, title in [("business_snapshot", "BUSINESS"), ("financial_snapshot", "FINANCIALS"), ("trajectory", "TRAJECTORY"),
                       ("balance_sheet", "BALANCE SHEET"), ("cash_quality", "CASH QUALITY")]:
        print(f"\n-- {title}")
        for c in v.get(key, []):
            claim(c)
    print("\n-- PROMISED vs DELIVERED")
    for e in v.get("promised_vs_delivered", []):
        print(f"  [{e.get('verdict','?').upper()}] {e.get('topic','')}  (said in {e.get('quarter_promised','?')})")
        print(W(f"promised: {e['promised']['text']}  {cites(e['promised'])}", "     "))
        if e.get("delivered"):
            print(W(f"delivered: {e['delivered']['text']}  {cites(e['delivered'])}", "     "))
    for key, title in [("narrative_vs_numbers", "NARRATIVE vs NUMBERS"), ("bull_case", "BULL"), ("bear_case", "BEAR")]:
        print(f"\n-- {title}")
        for c in v.get(key, []):
            claim(c, "+" if key == "bull_case" else "−" if key == "bear_case" else "•")
    print("\n-- STAGE 1 EXTRACTION")
    for d in r["stage1"]:
        print(f"  {d['doc']:<34} {d.get('quarter',''):<10} kept {d['n_items']:>3}, dropped (quote not found) {d['n_dropped']}")
    print(f"\n-- CLAIMS THAT FAILED THE QUOTE CHECK ({len(r['failed_claims'])} stage-2, "
          f"{sum(d['n_dropped'] for d in r['stage1'])} stage-1)")
    for f in r["failed_claims"]:
        print(W(f"✗ {f.get('path')}: {f.get('text') or f.get('reason')}  {f.get('failed_cites', '')}", "  "))
    for d in r["stage1"]:
        for x in d["dropped"][:3]:
            print(W(f"✗ [stage1 {d['doc']}] {x.get('text','')} — {x.get('reason')}", "  "))
    print("\n-- TOKEN USAGE")
    tot = 0
    for st, u in r["usage"].items():
        tot += u["prompt"] + u["output"] + u["thinking"]
        print(f"  {st:<22} {u['model']:<22} calls {u['calls']} (cached {u['cached_calls']})  in {u['prompt']:>8,}  out {u['output']:>7,}  thinking {u['thinking']:>7,}")
    print(f"  total fresh tokens: {tot:,}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], "--no-ingest" not in sys.argv, "--fast-stage2" in sys.argv))
