"""JSONL logging helpers for Amon."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .fs.atomic import append_jsonl
from .project_log_store import ProjectLogStore
from .project_registry import ProjectRegistry

_LOGGER = logging.getLogger("amon.logging")
_PROJECT_LOG_STORES: dict[Path, ProjectLogStore] = {}


def log_event(event: dict[str, Any]) -> None:
    payload = _build_payload(event)
    _append_jsonl(_log_path("amon.log"), payload)
    _append_jsonl(_log_path("events.log"), payload)
    _project_log_store().append_app(payload)
    _project_log_store().append_event(payload)


def log_billing(record: dict[str, Any]) -> None:
    payload = _build_payload(record)
    payload.setdefault("token", 0)
    _append_jsonl(_log_path("billing.log"), payload)
    _project_log_store().append_billing(payload)


def _project_log_store() -> ProjectLogStore:
    data_dir = _resolve_data_dir()
    store = _PROJECT_LOG_STORES.get(data_dir)
    if store is not None:
        return store
    registry = ProjectRegistry(data_dir / "projects", logger=_LOGGER)
    registry.scan()
    store = ProjectLogStore(data_dir=data_dir, registry=registry, logger=_LOGGER)
    _PROJECT_LOG_STORES[data_dir] = store
    return store


def _build_payload(source: dict[str, Any]) -> dict[str, Any]:
    payload = dict(source)
    payload.setdefault("ts", _now_iso())
    payload.setdefault("level", "INFO")
    payload.setdefault("project_id", None)
    payload.setdefault("session_id", None)
    payload.setdefault("run_id", None)
    payload.setdefault("chat_id", None)
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
