"""Tool registry and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
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

    def call(self, call: ToolCall, require_approval: bool = False) -> ToolResult:
        if call.tool not in self._handlers:
            result = ToolResult(
                content=[{"type": "text", "text": f"Unknown tool: {call.tool}"}],
                is_error=True,
                meta={"status": "unknown_tool"},
            )
            self.audit_sink.record(call, result, "deny")
            return result

        decision = self.policy.decide(call)
        if decision == "deny":
            result = ToolResult(
                content=[{"type": "text", "text": "Tool execution denied."}],
                is_error=True,
                meta={"status": "denied"},
            )
            self.audit_sink.record(call, result, decision)
            return result
        if decision == "ask":
            if require_approval:
                result = ToolResult(
                    content=[{"type": "text", "text": "Tool execution requires approval."}],
                    is_error=True,
                    meta={"status": "approval_required"},
                )
                self.audit_sink.record(call, result, decision)
                return result
            result = ToolResult(
                content=[{"type": "text", "text": "Tool execution not approved."}],
                is_error=True,
                meta={"status": "approval_missing"},
            )
            self.audit_sink.record(call, result, decision)
            return result

        self._apply_workspace_guard(call)
        handler = self._handlers[call.tool]
        result = handler(call)
        self.audit_sink.record(call, result, decision)
        return result

    def _apply_workspace_guard(self, call: ToolCall) -> None:
        if not self.workspace_guard:
            return
        if call.tool.startswith("filesystem."):
            for key in ("path", "root"):
                value = call.args.get(key)
                if isinstance(value, str):
                    self.workspace_guard.assert_in_workspace(value)
        if call.tool == "process.exec":
            cwd = call.args.get("cwd")
            if isinstance(cwd, str):
                self.workspace_guard.assert_in_workspace(cwd)
