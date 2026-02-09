"""Built-in tooling registry and handlers."""

from __future__ import annotations

from pathlib import Path

from .audit import FileAuditSink, default_audit_log_path
from .policy import ToolPolicy, WorkspaceGuard
from .registry import ToolRegistry
from .builtins.filesystem import (
    handle_filesystem_grep,
    handle_filesystem_list,
    handle_filesystem_read,
    spec_filesystem_grep,
    spec_filesystem_list,
    spec_filesystem_read,
)


def build_registry(workspace_root: Path) -> ToolRegistry:
    registry = ToolRegistry(
        policy=ToolPolicy(allow=("filesystem.read", "filesystem.list", "filesystem.grep")),
        workspace_guard=WorkspaceGuard(workspace_root=workspace_root),
        audit_sink=FileAuditSink(default_audit_log_path()),
    )
    register_builtin_tools(registry)
    return registry


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(spec_filesystem_read(), handle_filesystem_read)
    registry.register(spec_filesystem_list(), handle_filesystem_list)
    registry.register(spec_filesystem_grep(), handle_filesystem_grep)
