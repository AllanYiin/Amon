"""Chat session store for Amon."""

from __future__ import annotations

import json
import os
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.logging import log_event
from amon.fs.atomic import append_jsonl
from amon.config import read_yaml
from amon.fs.safety import validate_identifier, validate_project_id


NOISY_EVENT_TYPES = {"assistant_chunk"}
MAX_HISTORY_CHARS = 3200
MAX_USER_TURN_CHARS = 420
MAX_ASSISTANT_TURN_CHARS = 240


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
    validate_identifier(chat_id, "chat_id")
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
        append_jsonl(session_path, payload)
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

    if payload.get("type") not in NOISY_EVENT_TYPES:
        log_event(
            {
                "event": "chat_session_event",
                "project_id": payload["project_id"],
                "session_id": chat_id,
                "type": payload.get("type"),
                "run_id": payload.get("run_id"),
            }
        )




def load_latest_chat_id(project_id: str) -> str | None:
    """Return the most recently updated chat session id for a project."""
    validate_project_id(project_id)
    sessions_dir = _resolve_project_path(project_id) / "sessions" / "chat"
    if not sessions_dir.exists():
        return None
    try:
        candidates = [path for path in sessions_dir.glob("*.jsonl") if path.is_file()]
    except OSError:
        return None
    if not candidates:
        return None
    latest = max(candidates, key=lambda item: item.stat().st_mtime)
    return latest.stem


def chat_session_exists(project_id: str, chat_id: str) -> bool:
    """Return True when the chat session file exists for the given project/chat pair."""
    validate_project_id(project_id)
    if not chat_id:
        return False
    validate_identifier(chat_id, "chat_id")
    return _chat_session_path(project_id, chat_id).exists()


def ensure_chat_session(project_id: str, chat_id: str | None = None) -> tuple[str, str]:
    """Ensure a usable chat session and return (chat_id, source)."""
    validate_project_id(project_id)
    incoming_chat_id = (chat_id or "").strip()

    if incoming_chat_id and chat_session_exists(project_id, incoming_chat_id):
        return incoming_chat_id, "incoming"

    latest_chat_id = load_latest_chat_id(project_id)
    if latest_chat_id:
        return latest_chat_id, "latest"

    return create_chat_session(project_id), "new"

def load_recent_dialogue(project_id: str, chat_id: str, limit: int = 12) -> list[dict[str, str]]:
    """Load recent user/assistant dialogue turns for contextual continuity."""
    if not chat_id:
        return []
    validate_identifier(chat_id, "chat_id")
    if limit <= 0:
        return []
    validate_project_id(project_id)

    session_path = _chat_session_path(project_id, chat_id)
    if not session_path.exists():
        return []

    dialogue: list[dict[str, str]] = []
    try:
        for payload in _iter_recent_session_payloads(session_path, max_lines=max(limit * 8, 64), max_bytes=256 * 1024):
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


def load_latest_run_context(project_id: str, chat_id: str) -> dict[str, str | None]:
    """Load the latest run_id and assistant reply text from a chat session."""
    if not chat_id:
        return {"run_id": None, "last_assistant_text": None}
    validate_identifier(chat_id, "chat_id")
    validate_project_id(project_id)

    session_path = _chat_session_path(project_id, chat_id)
    if not session_path.exists():
        return {"run_id": None, "last_assistant_text": None}

    latest_run_id: str | None = None
    last_assistant_text: str | None = None
    try:
        for payload in _iter_recent_session_payloads(session_path, max_lines=512, max_bytes=384 * 1024):
            run_id = payload.get("run_id")
            if isinstance(run_id, str) and run_id.strip():
                latest_run_id = run_id.strip()
            if payload.get("type") == "assistant":
                text = payload.get("text")
                if isinstance(text, str) and text.strip():
                    last_assistant_text = text.strip()
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
        return {"run_id": None, "last_assistant_text": None}

    return {"run_id": latest_run_id, "last_assistant_text": last_assistant_text}


