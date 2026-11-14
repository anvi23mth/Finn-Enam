"""Classify announcements (cheap model, batched, cached) and extract results tables.
Usage: python -I scripts/classify_announcements.py [--force] [--results TMPV HDFCBANK] [--skip-classify]"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import announce_intel as ai  # noqa: E402
from app.llm import LLMError  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-classify", action="store_true")
    ap.add_argument("--results", nargs="*", default=[])
    args = ap.parse_args()
    try:
        if not args.skip_classify:
            c = ai.classify_all(args.force)
            print(f"classified {c['count']} (models: {c['models']}); unvalidated: {len(c['unvalidated'])}")
        classified = json.loads((ai.ANN_DIR / "classified.json").read_text())
        for r in ai.run_results([t.upper() for t in args.results], classified):
            print(f"results {r['ticker']}: {r['status']}" + (f" — {r.get('error') or r.get('not_found_or_unverified')}" if r["status"] != "ok" else ""))
    except LLMError as e:
        print(f"LLM FAILED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
