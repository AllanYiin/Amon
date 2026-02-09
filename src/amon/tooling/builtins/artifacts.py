"""Artifacts builtin tools."""

from __future__ import annotations

import base64
import difflib
from pathlib import Path
from typing import Any

from ..policy import WorkspaceGuard
from ..types import ToolCall, ToolResult, ToolSpec


def spec_artifacts_write_text() -> ToolSpec:
    return ToolSpec(
        name="artifacts.write_text",
        description="Write text content to a file in the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_artifacts_write_text(call: ToolCall, *, guard: WorkspaceGuard | None) -> ToolResult:
    path = call.args.get("path")
    content = call.args.get("content")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(content, str):
        return ToolResult(
            content=[{"type": "text", "text": "缺少 content 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    encoding = str(call.args.get("encoding", "utf-8"))
    try:
        if guard:
            guard.assert_in_workspace(path)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
    except (OSError, ValueError) as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"寫入失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(content=[{"type": "text", "text": f"已寫入：{path}"}])


def spec_artifacts_write_file() -> ToolSpec:
    return ToolSpec(
        name="artifacts.write_file",
        description="Write base64-encoded binary content to a file.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content_base64": {"type": "string"},
            },
            "required": ["path", "content_base64"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_artifacts_write_file(call: ToolCall, *, guard: WorkspaceGuard | None) -> ToolResult:
    path = call.args.get("path")
    content_base64 = call.args.get("content_base64")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(content_base64, str) or not content_base64:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 content_base64 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        if guard:
            guard.assert_in_workspace(path)
        data = base64.b64decode(content_base64)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except (OSError, ValueError) as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"寫入失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(content=[{"type": "text", "text": f"已寫入：{path}"}])


def spec_artifacts_preview_diff() -> ToolSpec:
    return ToolSpec(
        name="artifacts.preview_diff",
        description="Preview a unified diff for a text file update.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_artifacts_preview_diff(call: ToolCall, *, guard: WorkspaceGuard | None) -> ToolResult:
    path = call.args.get("path")
    content = call.args.get("content")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(content, str):
        return ToolResult(
            content=[{"type": "text", "text": "缺少 content 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        if guard:
            guard.assert_in_workspace(path)
        target = Path(path)
        before = target.read_text(encoding="utf-8") if target.exists() else ""
    except (OSError, ValueError) as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"讀取失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    diff_lines = difflib.unified_diff(
        before.splitlines(),
        content.splitlines(),
        fromfile=str(path),
        tofile=str(path),
        lineterm="",
    )
    return ToolResult(content=[{"type": "text", "text": "\n".join(diff_lines)}])


def register_artifacts_tools(registry: Any, *, guard: WorkspaceGuard | None) -> None:
    registry.register(
        spec_artifacts_preview_diff(),
        lambda call: handle_artifacts_preview_diff(call, guard=guard),
    )
    registry.register(
        spec_artifacts_write_text(),
        lambda call: handle_artifacts_write_text(call, guard=guard),
    )
    registry.register(
        spec_artifacts_write_file(),
        lambda call: handle_artifacts_write_file(call, guard=guard),
    )
