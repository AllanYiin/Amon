#!/usr/bin/env python3
"""Heuristic linter for search query batches.

Usage:
  python scripts/lint_query_batches.py queries.txt

The input file should contain one query per line. Blank lines and lines
starting with "#" are ignored. Markdown list markers are tolerated.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


LIST_PREFIX = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
OPERATOR_RE = re.compile(r"\b(site|filetype|before|after):", re.IGNORECASE)


@dataclass
class Finding:
    level: str
    line_no: int
    message: str

    def format(self, path: Path) -> str:
        return f"[{self.level}] {path}:{self.line_no}: {self.message}"


def normalize_line(raw: str) -> str:
    line = raw.strip()
    line = LIST_PREFIX.sub("", line)
    return line.strip()


def bare_term_count(query: str) -> int:
    stripped = re.sub(r'"[^"]+"', " ", query)
    stripped = OPERATOR_RE.sub(" ", stripped)
    stripped = re.sub(r"\b(?:OR|AND)\b", " ", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"[()]", " ", stripped)
    tokens = [token for token in stripped.split() if token and not token.startswith("-")]
    return len(tokens)


def lint_queries(path: Path) -> tuple[list[Finding], list[Finding]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    errors: list[Finding] = []
    warnings: list[Finding] = []
    seen: dict[str, int] = {}

    for idx, raw in enumerate(lines, start=1):
        query = normalize_line(raw)
        if not query or query.startswith("#"):
            continue

        normalized = re.sub(r"\s+", " ", query.lower()).strip()
        if normalized in seen:
            errors.append(Finding("ERROR", idx, f"Duplicate query; first seen on line {seen[normalized]}"))
        else:
            seen[normalized] = idx

        if len(query.split()) > 10:
            warnings.append(Finding("WARN", idx, "Looks like a full sentence; consider splitting into shorter query families"))

        term_count = bare_term_count(query)
        if term_count > 4:
            warnings.append(Finding("WARN", idx, f"Has {term_count} bare terms; consider reducing to 2-3 core concepts"))

        site_count = len(re.findall(r"\bsite:[^\s]+", query, flags=re.IGNORECASE))
        if site_count > 1:
            warnings.append(Finding("WARN", idx, "Contains more than one site restriction; verify this is intentional"))

        if re.search(r"\b(?:before|after):", query, flags=re.IGNORECASE):
            warnings.append(Finding("WARN", idx, "Uses before:/after:; treat as heuristic and verify with current search-engine behavior"))

        if re.search(r"\bfiletype:\s*$", query, flags=re.IGNORECASE):
            warnings.append(Finding("WARN", idx, "filetype: is present without an extension"))

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint search query batches")
    parser.add_argument("path", help="Path to a UTF-8 text or markdown file with one query per line")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return 1

    try:
        errors, warnings = lint_queries(path)
    except UnicodeDecodeError as exc:
        print(f"[ERROR] Input must be UTF-8 text: {exc}")
        return 1

    for finding in errors + warnings:
        print(finding.format(path))

    print(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
