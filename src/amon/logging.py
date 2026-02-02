"""JSONL logging helpers for Amon."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def log_event(event: dict[str, Any]) -> None:
    payload = _build_payload(event)
    _append_jsonl(_log_path("amon.log"), payload)


def log_billing(record: dict[str, Any]) -> None:
    payload = _build_payload(record)
    payload.setdefault("token", 0)
    _append_jsonl(_log_path("billing.log"), payload)


def _build_payload(source: dict[str, Any]) -> dict[str, Any]:
    payload = dict(source)
    payload.setdefault("ts", _now_iso())
    payload.setdefault("level", "INFO")
    payload.setdefault("project_id", None)
    payload.setdefault("session_id", None)
    return payload


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _log_path(filename: str) -> Path:
    return _resolve_data_dir() / "logs" / filename


def _resolve_data_dir() -> Path:
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.amon").expanduser()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
