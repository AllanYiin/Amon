#!/usr/bin/env python3
"""Scan repository text files for Unicode control characters (Trojan Source)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BIDI_CONTROLS = {
    "\u202A",  # LRE
    "\u202B",  # RLE
    "\u202D",  # LRO
    "\u202E",  # RLO
    "\u202C",  # PDF
    "\u2066",  # LRI
    "\u2067",  # RLI
    "\u2068",  # FSI
    "\u2069",  # PDI
}

ZERO_WIDTH = {
    "\u200B",  # ZWSP
    "\u200C",  # ZWNJ
    "\u200D",  # ZWJ
    "\u2060",  # WJ
    "\uFEFF",  # BOM
}

DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".ruff_cache",
}

SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".whl",
    ".egg",
    ".mp3",
    ".mp4",
    ".mov",
    ".wav",
    ".pyc",
    ".so",
    ".dylib",
    ".exe",
}

SKIP_SUFFIXES = {
    ".min.js",
    ".min.css",
}


@dataclass
class Finding:
    path: Path
    line_no: int
    column: int
    codepoint: str
    preview: str


def is_binary(data: bytes) -> bool:
    return b"\x00" in data


def iter_text_files(root: Path, exclude: set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            if path.name in exclude:
                continue
            continue
        if any(part in exclude for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_EXTENSIONS:
            continue
        if any(path.name.endswith(suffix) for suffix in SKIP_SUFFIXES):
            continue
        yield path


def scan_file(path: Path, include_zero_width: bool) -> list[Finding]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if is_binary(data):
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []

    targets = BIDI_CONTROLS | (ZERO_WIDTH if include_zero_width else set())
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for index, char in enumerate(line):
            if char in targets:
                codepoint = f"U+{ord(char):04X}"
                preview = line.strip()
                findings.append(
                    Finding(
                        path=path,
                        line_no=line_no,
                        column=index + 1,
                        codepoint=codepoint,
                        preview=preview,
                    )
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for Unicode control characters.")
    parser.add_argument("--root", default=".", help="Root directory to scan")
    parser.add_argument(
        "--include-zero-width",
        action="store_true",
        help="Also flag zero-width characters",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional directories to exclude",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    exclude = set(DEFAULT_EXCLUDES)
    exclude.update(args.exclude)

    all_findings: list[Finding] = []
    for path in iter_text_files(root, exclude):
        all_findings.extend(scan_file(path, args.include_zero_width))

    if all_findings:
        for finding in all_findings:
            rel_path = finding.path.relative_to(root)
            print(
                f"{rel_path}:{finding.line_no}:{finding.column} "
                f"{finding.codepoint} {finding.preview}"
            )
        return 1

    print("No Unicode control characters found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
