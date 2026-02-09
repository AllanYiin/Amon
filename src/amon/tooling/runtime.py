"""Runtime registry builder for builtin + native tools."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .audit import AuditSink, FileAuditSink, NullAuditSink, default_audit_log_path
from .builtin import register_builtin_tools
from .native import NativeToolRuntime, load_native_runtimes
from .policy import ToolPolicy, WorkspaceGuard
from .registry import ToolRegistry


def build_registry(
    workspace_root: Path,
    base_dirs: Iterable[tuple[str, Path]],
    *,
    audit_sink: AuditSink | None = None,
) -> ToolRegistry:
    native_runtimes = load_native_runtimes(base_dirs)
    allow = ["filesystem.read", "filesystem.list", "filesystem.grep"]
    ask: list[str] = []
    deny: list[str] = []
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
