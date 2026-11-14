from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime, timezone
from . import config, llm, stage1, stage1b, stage2, ledger as ledger_mod
from .docs import load_docs
from .ingest import ingest
from .log import log


class DocumentsNotFound(RuntimeError):
    """No usable annual report / concall documents for the ticker (nothing was sent to the LLM)."""


def run_research(ticker: str, do_ingest: bool = True, stage2_models: list | None = None, override_reason: str | None = None,
                 progress=None) -> dict:
    say = progress or (lambda m: None)
    t = ticker.upper()
    usage = llm.Usage()
    ing = asdict(ingest(t, progress=say)) if do_ingest else None
    docs = load_docs(t)
    if not docs:
        why = "; ".join(ing["errors"]) if ing and ing["errors"] else "no documents downloaded"
        raise DocumentsNotFound(f"Could not find an annual report or concall transcripts for '{t}' on screener.in ({why}). "
                                f"Check that it is a listed NSE symbol that screener.in covers.")
    by_id = {d.id: d for d in docs}
    n_calls = sum(1 for d in docs if d.kind == "concall")
    s1, seen = [], 0
    for d in docs:
        if d.kind == "annual_report":
            say("extracting annual report")
            s1.append(stage1.run_ar(d, usage))
        else:
            seen += 1
            say(f"extracting concall {seen} of {n_calls}")
            s1.append(stage1.run_concall(d, usage))
    log(f"stage 1 done: {sum(len(d['items']) for d in s1)} verified items, {sum(len(d['dropped']) for d in s1)} dropped")
    say("structuring facts (scope, period, values)")
    facts = stage1b.run(by_id, s1, usage)
    led = ledger_mod.build(facts)
    log(f"ledger: {len(led['pairs'])} guidance pairs, {len(led['actuals'])} actuals, {len(led['conflicts'])} conflicts, {len(led['scope_variants'])} scope variants, data through {led['data_through']}")
    combined_hash = "|".join(sorted(d.sha for d in docs))
    say("writing analysis")
    raw, strong_used = stage2.run(t, facts, led, usage, combined_hash, models=stage2_models)
    log(f"stage 2 model actually used: {strong_used}; verifying citations")
    say("verifying citations")
    failed: list = []
    view = stage2.verify_tree(raw, by_id, failed)
    flags: list = []
    fb = {f["fid"]: f for f in facts}
    view = stage2.check_consistency(view, fb, flags)
    expl = {e["pair_id"]: e for e in (view.pop("guidance_explanations", None) or []) if isinstance(e, dict) and "pair_id" in e}
    view["promised_vs_delivered"] = [{**p, "explanation": None if p["verdict"] == "revised" else (expl.get(p["id"]) or {}).get("text")} for p in led["pairs"]]
    out = {"ticker": t, "company": (ing or {}).get("company"), "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "warnings": [e for e in ((ing or {}).get("errors") or [])],
           "models": {"cheap": config.CHEAP_MODEL, "strong_requested": config.STRONG_MODEL, "strong_used": strong_used,
                      "strong_chain": stage2_models or config.strong_chain(), "used_fallback": strong_used != config.STRONG_MODEL,
                      "stage2_override": override_reason},
           "view": view, "failed_claims": failed, "consistency_flags": flags,
           "ledger": {k: led[k] for k in ("data_through", "unscored_guidance", "conflicts", "scope_variants")},
           "stage1": [{k: v for k, v in d.items() if k != "items"} | {"n_items": len(d["items"]), "n_dropped": len(d["dropped"]),
                                                                      "dropped": d["dropped"]} for d in s1],
           "facts_flagged": [{"fid": f["fid"], "flags": f["flags"], "quote": f.get("quote")} for f in facts if f.get("flags")],
           "usage": usage.stages, "ingest": ing}
    config.RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    (config.RESEARCH_DIR / f"{t}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out
