from __future__ import annotations
import json
from dataclasses import asdict
from . import config, llm, stage1, stage2
from .log import log
from .docs import load_docs
from .ingest import ingest


def run_research(ticker: str, do_ingest: bool = True, stage2_models: list | None = None, override_reason: str | None = None) -> dict:
    t = ticker.upper()
    usage = llm.Usage()
    ing = asdict(ingest(t)) if do_ingest else None
    docs = load_docs(t)
    if not docs:
        raise RuntimeError(f"no ingested documents for {t}" + (f": {ing['errors']}" if ing else ""))
    s1 = []
    for d in docs:
        s1.append(stage1.run_ar(d, usage) if d.kind == "annual_report" else stage1.run_concall(d, usage))
    # last 4 concalls only, oldest -> newest by quarter label order from filename month is unreliable; keep file order
    combined_hash = "|".join(sorted(d.sha for d in docs))
    log(f"stage 1 done: {sum(len(d['items']) for d in s1)} verified items, {sum(len(d['dropped']) for d in s1)} dropped")
    raw, strong_used = stage2.run(t, s1, usage, combined_hash, models=stage2_models)
    log(f"stage 2 model actually used: {strong_used}")
    log("stage 2 done; verifying citations")
    failed: list = []
    by_id = {d.id: d for d in docs}
    view = stage2.verify_tree(raw, by_id, failed)
    out = {"ticker": t, "models": {"cheap": config.CHEAP_MODEL, "strong_requested": config.STRONG_MODEL, "strong_used": strong_used,
                         "strong_chain": stage2_models or config.strong_chain(), "used_fallback": strong_used != config.STRONG_MODEL,
                         "stage2_override": override_reason}, "view": view,
           "failed_claims": failed,
           "stage1": [{k: v for k, v in d.items() if k != "items"} | {"n_items": len(d["items"]), "n_dropped": len(d["dropped"]),
                                                                      "dropped": d["dropped"]} for d in s1],
           "usage": usage.stages, "ingest": ing}
    config.RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    (config.RESEARCH_DIR / f"{t}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out
