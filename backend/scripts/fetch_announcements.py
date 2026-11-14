"""Fetch recent corporate announcements for the portfolio from screener.in.
Usage: python -m scripts.fetch_announcements [--days N] [--exchanges] [TICKER ...]
--exchanges also tries NSE/BSE (skipped for the rest of the run once one returns 403)."""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import announcements as ann, config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--exchanges", action="store_true", help="also try NSE/BSE (optional; skipped on 403)")
    args = ap.parse_args()
    portfolio = ann.load_portfolio()
    tickers = [t.upper() for t in args.tickers] or portfolio
    ex = ann.Exchanges(args.exchanges)
    results, failures = {}, {}
    for t in tickers:
        try:
            r = results[t] = ann.fetch_ticker(t, ex, args.days)
            print(f"{t:12s} +{r['new']} new, {r['total']} kept", flush=True)
        except Exception as e:
            failures[t] = str(e)
            print(f"{t:12s} FAILED: {e}", flush=True)
        time.sleep(config.REQUEST_DELAY)
    allr = ann.write_combined(portfolio)

    print("\n=== Announcements per ticker (span = days covered by what screener returned) ===")
    for t in tickers:
        n = len(ann.load_snapshot(t)["announcements"])
        sp = results[t]["span_days"] if t in results else "-"
        print(f"{t:12s} {n:3d}   oldest {sp}d ago" + ("   FETCH FAILED" if t in failures else ""))
    print(f"\nFailures: {len(failures)}")
    for t, e in failures.items():
        print(f"  {t}: {e}")
    if ex.skip_reason:
        print(f"Note: {ex.skip_reason}")
    print(f"\n=== 10 most recent across portfolio (of {len(allr)}) ===")
    for a in allr[:10]:
        print(f"{a['datetime'][:16]}  {a['ticker']:11s} {a['subject'][:85]}\n    {a['attachment']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
