"""Audit sink interface for tooling calls."""

from __future__ import annotations

from dataclasses import dataclass
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
