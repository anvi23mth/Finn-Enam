from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DOCS_DIR = (BACKEND_DIR / os.getenv("DOCS_DIR", "../data/docs")).resolve()
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
CONCALL_COUNT = int(os.getenv("CONCALL_COUNT", "4"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
