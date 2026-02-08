"""Amon native tool: text_upper."""

from __future__ import annotations

from amon.tooling.types import ToolCall, ToolResult, ToolSpec

TOOL_SPEC = ToolSpec(
    name="native:text_upper",
    description="text_upper native tool",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    output_schema={
        "type": "object",
        "properties": {"result": {"type": "string"}},
        "required": ["result"],
    },
    risk="low",
    annotations={"native": True},
)


def handle(call: ToolCall) -> ToolResult:
    text = call.args.get("text", "")
    if not isinstance(text, str):
        return ToolResult(
            content=[{"type": "text", "text": "text 必須是字串"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    result = text.upper()
    return ToolResult(
        content=[{"type": "text", "text": result}],
        is_error=False,
        meta={"status": "ok"},
    )
