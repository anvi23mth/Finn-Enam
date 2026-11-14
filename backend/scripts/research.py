#!/usr/bin/env python3
"""Usage: python backend/scripts/research.py INFY [--no-ingest] [--fast-stage2]
  --fast-stage2: run Stage 2 on CHEAP_MODEL only (use when the strong chain is overloaded); recorded as a fallback in the output"""
from __future__ import annotations
import sys, textwrap
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.research import run_research  # noqa: E402
from app.llm import LLMError  # noqa: E402
from app.ledger import fmt_range  # noqa: E402

W = lambda s, i="    ": textwrap.fill(s, 104, initial_indent=i, subsequent_indent=i)


def cites(c):
    seen = dict.fromkeys(f"[{x['doc'].split('__')[-1]} p{x['page']}]" for x in c.get("cites", []))
    return " ".join(seen)


def claim(c, bullet="•"):
    print(W(f"{bullet} {c['text']}  {cites(c)}", "  "))


def main(t: str, ingest: bool, fast: bool = False):
    from app import config
    try:
        r = run_research(t, do_ingest=ingest, stage2_models=[config.CHEAP_MODEL] if fast else None,
                         override_reason=f"manual --fast-stage2: Stage 2 forced onto {config.CHEAP_MODEL} because the strong chain was overloaded" if fast else None)
    except (LLMError, RuntimeError) as e:
        print(f"ERROR: {e}"); return 1
    v, m = r["view"], r["models"]
    print(f"\n==== {r['ticker']}  (stage1/1b model={m['cheap']}, stage2 model used={m['strong_used']}"
          f"{' — FALLBACK, requested ' + m['strong_requested'] if m['used_fallback'] else ''}) ====")
    print(f"reported data runs through: {r['ledger']['data_through']}")
    for key, title in [("business_snapshot", "BUSINESS"), ("financial_snapshot", "FINANCIALS"), ("trajectory", "TRAJECTORY"),
                       ("balance_sheet", "BALANCE SHEET"), ("cash_quality", "CASH QUALITY"), ("reconciliation", "RECONCILIATION")]:
        print(f"\n-- {title}")
        for c in v.get(key, []):
            claim(c)
    print("\n-- PROMISED vs DELIVERED  (verdicts assigned by code)")
    for p in v["promised_vs_delivered"]:
        rng = fmt_range(p)
        rep = f"  (reiterated {', '.join(p['reiterated_in'])})" if p["reiterated_in"] else ""
        print(f"  [{(p['verdict'] or 'unscored').upper()}] {p['metric']} for {p['covers']}: guided {rng} {p.get('unit') or ''} in {p['quarter_said']}{rep}")
        print(W(f"“{p['promised']['quote']}” [{p['promised']['doc'].split('__')[-1]} p{p['promised']['page']}]", "     "))
        print(W(f"code: {p['detail']}", "     "))
        if p.get("actual"):
            print(W(f"actual: “{p['actual']['quote']}” [{p['actual']['doc'].split('__')[-1]} p{p['actual']['page']}]", "     "))
        if p.get("explanation"):
            print(W(f"note: {p['explanation']}", "     "))
    un = r["ledger"]["unscored_guidance"]
    print(f"\n-- QUALITATIVE / UNSCORED GUIDANCE ({len(un)}; no metric+period+number, not scored)")
    for g in un[:8]:
        print(W(f"• ({g['quarter_said']}) {g['text']} [{g['doc'].split('__')[-1]} p{g['page']}]", "  "))
    for key, title in [("narrative_vs_numbers", "NARRATIVE vs NUMBERS"), ("bull_case", "BULL"), ("bear_case", "BEAR")]:
        print(f"\n-- {title}")
        for c in v.get(key, []):
            claim(c, "+" if key == "bull_case" else "−" if key == "bear_case" else "•")
    s1_drop = sum(d["n_dropped"] for d in r["stage1"])
    print(f"\n-- CHECKS")
    print(f"  stage-1 items dropped (quote/numbers not on page): {s1_drop}   kept: {sum(d['n_items'] for d in r['stage1'])}")
    print(f"  stage-2 claims failing the quote check: {len(r['failed_claims'])}")
    print(f"  stage-2 claims removed for scope/period mixing: {len(r['consistency_flags'])}")
    print(f"  structured facts with value/scope corrections: {len(r['facts_flagged'])}")
    print(f"  conflicts (same metric+period+scope, different values): {len(r['ledger']['conflicts'])};  scope variants (standalone vs consolidated etc.): {len(r['ledger']['scope_variants'])}")
    for c in r["ledger"]["conflicts"] + r["ledger"]["scope_variants"]:
        print(W(f"~ {c['metric']} {c['period']}: " + "; ".join(f"{x['value']:g} {x.get('unit') or ''} ({x['scope']}, {x['doc'].split('__')[-1]} p{x['page']})" for x in c["facts"]), "    "))
    for f in r["failed_claims"]:
        print(W(f"✗ failed quote: {f.get('path')}: {f.get('text') or f.get('reason')}", "  "))
    for f in r["consistency_flags"]:
        print(W(f"⚑ {f['section']}: {f['reason']} — “{f['text']}”", "  "))
    print("\n-- TOKEN USAGE (fresh calls only; cached calls cost 0)")
    tot = 0
    for st, u in r["usage"].items():
        tot += u["prompt"] + u["output"] + u["thinking"]
        print(f"  {st:<22} {u['model']:<22} calls {u['calls']} (cached {u['cached_calls']})  in {u['prompt']:>8,}  out {u['output']:>7,}")
    print(f"  total fresh tokens: {tot:,}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], "--no-ingest" not in sys.argv, "--fast-stage2" in sys.argv))
