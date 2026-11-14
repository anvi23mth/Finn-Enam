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
