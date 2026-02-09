"""Core tooling dataclasses and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Callable, Literal


Risk = Literal["low", "medium", "high"]
Decision = Literal["allow", "ask", "deny"]


@dataclass(frozen=True)
class ToolSpec:
    """Defines a tool interface."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    risk: Risk = "low"
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """Represents a tool invocation request."""

    tool: str
    args: dict[str, Any]
    caller: str = "agent"
    project_id: str | None = None
    session_id: str | None = None
    ts_ms: int = field(
        default_factory=lambda: int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    )


@dataclass
class ToolResult:
    """Represents a tool invocation outcome."""

    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        parts: list[str] = []
        for item in self.content:
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif "text" in item:
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)


Handler = Callable[[ToolCall], ToolResult]


def json_dumps_stable(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
