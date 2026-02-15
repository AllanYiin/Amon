"""Runtime registry builder for builtin + native tools."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .audit import AuditSink, FileAuditSink, NullAuditSink, default_audit_log_path
from .builtin import register_builtin_tools
from .native import NativeToolRuntime, load_native_runtimes
from .policy import ToolPolicy, WorkspaceGuard
from .registry import ToolRegistry


LOW_RISK_ALLOW_TOOLS = (
    "filesystem.read",
    "filesystem.list",
    "filesystem.grep",
    "filesystem.glob",
    "memory.search",
)

MEDIUM_RISK_ASK_TOOLS = (
    "filesystem.write",
    "filesystem.move",
    "filesystem.copy",
    "web.fetch",
    "web.search",
    "sandbox.run",
)

HIGH_RISK_DENY_TOOLS = (
    "filesystem.delete",
    "process.exec",
    "terminal.exec",
    "terminal.session.start",
    "terminal.session.exec",
    "terminal.session.stop",
)


def build_registry(
    workspace_root: Path,
    base_dirs: Iterable[tuple[str, Path]],
    *,
    audit_sink: AuditSink | None = None,
) -> ToolRegistry:
    native_runtimes = load_native_runtimes(base_dirs)
    allow = list(LOW_RISK_ALLOW_TOOLS)
    ask: list[str] = list(MEDIUM_RISK_ASK_TOOLS)
    deny: list[str] = list(HIGH_RISK_DENY_TOOLS)
    for runtime in native_runtimes:
        permission = runtime.manifest.effective_permission
        if permission == "allow":
            allow.append(runtime.manifest.namespaced_name)
        elif permission == "ask":
            ask.append(runtime.manifest.namespaced_name)
        else:
            deny.append(runtime.manifest.namespaced_name)
    registry = ToolRegistry(
        policy=ToolPolicy(allow=tuple(allow), ask=tuple(ask), deny=tuple(deny)),
        workspace_guard=WorkspaceGuard(workspace_root=workspace_root),
        audit_sink=audit_sink or FileAuditSink(default_audit_log_path()),
    )
    register_builtin_tools(registry)
    _register_native(registry, native_runtimes)
    return registry


def _register_native(registry: ToolRegistry, runtimes: Iterable[NativeToolRuntime]) -> None:
    for runtime in runtimes:
        registry.register(runtime.spec, runtime.handler)
