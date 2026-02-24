"""Syntax-level validators for ingested artifact files."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run_command(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return False, str(exc)
    if completed.returncode == 0:
        return True, "ok"
    message = (completed.stderr or completed.stdout or "validation failed").strip()
    return False, message[:400]


def run_validators(file_path: Path) -> list[dict[str, Any]]:
    """Run syntax validators by file extension."""

    suffix = file_path.suffix.lower()
    checks: list[dict[str, Any]] = []

    if suffix == ".py":
        ok, message = _run_command([sys.executable, "-m", "py_compile", str(file_path)])
        checks.append({"tool": "py_compile", "status": "valid" if ok else "invalid", "message": message})
        return checks

    if suffix == ".js":
        node_bin = shutil.which("node")
        if not node_bin:
            checks.append({"tool": "node --check", "status": "skipped", "message": "node not found"})
            return checks
        ok, message = _run_command([node_bin, "--check", str(file_path)])
        checks.append({"tool": "node --check", "status": "valid" if ok else "invalid", "message": message})
        return checks

    if suffix == ".ts":
        tsc_bin = shutil.which("tsc")
        if not tsc_bin:
            checks.append({"tool": "tsc --noEmit", "status": "skipped", "message": "tsc not found"})
            return checks
        ok, message = _run_command([tsc_bin, "--noEmit", str(file_path)])
        checks.append({"tool": "tsc --noEmit", "status": "valid" if ok else "invalid", "message": message})
        return checks

    checks.append({"tool": "none", "status": "skipped", "message": "no validator for extension"})
    return checks
