from __future__ import annotations
import gc
import json
from pathlib import Path
import pdfplumber

BATCH = 20


def extract_pdf(pdf_path: Path, force: bool = False) -> tuple[Path, int, str]:
    """Page-by-page text -> <name>.json. Returns (json_path, n_pages, 'cached'|'extracted')."""
    out = pdf_path.with_suffix(".json")
    if out.exists() and not force and out.stat().st_mtime >= pdf_path.stat().st_mtime:
        return out, len(json.loads(out.read_text())["pages"]), "cached"
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
    # Re-open the file every BATCH pages: pdfminer caches fonts/objects for the life of the document, which for a
    # 460-page annual report grows to several GB. Short-lived documents keep peak memory small (Render free tier = 512 MB).
    for start in range(0, n_pages, BATCH):
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(start, min(start + BATCH, n_pages)):
                page = pdf.pages[i]
                try:
                    text = page.extract_text() or ""
                except Exception as e:  # one bad page must not kill the document
                    pages.append({"page": i + 1, "text": "", "error": f"{type(e).__name__}: {e}"})
                    continue
                finally:
                    page.flush_cache()
                pages.append({"page": i + 1, "text": text})
        gc.collect()
    out.write_text(json.dumps({"source_pdf": pdf_path.name, "n_pages": len(pages), "pages": pages}, ensure_ascii=False))
    return out, len(pages), "extracted"
