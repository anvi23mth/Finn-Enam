"""Single-worker background job queue (one analysis at a time keeps Gemini free-tier pacing safe). In-memory by design."""
from __future__ import annotations
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from . import config, store
from .llm import LLMError
from .research import DocumentsNotFound, run_research

_jobs: dict[str, dict] = {}
_q: queue.Queue = queue.Queue()
_lock = threading.Lock()
_worker: threading.Thread | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def submit(ticker: str) -> dict:
    """Returns the job dict, or raises queue.Full when the queue is at capacity. Re-uses an in-flight job for the same ticker."""
    global _worker
    with _lock:
        for j in _jobs.values():
            if j["ticker"] == ticker and j["status"] in ("queued", "running"):
                return j
        if sum(1 for j in _jobs.values() if j["status"] in ("queued", "running")) >= config.MAX_QUEUED_JOBS:
            raise queue.Full
        job = {"id": uuid.uuid4().hex[:12], "ticker": ticker, "status": "queued", "message": "waiting for the worker",
               "error": None, "error_code": None, "created_at": _now(), "started_at": None, "finished_at": None, "refunded": False}
        _jobs[job["id"]] = job
        while len(_jobs) > 60:                       # keep memory bounded
            _jobs.pop(next(iter(_jobs)))
        _q.put(job["id"])
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_loop, daemon=True, name="research-worker")
            _worker.start()
    return job


def get(job_id: str) -> dict | None:
    with _lock:
        j = _jobs.get(job_id)
        return dict(j) if j else None


def _set(job: dict, **kw) -> None:
    with _lock:
        job.update(kw)


def _loop() -> None:
    while True:
        jid = _q.get()
        with _lock:
            job = _jobs.get(jid)
        if not job:
            continue
        _set(job, status="running", started_at=_now(), message="starting")
        try:
            run_research(job["ticker"], progress=lambda m: _set(job, message=m))
            _set(job, status="done", message="finished", finished_at=_now())
        except DocumentsNotFound as e:
            store.refund()   # nothing was sent to the LLM
            _set(job, status="failed", error=str(e), error_code="documents_not_found", refunded=True, message="documents not found", finished_at=_now())
        except LLMError as e:
            _set(job, status="failed", error=f"The language-model step failed: {str(e)[:400]}", error_code="llm_error", message="analysis failed", finished_at=_now())
        except Exception as e:  # noqa: BLE001 - a job failure must never kill the worker
            _set(job, status="failed", error=f"{type(e).__name__}: {str(e)[:300]}", error_code="internal_error", message="analysis failed", finished_at=_now())
