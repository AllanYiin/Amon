from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from context_store import Chunk, ContextStore


def _try_pypdf_extract(pdf_path: Path) -> List[str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        from PyPDF2 import PdfReader  # type: ignore

    reader = PdfReader(str(pdf_path))
    pages_text: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        # Normalise some whitespace
        t = re.sub(r"\s+", " ", t).strip()
        pages_text.append(t)
    return pages_text


def load_pdf_as_chunks(
    pdf_path: str,
    *,
    chunk_by: str = "page",
    max_chars_per_chunk: int = 80_000,
    keep_empty_pages: bool = False,
    pdf_id: Optional[str] = None,
) -> ContextStore:
    """Load a PDF into a ContextStore.

    Parameters
    ----------
    pdf_path:
        Path to the PDF.
    chunk_by:
        - "page": one chunk per page.
        - "chars": concatenate pages and re-chunk by characters.
    max_chars_per_chunk:
        Only used for chunk_by="chars".

    Returns
    -------
    ContextStore with `Chunk` objects, each with a `source` label.
    """

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = _try_pypdf_extract(path)
    label = pdf_id or path.name

    chunks: List[Chunk] = []

    if chunk_by == "page":
        for idx, text in enumerate(pages, start=1):
            if not text and not keep_empty_pages:
                continue
            chunks.append(Chunk(source=f"pdf:{label}#page={idx}", text=text))
        return ContextStore(chunks)

    if chunk_by == "chars":
        joined = "\n\n".join([t for t in pages if t or keep_empty_pages])
        # Re-chunk
        pos = 0
        chunk_idx = 0
        while pos < len(joined):
            chunk = joined[pos : pos + max_chars_per_chunk]
            chunks.append(Chunk(source=f"pdf:{label}#chunk={chunk_idx}", text=chunk))
            pos += max_chars_per_chunk
            chunk_idx += 1
        return ContextStore(chunks)

    raise ValueError(f"Unknown chunk_by={chunk_by!r}. Use 'page' or 'chars'.")
