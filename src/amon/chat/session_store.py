"""Chat session store for Amon."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.logging import log_event
from amon.fs.safety import validate_project_id


def create_chat_session(project_id: str) -> str:
    validate_project_id(project_id)

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
    project_id = event.get("project_id")
    if not isinstance(project_id, str):
        raise ValueError("project_id 需為字串")
    validate_project_id(project_id)

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


def load_recent_dialogue(project_id: str, chat_id: str, limit: int = 12) -> list[dict[str, str]]:
    """Load recent user/assistant dialogue turns for contextual continuity."""
    if not chat_id:
        return []
    if limit <= 0:
        return []
    validate_project_id(project_id)

    session_path = _chat_session_path(project_id, chat_id)
    if not session_path.exists():
        return []

    dialogue: list[dict[str, str]] = []
    try:
        for raw_line in session_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = payload.get("type")
            text = payload.get("text")
            if event_type not in {"user", "assistant"} or not isinstance(text, str) or not text.strip():
                continue
            role = "user" if event_type == "user" else "assistant"
            dialogue.append({"role": role, "content": text.strip()})
    except OSError as exc:
        log_event(
            {
                "event": "chat_session_read_failed",
                "level": "WARNING",
                "project_id": project_id,
                "session_id": chat_id,
                "error": str(exc),
            }
        )
        return []
    return dialogue[-limit:]


def build_prompt_with_history(message: str, dialogue: list[dict[str, str]] | None = None) -> str:
    """Compose prompt with conversation history when available."""
    cleaned_message = (message or "").strip()
    if not dialogue:
        return cleaned_message

    history_lines: list[str] = []
    for item in dialogue:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        speaker = "使用者" if role == "user" else "Amon"
        history_lines.append(f"{speaker}: {content}")
    if not history_lines:
        return cleaned_message
    history = "\n".join(history_lines)
    return (
        "請根據以下歷史對話延續回覆，保持脈絡一致。\n"
        "[歷史對話]\n"
        f"{history}\n"
        "[目前訊息]\n"
        f"使用者: {cleaned_message}"
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
