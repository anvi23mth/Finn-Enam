"""Thin Gemini REST client: JSON output, on-disk cache, throttling, retry/backoff, token accounting."""
from __future__ import annotations
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
import httpx
from . import config
from .log import log

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_last_call = 0.0


class LLMError(Exception):
    pass


@dataclass
class Usage:
    """Token usage grouped by stage name."""
    stages: dict = field(default_factory=dict)

    def add(self, stage: str, model: str, u: dict, cached: bool):
        s = self.stages.setdefault(stage, {"model": model, "calls": 0, "cached_calls": 0, "prompt": 0, "output": 0, "thinking": 0})
        s["calls"] += 1
        if cached:
            s["cached_calls"] += 1
        else:
            s["prompt"] += u.get("promptTokenCount", 0)
            s["output"] += u.get("candidatesTokenCount", 0)
            s["thinking"] += u.get("thoughtsTokenCount", 0)


def cache_key(model: str, version: str, doc_hash: str, part: str, prompt: str) -> str:
    h = hashlib.sha256(f"{model}|{version}|{doc_hash}|{part}|{prompt}".encode()).hexdigest()
    return h[:40]


def _parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    return json.loads(t)


def call_json(*, model: str, system: str, prompt: str, version: str, doc_hash: str, part: str,
              stage: str, usage: Usage, retries: int | None = None) -> dict:
    """Cached JSON generation. Cache key = model + prompt version + document hash + part + full prompt."""
    key = cache_key(model, version, doc_hash, part, system + prompt)
    path = config.CACHE_DIR / f"{key}.json"
    if path.exists():
        log(f"  ✓ {stage} {part}: cache hit")
        rec = json.loads(path.read_text())
        usage.add(stage, model, rec["usage"], cached=True)
        return rec["result"]
    if not config.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set in backend/.env")

    global _last_call
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": 16384}}
    delay = 8.0
    last_err = ""
    max_retries = config.LLM_MAX_RETRIES if retries is None else retries
    for attempt in range(max_retries + 1):
        wait = config.LLM_MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        try:
            log(f"  → {stage} {part} [{model}] attempt {attempt + 1}/{max_retries + 1}, prompt ~{len(prompt) // 4:,} tokens")
            r = httpx.post(URL.format(model=model), json=body,
                           timeout=httpx.Timeout(config.LLM_TIMEOUT, connect=15),
                           headers={"x-goog-api-key": config.GEMINI_API_KEY})
        except httpx.HTTPError as e:
            last_err = f"{type(e).__name__}: {e}"
        else:
            if r.status_code == 200:
                data = r.json()
                cand = (data.get("candidates") or [{}])[0]
                text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
                if cand.get("finishReason") not in (None, "STOP"):
                    last_err = f"finishReason={cand.get('finishReason')}"
                else:
                    try:
                        result = _parse_json(text)
                    except json.JSONDecodeError as e:
                        last_err = f"invalid JSON from model: {e}"
                    else:
                        u = data.get("usageMetadata", {})
                        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps({"model": model, "version": version, "usage": u, "result": result}))
                        usage.add(stage, model, u, cached=False)
                        log(f"  ✓ {stage} {part}: ok, in {u.get('promptTokenCount', 0):,} / out {u.get('candidatesTokenCount', 0):,} / thinking {u.get('thoughtsTokenCount', 0):,}")
                        return result
            elif r.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                m = re.search(r'retry in ([\d.]+)s', r.text) or re.search(r'"retryDelay":\s*"([\d.]+)s"', r.text)
                if m:
                    delay = max(delay, float(m.group(1)) + 1)
                if r.status_code == 429 and (delay > config.LLM_MAX_WAIT or "PerDay" in r.text):
                    raise LLMError(f"Gemini quota exhausted for {model} (HTTP 429, server asked to wait ~{delay:.0f}s): {r.text[:500]}")
            else:  # 400/401/403/404: not retryable — surface verbatim
                raise LLMError(f"Gemini API HTTP {r.status_code} for model {model}: {r.text[:600]}")
        log(f"  ! {stage} {part}: {last_err[:200]}")
        if attempt < max_retries:
            log(f"    retrying in {delay:.0f}s")
            time.sleep(delay)
            delay = min(delay * 2, 90)
    raise LLMError(f"Gemini call failed after {max_retries + 1} attempts ({model}, {part}): {last_err}")


def call_chain(*, models: list, system: str, prompt: str, version: str, doc_hash: str, part: str,
               stage: str, usage: Usage) -> tuple:
    """Try models in order; returns (result, model_actually_used).
    Models are tried in order; for each, a cached result is used if present, otherwise a live call is made, moving on after retries are exhausted (503/timeout/429/quota/model errors).
    Earlier models get config.STRONG_RETRIES retries; the last model gets the full LLM_MAX_RETRIES."""
    errors = []
    for i, m in enumerate(models):
        last = i == len(models) - 1
        if (config.CACHE_DIR / f"{cache_key(m, version, doc_hash, part, system + prompt)}.json").exists():
            # cache hit for THIS model only; a cached fallback result is not used while an earlier model might still work
            return call_json(model=m, system=system, prompt=prompt, version=version, doc_hash=doc_hash, part=part,
                             stage=stage, usage=usage), m
        try:
            res = call_json(model=m, system=system, prompt=prompt, version=version, doc_hash=doc_hash, part=part,
                            stage=stage, usage=usage, retries=config.LLM_MAX_RETRIES if last else config.STRONG_RETRIES)
            if i:
                log(f"  ⚠ {stage}: primary '{models[0]}' unavailable; used fallback '{m}'")
            return res, m
        except LLMError as e:
            errors.append(f"{m}: {str(e)[:220]}")
            log(f"  ✗ {stage}: {m} failed -> {'giving up' if last else 'trying next model'}")
    raise LLMError("all models in the chain failed: " + " | ".join(errors))
