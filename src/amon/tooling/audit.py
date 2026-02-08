"""Audit sink interface for tooling calls."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Protocol

from .types import ToolCall, ToolResult


class AuditSink(Protocol):
    """Records tool calls and outcomes."""

    def record(
        self,
        call: ToolCall,
        result: ToolResult,
        decision: str,
        *,
        duration_ms: int,
        source: str,
    ) -> None:
        ...


@dataclass(frozen=True)
class NullAuditSink:
    """No-op audit sink."""

    def record(
        self,
        call: ToolCall,
        result: ToolResult,
        decision: str,
        *,
        duration_ms: int,
        source: str,
    ) -> None:
        return None


@dataclass(frozen=True)
class FileAuditSink:
    """Append audit records to a log file."""

    log_path: Path

    def record(
        self,
        call: ToolCall,
        result: ToolResult,
        decision: str,
        *,
        duration_ms: int,
        source: str,
    ) -> None:
        result_payload = {
            "content": result.content,
            "is_error": result.is_error,
            "meta": result.meta,
        }
        payload = {
            "ts_ms": call.ts_ms,
            "tool": call.tool,
            "project_id": call.project_id,
            "session_id": call.session_id,
            "decision": decision,
            "duration_ms": duration_ms,
            "args_sha256": _hash_payload(call.args),
            "result_sha256": _hash_payload(result_payload),
            "args_preview": _redact_preview(call.args),
            "result_preview": _redact_preview(result_payload),
            "source": source,
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            return None


def default_audit_log_path() -> Path:
    base_dir = Path(os.environ.get("AMON_HOME", "~/.amon")).expanduser()
    return base_dir / "logs" / "tool_audit.jsonl"


def _hash_payload(payload: object) -> str:
    try:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        serialized = repr(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _redact_preview(payload: object, *, max_depth: int = 3, max_items: int = 6) -> object:
    if max_depth <= 0:
        return "[REDACTED]"
    if isinstance(payload, dict):
        preview: dict[str, object] = {}
        for key, value in list(payload.items())[:max_items]:
            preview[str(key)] = _redact_preview(value, max_depth=max_depth - 1, max_items=max_items)
        if len(payload) > max_items:
            preview["..."] = "[REDACTED]"
        return preview
    if isinstance(payload, list):
        preview_list = [_redact_preview(item, max_depth=max_depth - 1, max_items=max_items) for item in payload[:max_items]]
        if len(payload) > max_items:
            preview_list.append("[REDACTED]")
        return preview_list
    return "[REDACTED]"
