"""Shared JSON storage helpers for manifest v1 repositories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..fs.atomic import atomic_write_text


def read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
