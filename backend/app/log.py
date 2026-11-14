from __future__ import annotations
import sys
import time

_t0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - _t0:6.0f}s] {msg}", file=sys.stderr, flush=True)
