"""Helpers for persisting inspectable LLM request payloads."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .fs.atomic import append_jsonl


def build_llm_request_payload(
    *,
    source: str,
    provider: str,
    model: str | None,
    project_id: str | None,
    run_id: str | None,
    thread_id: str | None,
    node_id: str | None,
    request_id: str | None,
    stage: str | None,
    messages: list[dict[str, Any]] | None,
    prompt_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chat_messages = _normalize_chat_messages(messages or [])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "ts": _now_iso(),
        "source": str(source or "").strip() or "unknown",
        "stage": str(stage or "").strip() or None,
        "provider": str(provider or "").strip() or "unknown",
        "model": str(model or "").strip() or None,
        "project_id": str(project_id or "").strip() or None,
        "run_id": str(run_id or "").strip() or None,
        "thread_id": str(thread_id or "").strip() or None,
        "node_id": str(node_id or "").strip() or None,
        "request_id": str(request_id or "").strip() or None,
        "message_count": len(chat_messages),
        "chat_messages": chat_messages,
        "openai_messages": [_to_openai_input_message(item) for item in chat_messages],
    }
    if isinstance(prompt_text, str) and prompt_text.strip():
        payload["prompt_text"] = prompt_text
    if isinstance(metadata, dict) and metadata:
        payload["metadata"] = metadata
    return payload


def append_llm_request(project_path: Path | None, payload: dict[str, Any]) -> Path | None:
    if project_path is None:
        return None
    path = llm_request_log_path(project_path, run_id=payload.get("run_id"))
    append_jsonl(path, payload)
    return path


def llm_request_log_path(project_path: Path, *, run_id: Any = None) -> Path:
    normalized_run_id = str(run_id or "").strip()
    if normalized_run_id and not _is_unsafe_path_token(normalized_run_id):
        return project_path / ".amon" / "runs" / normalized_run_id / "llm_requests.jsonl"
    return project_path / ".amon" / "context" / "llm_requests.jsonl"


def load_recent_llm_requests(project_path: Path, *, run_id: Any = None, limit: int = 12) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    path = llm_request_log_path(project_path, run_id=run_id)
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    payloads: list[dict[str, Any]] = []
    for raw_line in reversed(lines):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
        if len(payloads) >= limit:
            break
    return payloads


def _normalize_chat_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        if not role:
            continue
        content = _content_to_text(item.get("content"))
        if not content.strip():
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _to_openai_input_message(message: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "message",
        "role": message["role"],
        "content": [{"type": "input_text", "text": message["content"]}],
    }


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
            parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    if content is None:
        return ""
    return str(content)


def _is_unsafe_path_token(token: str) -> bool:
    return "/" in token or "\\" in token or ".." in token


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
