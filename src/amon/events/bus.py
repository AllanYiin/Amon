"""JSONL event bus for Amon."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.fs.atomic import append_jsonl


REQUIRED_FIELDS = {"event_id", "ts", "type", "scope", "actor", "payload", "risk"}
def emit_event(event: dict[str, Any], *, dispatch_hooks: bool | None = None) -> str:
    """Emit an event to the JSONL bus and return the event_id."""
    payload = dict(event or {})
    if not isinstance(payload, dict):
        raise ValueError("event 必須為 dict")
    payload.setdefault("event_id", _generate_event_id())
    payload.setdefault("ts", _now_iso())
    payload.setdefault("project_id", None)
    missing = sorted(field for field in REQUIRED_FIELDS if field not in payload)
    if missing:
        raise ValueError(f"event 缺少必要欄位：{', '.join(missing)}")
    if "project_id" in payload and payload["project_id"] == "":
        payload["project_id"] = None
    append_jsonl(_events_path(), payload)
    if dispatch_hooks is None:
        dispatch_hooks = os.environ.get("AMON_DISABLE_HOOK_DISPATCH") != "1"
    if dispatch_hooks:
        _dispatch_hooks(payload)
    return str(payload["event_id"])


def _events_path() -> Path:
    base_dir = Path(os.environ.get("AMON_HOME", "~/.amon")).expanduser()
    return base_dir / "events" / "events.jsonl"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _generate_event_id() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d%H%M%S%f")


def _dispatch_hooks(payload: dict[str, Any]) -> None:
    try:
        from amon.hooks.runner import process_event
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("載入 hook runner 失敗：%s", exc, exc_info=True)
        return
    try:
        process_event(payload)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("Hook 執行失敗：%s", exc, exc_info=True)
