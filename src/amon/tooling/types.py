"""Core tooling dataclasses and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    """Defines a tool interface."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    risk: str = "low"
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    """Represents a tool invocation request."""

    tool: str
    args: dict[str, Any]
    caller: str
    project_id: str | None = None
    session_id: str | None = None
    ts_ms: int = field(
        default_factory=lambda: int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    )


@dataclass(frozen=True)
class ToolResult:
    """Represents a tool invocation outcome."""

    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        parts: list[str] = []
        for item in self.content:
            if "text" in item and isinstance(item["text"], str):
                parts.append(item["text"])
            else:
                parts.append(str(item))
        return "\n".join(parts)
