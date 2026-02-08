"""Built-in tooling registry and handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .policy import ToolPolicy, WorkspaceGuard
from .registry import ToolRegistry
from .types import ToolCall, ToolResult, ToolSpec


def build_registry(workspace_root: Path) -> ToolRegistry:
    registry = ToolRegistry(
        policy=ToolPolicy(allow=("filesystem.read",)),
        workspace_guard=WorkspaceGuard(workspace_root=workspace_root),
    )
    register_builtin_tools(registry)
    return registry


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(_filesystem_read_spec(), _filesystem_read)


def _filesystem_read_spec() -> ToolSpec:
    return ToolSpec(
        name="filesystem.read",
        description="Read a text file from the workspace.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        output_schema={"type": "object"},
        risk="low",
        annotations={"builtin": True},
    )


def _filesystem_read(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"讀取檔案失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(content=[{"type": "text", "text": text}], is_error=False)