def build_prompt_with_history(message: str, dialogue: list[dict[str, str]] | None = None) -> str:
    """Compose prompt with conversation history when available."""
    cleaned_message = (message or "").strip()
    if not dialogue:
        return cleaned_message

    anchor_task = _extract_anchor_task(dialogue)
    condensed_dialogue = _condense_dialogue(dialogue)

    history_lines: list[str] = []
    for item in condensed_dialogue:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        speaker = "使用者" if role == "user" else "Amon"
        history_lines.append(f"{speaker}: {content}")
    if not history_lines and not anchor_task:
        return cleaned_message

    blocks: list[str] = [
        "請根據以下歷史對話延續回覆，保持脈絡一致，不要改題。"
        "若目前訊息是對上一輪提問的簡短回答（例如選項、片語或關鍵字），"
        "請直接沿用既有任務往下執行，不要改成其他主題，也不要再次要求使用者重複確認。",
        "回覆收尾規約：除非缺少關鍵資訊而無法完成任務（例如缺參數、缺檔案、缺環境設定），"
        "否則不要用問句收尾；請以明確結論或下一步行動收束。",
    ]
    if anchor_task:
        blocks.append("[核心任務]\n" + anchor_task)
    if history_lines:
        blocks.append("[歷史對話]\n" + "\n".join(history_lines))
    blocks.append("[目前訊息]\n" + f"使用者: {cleaned_message}")
    return "\n".join(blocks)


def _extract_anchor_task(dialogue: list[dict[str, str]]) -> str:
    for item in dialogue:
        if item.get("role") != "user":
            continue
        content = _normalize_content(item.get("content") or "")
        if content:
            return _trim_content(content, MAX_USER_TURN_CHARS)
    return ""


def _condense_dialogue(dialogue: list[dict[str, str]]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    total_chars = 0
    for item in reversed(dialogue):
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _normalize_content(item.get("content") or "")
        if not content:
            continue
        limit = MAX_USER_TURN_CHARS if role == "user" else MAX_ASSISTANT_TURN_CHARS
        clipped = _trim_content(content, limit)
        needed = len(clipped) + 16
        if kept and total_chars + needed > MAX_HISTORY_CHARS:
            continue
        if not kept and total_chars + needed > MAX_HISTORY_CHARS:
            clipped = _trim_content(clipped, max(32, MAX_HISTORY_CHARS - total_chars - 16))
            if not clipped:
                continue
            needed = len(clipped) + 16
        kept.append({"role": role, "content": clipped})
        total_chars += needed
    kept.reverse()
    return kept


def _normalize_content(content: str) -> str:
    return " ".join(content.split())


def _trim_content(content: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(content) <= limit:
        return content
    return content[: max(0, limit - 1)].rstrip() + "…"



def _iter_recent_session_payloads(session_path: Path, *, max_lines: int, max_bytes: int) -> list[dict[str, Any]]:
    if max_lines <= 0 or max_bytes <= 0:
        return []
    with session_path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        if file_size <= 0:
            return []
        target = min(file_size, max_bytes)
        handle.seek(file_size - target)
        chunk = handle.read(target)
    if file_size > target:
        newline_index = chunk.find(b"\n")
        if newline_index >= 0:
            chunk = chunk[newline_index + 1 :]
    tail_lines = deque(chunk.splitlines(), maxlen=max_lines)
    payloads: list[dict[str, Any]] = []
    for raw in tail_lines:
        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads

def _chat_session_path(project_id: str, chat_id: str) -> Path:
    return _resolve_project_path(project_id) / "sessions" / "chat" / f"{chat_id}.jsonl"


def _resolve_project_path(project_id: str) -> Path:
    data_dir = _resolve_data_dir()
    projects_dir = data_dir / "projects"
    direct_path = projects_dir / project_id
    if direct_path.exists():
        return direct_path
    config_name = "amon.project.yaml"
    if projects_dir.exists():
        for candidate in projects_dir.iterdir():
            if not candidate.is_dir():
                continue
            config_path = candidate / config_name
            if not config_path.exists():
                continue
            config = read_yaml(config_path)
            amon_cfg = config.get("amon", {}) if isinstance(config, dict) else {}
            if str(amon_cfg.get("project_id") or "").strip() == project_id:
                return candidate
    return direct_path


def _resolve_data_dir() -> Path:
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.amon").expanduser()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
