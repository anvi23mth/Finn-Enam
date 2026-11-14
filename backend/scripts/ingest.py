#!/usr/bin/env python3
"""Usage: python backend/scripts/ingest.py INFY [DEEPAKNTR ...]"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ingest import ingest  # noqa: E402
from app import config  # noqa: E402


def main(tickers: list[str]) -> int:
    failures = 0
    for t in tickers:
        rep = ingest(t)
        print(f"\n=== {rep.ticker} ===")
        print(f"page: {rep.page_url or '—'}")
        print(f"docs found: {len(rep.docs)}   (saved under {config.DOCS_DIR / rep.ticker})")
        for d in rep.docs:
            if d.error:
                failures += 1
                print(f"  ✗ {d.kind:<13} {d.label:<18} FAILED  {d.error}\n      {d.url}")
            else:
                print(f"  ✓ {d.kind:<13} {d.label:<18} {d.pages:>4} pages ({d.empty_pages} empty)  [{d.download_status}/{d.extract_status}]  {d.pdf}")
        for e in rep.errors:
            failures += 1
            print(f"  ! {e}")
    print(f"\nfailures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
