from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from context_store import Chunk, ContextStore


_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


@dataclass
class BM25Index:
    """A tiny, dependency-free BM25 implementation.

    It's not meant to beat industrial search engines; it's meant to quickly narrow
    candidates when you have thousands of chunks.
    """

    store: ContextStore
    k1: float = 1.5
    b: float = 0.75

    _doc_freq: Counter = None  # type: ignore
    _doc_len: List[int] = None  # type: ignore
    _avgdl: float = 0.0
    _N: int = 0
    _tokenized: List[List[str]] = None  # type: ignore

    def build(self) -> "BM25Index":
        docs = [c.text for c in self.store.chunks]
        self._tokenized = [_tokenize(d) for d in docs]
        self._doc_len = [len(toks) for toks in self._tokenized]
        self._avgdl = sum(self._doc_len) / max(1, len(self._doc_len))
        self._N = len(self._tokenized)

        df = Counter()
        for toks in self._tokenized:
            df.update(set(toks))
        self._doc_freq = df
        return self

    def search(self, query: str, *, top_k: int = 10) -> List[Tuple[int, float]]:
        if self._tokenized is None:
            raise RuntimeError("Index not built. Call .build() first.")

        q_toks = _tokenize(query)
        if not q_toks:
            return []

        scores = []
        for i, doc_toks in enumerate(self._tokenized):
            tf = Counter(doc_toks)
            dl = self._doc_len[i]
            score = 0.0
            for term in q_toks:
                df = self._doc_freq.get(term, 0)
                if df == 0:
                    continue
                idf = math.log(1 + (self._N - df + 0.5) / (df + 0.5))
                freq = tf.get(term, 0)
                denom = freq + self.k1 * (1 - self.b + self.b * (dl / (self._avgdl or 1.0)))
                score += idf * (freq * (self.k1 + 1)) / (denom or 1.0)
            if score != 0.0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


def bm25_prefilter(store: ContextStore, query: str, *, top_k: int = 20) -> List[Chunk]:
    idx = BM25Index(store).build()
    hits = idx.search(query, top_k=top_k)
    return [store.chunks[i] for i, _ in hits]
