#!/usr/bin/env python3
"""Copy finished results into backend/seed/research (served on a fresh deploy) and public/seed/research (static fallback for the app).
Usage: python backend/scripts/make_seed.py INFY DEEPAKNTR"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

NAMES = {"INFY": "Infosys", "DEEPAKNTR": "Deepak Nitrite"}   # fallback when a result predates the `company` field
ROOT = config.BACKEND_DIR.parent

for t in map(str.upper, sys.argv[1:] or sys.exit(__doc__)):
    src = config.RESEARCH_DIR / f"{t}.json"
    d = json.loads(src.read_text())
    d.setdefault("company", NAMES.get(t))
    d.setdefault("generated_at", datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"))
    d.pop("ingest", None); d.pop("facts_flagged", None)          # bulky provenance; not needed to render
    for s in d.get("stage1", []):
        s.pop("dropped", None)
    for dest in (config.SEED_DIR, ROOT / "public" / "seed" / "research"):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{t}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    print(f"{t}: {src.stat().st_size // 1024} KB -> seed ({(config.SEED_DIR / f'{t}.json').stat().st_size // 1024} KB), company={d['company']}")
