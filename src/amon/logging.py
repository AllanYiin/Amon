"""JSONL logging helpers for Amon."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .fs.atomic import append_jsonl
from .project_log_store import ProjectLogStore

def log_event(event: dict[str, Any]) -> None:
    payload = _build_payload(event)
    _append_jsonl(_log_path("amon.log"), payload)
    _append_project_logs(payload, stream="events")


def log_billing(record: dict[str, Any]) -> None:
    payload = _build_payload(record)
    payload.setdefault("token", 0)
    _append_jsonl(_log_path("billing.log"), payload)
    _append_project_logs(payload, stream="events")


def _append_project_logs(payload: dict[str, Any], *, stream: str) -> None:
    project_id = str(payload.get("project_id") or "").strip()
    if not project_id:
        return
    store = ProjectLogStore(_resolve_data_dir())
    try:
        if stream == "events":
            store.append_event(project_id, payload)
        store.append_app(project_id, payload)
    except Exception as exc:
        logging.getLogger("amon.logging").warning("project log write failed for %s: %s", project_id, exc)


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


def _resolve_data_dir() -> Path:
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.amon").expanduser()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
