#!/usr/bin/env python3
"""Fail if text contains bullet lists or ordered lists."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LIST_PATTERNS = [
    re.compile(r"^\s*[-*+]\s+"),
    re.compile(r"^\s*\d+[.)]\s+"),
    re.compile(r"^\s*[一二三四五六七八九十]+[、.]\s*"),
    re.compile(r"^\s*[（(]?\d+[）)]\s+"),
    re.compile(r"^\s*[•●○▪◦]\s+"),
]


def find_violations(text: str) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    in_fence = False
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if any(pattern.search(line) for pattern in LIST_PATTERNS):
            violations.append((index, line.rstrip()))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check text for bullet or ordered list markers.")
    parser.add_argument("path", nargs="?", help="Optional file path. Reads stdin when omitted.")
    args = parser.parse_args()

    if args.path:
        text = Path(args.path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    violations = find_violations(text)
    if not violations:
        print("OK: no list markers found")
        return 0

    print("FOUND_LIST_MARKERS")
    for line_no, line in violations:
        print(f"{line_no}: {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
