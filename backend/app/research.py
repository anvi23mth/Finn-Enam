from __future__ import annotations
import json
from dataclasses import asdict
from . import config, llm, stage1, stage1b, stage2, ledger as ledger_mod
from .docs import load_docs
from .ingest import ingest
from .log import log


def run_research(ticker: str, do_ingest: bool = True, stage2_models: list | None = None, override_reason: str | None = None) -> dict:
    t = ticker.upper()
    usage = llm.Usage()
    ing = asdict(ingest(t)) if do_ingest else None
    docs = load_docs(t)
    if not docs:
        raise RuntimeError(f"no ingested documents for {t}" + (f": {ing['errors']}" if ing else ""))
    by_id = {d.id: d for d in docs}
    s1 = [stage1.run_ar(d, usage) if d.kind == "annual_report" else stage1.run_concall(d, usage) for d in docs]
    log(f"stage 1 done: {sum(len(d['items']) for d in s1)} verified items, {sum(len(d['dropped']) for d in s1)} dropped")
    facts = stage1b.run(by_id, s1, usage)
    led = ledger_mod.build(facts)
    log(f"ledger: {len(led['pairs'])} guidance pairs, {len(led['actuals'])} actuals, {len(led['conflicts'])} conflicts, {len(led['scope_variants'])} scope variants, data through {led['data_through']}")
    combined_hash = "|".join(sorted(d.sha for d in docs))
    raw, strong_used = stage2.run(t, facts, led, usage, combined_hash, models=stage2_models)
    log(f"stage 2 model actually used: {strong_used}; verifying citations")
    failed: list = []
    view = stage2.verify_tree(raw, by_id, failed)
    flags: list = []
    fb = {f["fid"]: f for f in facts}
    view = stage2.check_consistency(view, fb, flags)
    expl = {e["pair_id"]: e for e in (view.pop("guidance_explanations", None) or []) if isinstance(e, dict) and "pair_id" in e}
    view["promised_vs_delivered"] = [{**p, "explanation": (expl.get(p["id"]) or {}).get("text")} for p in led["pairs"]]
    out = {"ticker": t,
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
