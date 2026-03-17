from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass
class Chunk:
    """A single chunk of the overall context.

    `source` should be something like:
    - "pdf:mydoc.pdf#page=12"
    - "file:src/app/main.py"
    - "text:chunk=7"
    """

    source: str
    text: str


class ContextStore:
    """Holds an arbitrarily long prompt as an *external environment*.

    This mirrors the RLM idea: the model doesn't see the whole prompt; it sees
    metadata and can programmatically pull slices.
    """

    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self.chunks: List[Chunk] = list(chunks)

    @classmethod
    def from_text(cls, text: str, *, chunk_chars: int = 120_000) -> "ContextStore":
        chunks: List[Chunk] = []
        for i in range(0, len(text), chunk_chars):
            chunks.append(Chunk(source=f"text:chunk={i//chunk_chars}", text=text[i : i + chunk_chars]))
        return cls(chunks)

    def total_chars(self) -> int:
        return sum(len(c.text) for c in self.chunks)

    def chunk_lengths(self) -> List[int]:
        return [len(c.text) for c in self.chunks]

    def head(self, n_chars: int = 2000) -> str:
        if not self.chunks:
            return ""
        return self.chunks[0].text[:n_chars]

    def tail(self, n_chars: int = 2000) -> str:
        if not self.chunks:
            return ""
        return self.chunks[-1].text[-n_chars:]

    def get_chunk(self, idx: int) -> Chunk:
        return self.chunks[idx]

    def find_regex(
        self,
        pattern: str,
        *,
        flags: int = re.IGNORECASE,
        max_hits: int = 50,
        window: int = 200,
    ) -> List[Tuple[int, int, str]]:
        """Return (chunk_idx, char_pos, snippet) for regex matches."""
        rx = re.compile(pattern, flags)
        hits: List[Tuple[int, int, str]] = []
        for i, ch in enumerate(self.chunks):
            for m in rx.finditer(ch.text):
                start = max(m.start() - window, 0)
                end = min(m.end() + window, len(ch.text))
                snippet = ch.text[start:end]
                hits.append((i, m.start(), snippet))
                if len(hits) >= max_hits:
                    return hits
        return hits

    def grep_keywords(
        self,
        keywords: Sequence[str],
        *,
        case_sensitive: bool = False,
        max_chunks: int = 200,
    ) -> List[int]:
        """Return chunk indices that contain ANY keyword."""
        if not keywords:
            return []
        kws = list(keywords)
        out: List[int] = []
        for i, ch in enumerate(self.chunks):
            hay = ch.text if case_sensitive else ch.text.lower()
            if any((kw if case_sensitive else kw.lower()) in hay for kw in kws):
                out.append(i)
                if len(out) >= max_chunks:
                    break
        return out

    def describe(self, *, max_sources: int = 12) -> str:
        """Compact description string suitable for root LM system prompt."""
        lines = [
            f"ContextStore: chunks={len(self.chunks)}, total_chars={self.total_chars():,}",
            f"chunk_lengths={self.chunk_lengths()[:max_sources]}" + (" ..." if len(self.chunks) > max_sources else ""),
            "sample_sources="
            + ", ".join(c.source for c in self.chunks[: max_sources])
            + (" ..." if len(self.chunks) > max_sources else ""),
        ]
        return "\n".join(lines)


def is_probably_text_file(path: str, *, max_bytes: int = 1_000_000) -> bool:
    """Heuristic: skip binary/huge files."""
    try:
        st = os.stat(path)
        if st.st_size > max_bytes:
            return False
        with open(path, "rb") as f:
            head = f.read(2048)
        if b"\x00" in head:
            return False
        return True
    except OSError:
        return False
