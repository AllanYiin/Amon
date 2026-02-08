"""Audit sink interface for tooling calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .types import ToolCall, ToolResult


class AuditSink(Protocol):
    """Records tool calls and outcomes."""

    def record(self, call: ToolCall, result: ToolResult, decision: str) -> None:
        ...


@dataclass(frozen=True)
class NullAuditSink:
    """No-op audit sink."""

    def record(self, call: ToolCall, result: ToolResult, decision: str) -> None:
        return None


@dataclass(frozen=True)
class FileAuditSink:
    """Append audit records to a log file."""

    log_path: Path

    def record(self, call: ToolCall, result: ToolResult, decision: str) -> None:
        payload = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "tool": call.tool,
            "caller": call.caller,
            "project_id": call.project_id,
            "session_id": call.session_id,
            "decision": decision,
            "is_error": result.is_error,
            "status": result.meta.get("status"),
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            return None
