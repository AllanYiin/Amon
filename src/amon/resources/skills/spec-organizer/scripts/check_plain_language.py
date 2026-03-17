#!/usr/bin/env python3
"""Check whether a user-facing spec still contains banned technical terms."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


EN_PATTERNS = [
    r"\bapi\b",
    r"\bdb\b",
    r"\bdatabase\b",
    r"\bbackend\b",
    r"\bfrontend\b",
    r"\bschema\b",
    r"\bqps\b",
    r"\bstate machine\b",
    r"\bendpoint\b",
    r"\bmigration\b",
    r"\bcache\b",
    r"\bqueue\b",
    r"\bcron\b",
    r"\bbatch job\b",
    r"\bstreaming\b",
    r"\btoken\b",
    r"\bcrud\b",
    r"\bauth\b",
    r"\bauthorization\b",
    r"\bwebsocket\b",
    r"\bllm\b",
    r"\bmodel\b",
]

ZH_TERMS = [
    "資料庫",
    "後端",
    "前端",
    "狀態機",
    "端點",
    "快取",
    "佇列",
    "批次工作",
    "串流",
    "權限驗證",
    "資料表",
]


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_matches(text: str) -> list[tuple[int, str]]:
    matches: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        for pattern in EN_PATTERNS:
            matched = re.search(pattern, lowered, flags=re.IGNORECASE)
            if matched:
                matches.append((line_no, matched.group(0)))
        for term in ZH_TERMS:
            if term in line:
                matches.append((line_no, term))
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Check banned technical terms in a non-technical spec")
    parser.add_argument("path", help="Path to the markdown/text file to scan")
    args = parser.parse_args()

    text = load_text(Path(args.path).resolve())
    matches = find_matches(text)

    if not matches:
        print("PASS: no banned technical terms found")
        return 0

    print("FAIL: banned technical terms found")
    for line_no, term in matches:
        print(f"  line {line_no}: {term}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
