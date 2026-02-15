"""Tool registry and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable

from .audit import AuditSink, NullAuditSink
from .policy import ToolPolicy, WorkspaceGuard
from .types import ToolCall, ToolResult, ToolSpec


ToolHandler = Callable[[ToolCall], ToolResult]


@dataclass
class ToolRegistry:
    """Registry for tool specs and handlers."""

    policy: ToolPolicy = field(default_factory=ToolPolicy)
    workspace_guard: WorkspaceGuard | None = None
    audit_sink: AuditSink = field(default_factory=NullAuditSink)
    _handlers: dict[str, ToolHandler] = field(default_factory=dict, init=False)
    _specs: dict[str, ToolSpec] = field(default_factory=dict, init=False)

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    def list_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def get_spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def get_handler(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def call(self, call: ToolCall, require_approval: bool = False) -> ToolResult:
        start = time.monotonic()
        if call.tool not in self._handlers:
            result = ToolResult(
                content=[{"type": "text", "text": f"Unknown tool: {call.tool}"}],
                is_error=True,
                meta={"status": "unknown_tool"},
            )
            self.audit_sink.record(
                call,
                result,
                "deny",
                duration_ms=_duration_ms(start),
                source="unknown",
            )
            return result

        spec = self._specs.get(call.tool)
        source = _resolve_source(spec)
        decision, reason = self.policy.explain(call)
        if decision == "deny":
            result = ToolResult(
                content=[{"type": "text", "text": f"Tool execution denied: {reason}"}],
                is_error=True,
                meta={"status": "denied", "reason": reason},
            )
            self.audit_sink.record(
                call,
                result,
                decision,
                duration_ms=_duration_ms(start),
                source=source,
            )
            return result
        if decision == "ask":
            if require_approval:
                result = ToolResult(
                    content=[{"type": "text", "text": f"Tool execution requires approval: {reason}"}],
                    is_error=True,
                    meta={"status": "approval_required", "reason": reason},
                )
                self.audit_sink.record(
                    call,
                    result,
                    decision,
                    duration_ms=_duration_ms(start),
                    source=source,
                )
                return result
            result = ToolResult(
                content=[{"type": "text", "text": f"Tool execution not approved: {reason}"}],
                is_error=True,
                meta={"status": "approval_missing", "reason": reason},
            )
            self.audit_sink.record(
                call,
                result,
                decision,
                duration_ms=_duration_ms(start),
                source=source,
            )
            return result

        self._apply_workspace_guard(call)
        handler = self._handlers[call.tool]
        result = handler(call)
        self.audit_sink.record(
            call,
            result,
            decision,
            duration_ms=_duration_ms(start),
            source=source,
        )
        return result

    def _apply_workspace_guard(self, call: ToolCall) -> None:
        if not self.workspace_guard:
            return
        if call.tool.startswith("filesystem."):
            for key in ("path", "root"):
                value = call.args.get(key)
                if isinstance(value, str):
                    self.workspace_guard.assert_in_workspace(value)
        if call.tool in {"process.exec", "terminal.exec", "terminal.session.start"}:
            cwd = call.args.get("cwd")
            if isinstance(cwd, str):
                self.workspace_guard.assert_in_workspace(cwd)


def _resolve_source(spec: ToolSpec | None) -> str:
    if not spec:
        return "unknown"
    annotations = spec.annotations or {}
    if annotations.get("native"):
        return "native"
    if annotations.get("builtin"):
        return "builtin"
    return "builtin"


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))
