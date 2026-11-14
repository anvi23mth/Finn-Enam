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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "gemini-3.5-flash-lite")
STRONG_MODEL = os.getenv("STRONG_MODEL", "gemini-3.8-flash")
LLM_MIN_INTERVAL = float(os.getenv("LLM_MIN_INTERVAL", "4"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "6"))
CHUNK_PAGES = int(os.getenv("CHUNK_PAGES", "8"))
AR_MAX_PAGES = int(os.getenv("AR_MAX_PAGES", "48"))
CACHE_DIR = (DOCS_DIR.parent / "cache" / "llm")
RESEARCH_DIR = (DOCS_DIR.parent / "research")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_WAIT = float(os.getenv("LLM_MAX_WAIT", "120"))   # fail fast if the server asks us to wait longer than this
S2_MAX_CHARS = int(os.getenv("S2_MAX_CHARS", "48000"))    # cap on Stage-2 input (~12k tokens)
STRONG_MODEL_FALLBACKS = [m.strip() for m in os.getenv("STRONG_MODEL_FALLBACKS", "").split(",") if m.strip()]
STRONG_RETRIES = int(os.getenv("STRONG_RETRIES", "2"))   # retries per model before moving to the next fallback


def strong_chain() -> list:
    """STRONG_MODEL, then fallbacks, with CHEAP_MODEL always last so the run completes."""
    chain = []
    for m in [STRONG_MODEL, *STRONG_MODEL_FALLBACKS, CHEAP_MODEL]:
        if m not in chain:
            chain.append(m)
    return chain
