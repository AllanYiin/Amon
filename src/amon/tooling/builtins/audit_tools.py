"""Audit query builtin tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..audit import default_audit_log_path
from ..policy import WorkspaceGuard
from ..types import ToolCall, ToolResult, ToolSpec


def spec_audit_log_query() -> ToolSpec:
    return ToolSpec(
        name="audit.log_query",
        description="Query tool audit log entries.",
        input_schema={
            "type": "object",
            "properties": {
                "tool": {"type": "string"},
                "decision": {"type": "string"},
                "since_ts_ms": {"type": "integer"},
                "until_ts_ms": {"type": "integer"},
                "limit": {"type": "integer", "default": 100},
            },
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_audit_log_query(call: ToolCall, *, log_path: Path) -> ToolResult:
    tool_name = call.args.get("tool")
    decision = call.args.get("decision")
    since_ts_ms = call.args.get("since_ts_ms")
    until_ts_ms = call.args.get("until_ts_ms")
    limit = int(call.args.get("limit", 100))
    entries: list[dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(entries) >= limit:
                    break
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if tool_name and item.get("tool") != tool_name:
                    continue
                if decision and item.get("decision") != decision:
                    continue
                if since_ts_ms is not None and item.get("ts_ms", 0) < since_ts_ms:
                    continue
                if until_ts_ms is not None and item.get("ts_ms", 0) > until_ts_ms:
                    continue
                entries.append(item)
    except FileNotFoundError:
        return ToolResult(
            content=[{"type": "text", "text": "找不到 audit log。"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"讀取 audit log 失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(entries, ensure_ascii=False)}],
        meta={"count": len(entries)},
    )


def spec_audit_export() -> ToolSpec:
    return ToolSpec(
        name="audit.export",
        description="Export audit log entries to a JSONL file.",
        input_schema={
            "type": "object",
            "properties": {
                "output_path": {"type": "string"},
                "limit": {"type": "integer", "default": 1000},
            },
            "required": ["output_path"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_audit_export(call: ToolCall, *, log_path: Path, guard: WorkspaceGuard | None) -> ToolResult:
    output_path = call.args.get("output_path")
    if not isinstance(output_path, str) or not output_path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 output_path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    limit = int(call.args.get("limit", 1000))
    try:
        if guard:
            guard.assert_in_workspace(output_path)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with log_path.open("r", encoding="utf-8") as source, output.open("w", encoding="utf-8") as sink:
            for line in source:
                if count >= limit:
                    break
                sink.write(line)
                count += 1
    except FileNotFoundError:
        return ToolResult(
            content=[{"type": "text", "text": "找不到 audit log。"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    except (OSError, ValueError) as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"匯出失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(
        content=[{"type": "text", "text": f"已匯出 {count} 筆紀錄到 {output_path}"}],
        meta={"count": count},
    )


def register_audit_tools(
    registry: Any,
    *,
    log_path: Path | None = None,
    guard: WorkspaceGuard | None,
) -> None:
    resolved_log_path = log_path or default_audit_log_path()
    registry.register(
        spec_audit_log_query(),
        lambda call: handle_audit_log_query(call, log_path=resolved_log_path),
    )
    registry.register(
        spec_audit_export(),
        lambda call: handle_audit_export(call, log_path=resolved_log_path, guard=guard),
    )
