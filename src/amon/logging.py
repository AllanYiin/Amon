"""JSONL logging helpers for Amon."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .fs.atomic import append_jsonl

def log_event(event: dict[str, Any]) -> None:
    payload = _build_payload(event)
    _append_jsonl(_log_path("amon.log"), payload)
    project_log_path = _project_log_path(payload, "events.log")
    if project_log_path is not None:
        _append_jsonl(project_log_path, payload)


def log_billing(record: dict[str, Any]) -> None:
    payload = _build_payload(record)
    payload.setdefault("token", 0)
    _append_jsonl(_log_path("billing.log"), payload)
    project_log_path = _project_log_path(payload, "billing.log")
    if project_log_path is not None:
        _append_jsonl(project_log_path, payload)


def _build_payload(source: dict[str, Any]) -> dict[str, Any]:
    payload = dict(source)
    payload.setdefault("ts", _now_iso())
    payload.setdefault("level", "INFO")
    payload.setdefault("project_id", None)
    payload.setdefault("session_id", None)
    return payload


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    append_jsonl(path, payload)


def _log_path(filename: str) -> Path:
    return _resolve_data_dir() / "logs" / filename


def _project_log_path(payload: dict[str, Any], filename: str) -> Path | None:
    project_id = str(payload.get("project_id") or "").strip()
    if not project_id:
        return None

    projects_dir = _resolve_data_dir() / "projects"
    direct_path = projects_dir / project_id
    if (direct_path / "amon.project.yaml").exists():
        return direct_path / ".amon" / "logs" / filename

    for candidate in projects_dir.glob("*/amon.project.yaml"):
        if candidate.parent.name == project_id:
            return candidate.parent / ".amon" / "logs" / filename
    return None


def _resolve_data_dir() -> Path:
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.amon").expanduser()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
