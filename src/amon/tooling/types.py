"""Placeholder dataclasses for tooling types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    """Defines a tool's interface for later wiring."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolCall:
    """Represents a tool invocation request."""

    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Represents a tool invocation outcome."""

    tool_name: str
    success: bool
    output: Any | None = None
    error: str | None = None
