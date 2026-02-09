"""Filesystem builtin tools."""

from __future__ import annotations

from pathlib import Path
import os
import re
from typing import Any

from ..types import ToolCall, ToolResult, ToolSpec


def spec_filesystem_read() -> ToolSpec:
    return ToolSpec(
        name="filesystem.read",
        description="Read a UTF-8 text file within the workspace. Use for code/config/doc reading.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5_000_000,
                    "default": 200_000,
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_filesystem_read(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    max_bytes = int(call.args.get("max_bytes", 200_000))
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"讀取檔案失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return ToolResult(
        content=[{"type": "text", "text": text}],
        meta={"truncated": truncated, "bytes": len(data)},
    )


def spec_filesystem_list() -> ToolSpec:
    return ToolSpec(
        name="filesystem.list",
        description="List directory entries within the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_entries": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10_000,
                    "default": 500,
                },
                "include_hidden": {"type": "boolean", "default": False},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_filesystem_list(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    max_entries = int(call.args.get("max_entries", 500))
    include_hidden = bool(call.args.get("include_hidden", False))
    items: list[dict[str, Any]] = []
    try:
        for name in sorted(os.listdir(path)):
            if not include_hidden and name.startswith("."):
                continue
            full = os.path.join(path, name)
            items.append(
                {"name": name, "type": "dir" if os.path.isdir(full) else "file"}
            )
            if len(items) >= max_entries:
                break
    except FileNotFoundError:
        return ToolResult(
            content=[{"type": "text", "text": f"找不到目錄：{path}"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"列出目錄失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    lines = [f"{item['type']}\t{item['name']}" for item in items]
    return ToolResult(
        content=[{"type": "text", "text": "\n".join(lines)}],
        meta={"count": len(items)},
    )


def spec_filesystem_grep() -> ToolSpec:
    return ToolSpec(
        name="filesystem.grep",
        description="Search for a regex pattern in files under a root directory (workspace-bounded).",
        input_schema={
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "pattern": {"type": "string"},
                "file_glob": {"type": "string", "default": "**/*"},
                "max_hits": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50_000,
                    "default": 2000,
                },
            },
            "required": ["root", "pattern"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_filesystem_grep(call: ToolCall) -> ToolResult:
    root = call.args.get("root")
    pattern = call.args.get("pattern")
    if not isinstance(root, str) or not root:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 root 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(pattern, str) or not pattern:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 pattern 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    file_glob = call.args.get("file_glob", "**/*")
    max_hits = int(call.args.get("max_hits", 2000))

    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"無效的正則表達式：{exc}"}],
            is_error=True,
            meta={"status": "invalid_pattern"},
        )

    hits: list[str] = []
    for dirpath, _, filenames in os.walk(os.path.expanduser(root)):
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if file_glob not in ("**/*", "*"):
                if file_glob.startswith("*.") and not filename.endswith(file_glob[1:]):
                    continue
            try:
                data = Path(full).read_bytes()[:2_000_000]
                text = data.decode("utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    hits.append(f"{rel}:{lineno}:{line[:300]}")
                    if len(hits) >= max_hits:
                        return ToolResult(
                            content=[{"type": "text", "text": "\n".join(hits)}],
                            meta={"truncated": True, "hits": len(hits)},
                        )
    return ToolResult(
        content=[{"type": "text", "text": "\n".join(hits)}],
        meta={"truncated": False, "hits": len(hits)},
    )
