"""Chat session store for Amon."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.logging import log_event
from amon.fs.atomic import append_jsonl, atomic_write_text
from amon.config import read_yaml
from amon.fs.safety import validate_identifier, validate_project_id


NOISY_EVENT_TYPES = {"assistant_chunk", "assistant_reasoning"}
MAX_HISTORY_CHARS = 3200
MAX_USER_TURN_CHARS = 420
MAX_ASSISTANT_TURN_CHARS = 240
_RECENT_MESSAGES_MAX = 6


def create_thread_session(project_id: str) -> str:
    validate_project_id(project_id)
    _migrate_legacy_sessions_if_needed(project_id)

    thread_id = uuid.uuid4().hex
    thread_dir = _thread_dir_path(project_id, thread_id)

    try:
        thread_dir.mkdir(parents=True, exist_ok=True)
        _thread_events_path(project_id, thread_id).touch(exist_ok=True)
        _write_thread_rollup(project_id, _new_rollup(project_id, thread_id))
        _upsert_thread_index(project_id, thread_id, _new_rollup(project_id, thread_id))
        _write_project_state(project_id, {"schema_version": 1, "active_thread_id": thread_id})
    except OSError as exc:
        log_event(
            {
                "event": "thread_session_create_failed",
                "level": "ERROR",
                "project_id": project_id,
                "session_id": thread_id,
                "error": str(exc),
            }
        )
        raise

    log_event({"event": "thread_session_created", "project_id": project_id, "session_id": thread_id})
    return thread_id


def append_event(thread_id: str, event: dict[str, Any]) -> None:
    if not thread_id:
        raise ValueError("thread_id 不可為空")
    validate_identifier(thread_id, "thread_id")
    if not isinstance(event, dict):
        raise ValueError("event 需為 dict")

    missing_fields = [key for key in ("type", "text", "project_id") if not event.get(key)]
    if missing_fields:
        raise ValueError(f"event 缺少必要欄位：{', '.join(missing_fields)}")
    project_id = event.get("project_id")
    if not isinstance(project_id, str):
        raise ValueError("project_id 需為字串")
    validate_project_id(project_id)
    _migrate_legacy_sessions_if_needed(project_id)

    payload = dict(event)
    payload.setdefault("ts", _now_iso())
    payload["thread_id"] = thread_id

    session_path = _thread_events_path(payload["project_id"], thread_id)

    try:
        append_jsonl(session_path, payload)
        _refresh_rollup_from_event(payload["project_id"], thread_id, payload)
        _write_project_state(payload["project_id"], {"schema_version": 1, "active_thread_id": thread_id})
    except OSError as exc:
        log_event(
            {
                "event": "thread_session_append_failed",
                "level": "ERROR",
                "project_id": payload["project_id"],
                "session_id": thread_id,
                "type": payload.get("type"),
                "error": str(exc),
            }
        )
        raise

    if payload.get("type") not in NOISY_EVENT_TYPES:
        log_details = _build_thread_session_log_details(payload)
        log_event(
            {
                "event": "thread_session_event",
                "project_id": payload["project_id"],
                "session_id": thread_id,
                "type": payload.get("type"),
                "run_id": payload.get("run_id"),
                **log_details,
            }
        )


def _build_thread_session_log_details(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("type") or "")
    details: dict[str, Any] = {}

    text = payload.get("text")
    if isinstance(text, str):
        details["text_chars"] = len(text.strip())

    if event_type == "router" and isinstance(text, str):
        details["summary"] = f"router:{text.strip() or 'unknown'}"
    elif event_type == "plan_created" and isinstance(text, str):
        details["summary"] = f"plan:{text.strip() or 'unknown'}"
    elif event_type == "command_result" and isinstance(text, str):
        details["summary"] = _summarize_command_result(text)
    elif event_type:
        details["summary"] = event_type

    command = payload.get("command")
    if isinstance(command, str) and command.strip():
        details["command"] = command.strip()

    return details


def _summarize_command_result(raw_text: str) -> str:
    trimmed = raw_text.strip()
    if not trimmed:
        return "command_result:empty"
    try:
        parsed = json.loads(trimmed)
    except json.JSONDecodeError:
        return "command_result:non_json"

    if not isinstance(parsed, dict):
        return "command_result:json"
    status = str(parsed.get("status") or "unknown")
    return f"command_result:{status}"


def load_latest_thread_id(project_id: str) -> str | None:
    """Return active thread id for a project."""
    validate_project_id(project_id)
    _migrate_legacy_sessions_if_needed(project_id)
    state = _load_project_state(project_id)
    active_thread_id = str(state.get("active_thread_id") or "").strip()
    if not active_thread_id:
        return None
    if thread_session_exists(project_id, active_thread_id):
        return active_thread_id
    return None


def thread_session_exists(project_id: str, thread_id: str) -> bool:
    """Return True when the thread file exists for the given project/chat pair."""
    validate_project_id(project_id)
    if not thread_id:
        return False
    validate_identifier(thread_id, "thread_id")
    _migrate_legacy_sessions_if_needed(project_id)
    return _thread_events_path(project_id, thread_id).exists()


def ensure_thread_session(project_id: str, thread_id: str | None = None) -> tuple[str, str]:
    """Ensure a usable thread and return (thread_id, source)."""
    validate_project_id(project_id)
    _migrate_legacy_sessions_if_needed(project_id)
    incoming_thread_id = (thread_id or "").strip()

    if incoming_thread_id and thread_session_exists(project_id, incoming_thread_id):
        _write_project_state(project_id, {"schema_version": 1, "active_thread_id": incoming_thread_id})
        return incoming_thread_id, "incoming"

    active_thread_id = load_latest_thread_id(project_id)
    if active_thread_id:
        return active_thread_id, "active"

    return create_thread_session(project_id), "new"


def load_recent_dialogue(project_id: str, thread_id: str, limit: int = 12) -> list[dict[str, str]]:
    """Load recent user/assistant dialogue turns for contextual continuity."""
    if not thread_id:
        return []
    validate_identifier(thread_id, "thread_id")
    if limit <= 0:
        return []
    validate_project_id(project_id)
    _migrate_legacy_sessions_if_needed(project_id)

    session_path = _thread_events_path(project_id, thread_id)
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
                "event": "thread_session_read_failed",
                "level": "WARNING",
                "project_id": project_id,
                "session_id": thread_id,
                "error": str(exc),
            }
        )
        return []
    return dialogue[-limit:]


def load_latest_run_context(project_id: str, thread_id: str) -> dict[str, str | None]:
    """Load the latest run_id and assistant reply text from a thread."""
    if not thread_id:
        return {"run_id": None, "last_assistant_text": None}
    validate_identifier(thread_id, "thread_id")
    validate_project_id(project_id)
    _migrate_legacy_sessions_if_needed(project_id)

    session_path = _thread_events_path(project_id, thread_id)
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
                "event": "thread_session_read_failed",
                "level": "WARNING",
                "project_id": project_id,
                "session_id": thread_id,
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
        "回覆收尾規約：只有在缺少關鍵資訊而無法完成任務（例如缺參數、缺檔案、缺環境設定），"
        "且無法以現有上下文或合理假設補足時，才提出問題；能先完成的部分先完成，"
        "不要為了低風險確認而中斷。若仍需提問，請一次整合提出所有阻塞問題，不要分散追問；"
        "一旦提問，就停在等待使用者回覆的狀態，不要自問自答，也不要在提問後自行追加假設繼續完成任務；"
        "否則不要用問句收尾，請以明確結論、已完成事項或下一步行動收束。",
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


def _load_project_state(project_id: str) -> dict[str, Any]:
    path = _project_state_path(project_id)
    if not path.exists():
        return {"schema_version": 1, "active_thread_id": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {"schema_version": 1, "active_thread_id": None}
    if not isinstance(payload, dict):
        return {"schema_version": 1, "active_thread_id": None}
    return payload


def _write_project_state(project_id: str, payload: dict[str, Any]) -> None:
    merged = {"schema_version": 1}
    current = _load_project_state(project_id)
    if isinstance(current, dict):
        merged.update(current)
    merged.update(payload)
    atomic_write_text(_project_state_path(project_id), json.dumps(merged, ensure_ascii=False, indent=2) + "\n")


def _load_rollup(project_id: str, thread_id: str) -> dict[str, Any]:
    path = _thread_rollup_path(project_id, thread_id)
    if not path.exists():
        return _new_rollup(project_id, thread_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return _new_rollup(project_id, thread_id)
    if not isinstance(payload, dict):
        return _new_rollup(project_id, thread_id)
    return payload


def _write_thread_rollup(project_id: str, payload: dict[str, Any]) -> None:
    thread_id = str(payload.get("thread_id") or "").strip()
    if not thread_id:
        return
    atomic_write_text(_thread_rollup_path(project_id, thread_id), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _refresh_rollup_from_event(project_id: str, thread_id: str, event: dict[str, Any]) -> None:
    rollup = _load_rollup(project_id, thread_id)
    now_iso = str(event.get("ts") or _now_iso())
    rollup["schema_version"] = 1
    rollup["project_id"] = project_id
    rollup["thread_id"] = thread_id
    rollup["updated_at"] = now_iso
    if not str(rollup.get("created_at") or "").strip():
        rollup["created_at"] = now_iso

    text = str(event.get("text") or "").strip()
    event_type = str(event.get("type") or "").strip()
    run_id = str(event.get("run_id") or "").strip()

    if event_type == "user":
        rollup["message_count"] = int(rollup.get("message_count") or 0) + 1
        rollup["last_user_text"] = text
        if not str(rollup.get("title") or "").strip():
            rollup["title"] = _trim_content(text, 64)
        _append_recent_message(rollup, {"role": "user", "content": text})
    elif event_type == "assistant":
        rollup["message_count"] = int(rollup.get("message_count") or 0) + 1
        rollup["last_assistant_text"] = text
        _append_recent_message(rollup, {"role": "assistant", "content": text})

    previous_latest_run_id = str(rollup.get("latest_run_id") or "").strip()
    if run_id:
        if run_id != previous_latest_run_id:
            rollup["run_count"] = int(rollup.get("run_count") or 0) + 1
        rollup["latest_run_id"] = run_id

    if "summary" not in rollup:
        rollup["summary"] = ""
    _write_thread_rollup(project_id, rollup)
    _upsert_thread_index(project_id, thread_id, rollup)


def _append_recent_message(rollup: dict[str, Any], item: dict[str, str]) -> None:
    recent_messages = rollup.get("recent_messages")
    if not isinstance(recent_messages, list):
        recent_messages = []
    recent_messages.append(item)
    rollup["recent_messages"] = recent_messages[-_RECENT_MESSAGES_MAX:]


def _new_rollup(project_id: str, thread_id: str) -> dict[str, Any]:
    now_iso = _now_iso()
    return {
        "schema_version": 1,
        "project_id": project_id,
        "thread_id": thread_id,
        "title": "",
        "summary": "",
        "created_at": now_iso,
        "updated_at": now_iso,
        "latest_run_id": "",
        "message_count": 0,
        "run_count": 0,
        "last_user_text": "",
        "last_assistant_text": "",
        "recent_messages": [],
    }


def _upsert_thread_index(project_id: str, thread_id: str, rollup: dict[str, Any]) -> None:
    path = _threads_index_path(project_id)
    index_payload = {"schema_version": 1, "project_id": project_id, "threads": []}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                index_payload.update(raw)
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    threads = index_payload.get("threads")
    normalized_threads: list[dict[str, Any]] = []
    if isinstance(threads, list):
        normalized_threads = [item for item in threads if isinstance(item, dict)]

    updated = False
    for item in normalized_threads:
        if str(item.get("thread_id") or "") == thread_id:
            item.update(
                {
                    "thread_id": thread_id,
                    "title": str(rollup.get("title") or ""),
                    "created_at": str(rollup.get("created_at") or ""),
                    "updated_at": str(rollup.get("updated_at") or ""),
                }
            )
            updated = True
            break
    if not updated:
        normalized_threads.append(
            {
                "thread_id": thread_id,
                "title": str(rollup.get("title") or ""),
                "created_at": str(rollup.get("created_at") or ""),
                "updated_at": str(rollup.get("updated_at") or ""),
            }
        )

    index_payload["schema_version"] = 1
    index_payload["project_id"] = project_id
    index_payload["threads"] = sorted(
        normalized_threads,
        key=lambda item: str(item.get("updated_at") or ""),
        reverse=True,
    )
    atomic_write_text(path, json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n")


def _migrate_legacy_sessions_if_needed(project_id: str) -> None:
    project_path = _resolve_project_path(project_id)
    legacy_dir = project_path / "sessions" / "chat"
    if not legacy_dir.exists():
        return

    state = _load_project_state(project_id)
    if bool(state.get("migration_v1_completed")):
        return

    try:
        legacy_files = [path for path in legacy_dir.glob("*.jsonl") if path.is_file()]
    except OSError:
        legacy_files = []

    active_thread_id = str(state.get("active_thread_id") or "").strip() or None
    if legacy_files:
        latest_legacy = max(legacy_files, key=lambda path: path.stat().st_mtime)
        for legacy_file in legacy_files:
            thread_id = legacy_file.stem
            validate_identifier(thread_id, "thread_id")
            thread_dir = _thread_dir_path(project_id, thread_id)
            thread_dir.mkdir(parents=True, exist_ok=True)
            events_path = _thread_events_path(project_id, thread_id)
            if not events_path.exists():
                shutil.copyfile(legacy_file, events_path)
            rollup = _build_rollup_from_events_file(project_id, thread_id, events_path)
            try:
                mtime_iso = datetime.fromtimestamp(legacy_file.stat().st_mtime).astimezone().isoformat(timespec="seconds")
                rollup["updated_at"] = mtime_iso
            except OSError:
                pass
            _write_thread_rollup(project_id, rollup)
            _upsert_thread_index(project_id, thread_id, rollup)
        if not active_thread_id:
            active_thread_id = latest_legacy.stem

    _write_project_state(
        project_id,
        {
            "schema_version": 1,
            "active_thread_id": active_thread_id,
            "migration_v1_completed": True,
        },
    )


def _build_rollup_from_events_file(project_id: str, thread_id: str, events_path: Path) -> dict[str, Any]:
    rollup = _new_rollup(project_id, thread_id)
    try:
        for raw_line in events_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            payload.setdefault("ts", _now_iso())
            _refresh_rollup_for_migration(rollup, payload)
    except OSError:
        return rollup
    return rollup


def _refresh_rollup_for_migration(rollup: dict[str, Any], payload: dict[str, Any]) -> None:
    now_iso = str(payload.get("ts") or _now_iso())
    rollup["updated_at"] = now_iso
    if not str(rollup.get("created_at") or "").strip():
        rollup["created_at"] = now_iso

    event_type = str(payload.get("type") or "").strip()
    text = str(payload.get("text") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()

    if event_type == "user":
        rollup["message_count"] = int(rollup.get("message_count") or 0) + 1
        rollup["last_user_text"] = text
        if not str(rollup.get("title") or "").strip():
            rollup["title"] = _trim_content(text, 64)
        _append_recent_message(rollup, {"role": "user", "content": text})
    elif event_type == "assistant":
        rollup["message_count"] = int(rollup.get("message_count") or 0) + 1
        rollup["last_assistant_text"] = text
        _append_recent_message(rollup, {"role": "assistant", "content": text})

    previous_latest_run_id = str(rollup.get("latest_run_id") or "").strip()
    if run_id:
        if run_id != previous_latest_run_id:
            rollup["run_count"] = int(rollup.get("run_count") or 0) + 1
        rollup["latest_run_id"] = run_id


def _project_state_path(project_id: str) -> Path:
    return _resolve_project_path(project_id) / ".amon" / "project_state.json"


def _threads_index_path(project_id: str) -> Path:
    return _resolve_project_path(project_id) / ".amon" / "threads" / "index.json"


def _thread_dir_path(project_id: str, thread_id: str) -> Path:
    return _resolve_project_path(project_id) / ".amon" / "threads" / thread_id


def _thread_events_path(project_id: str, thread_id: str) -> Path:
    return _thread_dir_path(project_id, thread_id) / "events.jsonl"


def _thread_rollup_path(project_id: str, thread_id: str) -> Path:
    return _thread_dir_path(project_id, thread_id) / "rollup.json"


def _thread_session_path(project_id: str, thread_id: str) -> Path:
    return _thread_events_path(project_id, thread_id)


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
