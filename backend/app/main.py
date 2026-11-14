from __future__ import annotations
from dataclasses import asdict
from fastapi import FastAPI
from .ingest import ingest

app = FastAPI(title="FINN backend")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ingest/{ticker}")
def ingest_ticker(ticker: str):
    return asdict(ingest(ticker))


@app.post("/research/{ticker}")
def research_ticker(ticker: str):
    from .research import run_research
    from .llm import LLMError
    from fastapi import HTTPException
    try:
        return run_research(ticker)
    except (LLMError, RuntimeError) as e:
        raise HTTPException(status_code=502, detail=str(e))
