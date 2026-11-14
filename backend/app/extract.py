from __future__ import annotations
import json
from pathlib import Path
import pdfplumber


def extract_pdf(pdf_path: Path, force: bool = False) -> tuple[Path, int, str]:
    """Page-by-page text -> <name>.json. Returns (json_path, n_pages, 'cached'|'extracted')."""
    out = pdf_path.with_suffix(".json")
    if out.exists() and not force and out.stat().st_mtime >= pdf_path.stat().st_mtime:
        return out, len(json.loads(out.read_text())["pages"]), "cached"
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:  # one bad page must not kill the document
                text = ""
                pages.append({"page": i, "text": text, "error": f"{type(e).__name__}: {e}"})
                continue
            pages.append({"page": i, "text": text})
    out.write_text(json.dumps({"source_pdf": pdf_path.name, "n_pages": len(pages), "pages": pages}, ensure_ascii=False))
    return out, len(pages), "extracted"
