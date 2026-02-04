"""Chat session store for Amon."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.logging import log_event


def create_chat_session(project_id: str) -> str:
    if not project_id:
        raise ValueError("project_id 不可為空")

    chat_id = uuid.uuid4().hex
    session_path = _chat_session_path(project_id, chat_id)

    try:
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.touch(exist_ok=True)
    except OSError as exc:
        log_event(
            {
                "event": "chat_session_create_failed",
                "level": "ERROR",
                "project_id": project_id,
                "session_id": chat_id,
                "error": str(exc),
            }
        )
        raise

    log_event({"event": "chat_session_created", "project_id": project_id, "session_id": chat_id})
    return chat_id


def append_event(chat_id: str, event: dict[str, Any]) -> None:
    if not chat_id:
        raise ValueError("chat_id 不可為空")
    if not isinstance(event, dict):
        raise ValueError("event 需為 dict")

    missing_fields = [key for key in ("type", "text", "project_id") if not event.get(key)]
    if missing_fields:
        raise ValueError(f"event 缺少必要欄位：{', '.join(missing_fields)}")

    payload = dict(event)
    payload.setdefault("ts", _now_iso())
    payload["chat_id"] = chat_id

    session_path = _chat_session_path(payload["project_id"], chat_id)

    try:
        session_path.parent.mkdir(parents=True, exist_ok=True)
        with session_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except OSError as exc:
        log_event(
            {
                "event": "chat_session_append_failed",
                "level": "ERROR",
                "project_id": payload["project_id"],
                "session_id": chat_id,
                "type": payload.get("type"),
                "error": str(exc),
            }
        )
        raise

    log_event(
        {
            "event": "chat_session_event",
            "project_id": payload["project_id"],
            "session_id": chat_id,
            "type": payload.get("type"),
            "run_id": payload.get("run_id"),
        }
    )


def _chat_session_path(project_id: str, chat_id: str) -> Path:
    return _resolve_data_dir() / "projects" / project_id / "sessions" / "chat" / f"{chat_id}.jsonl"


def _resolve_data_dir() -> Path:
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.amon").expanduser()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
