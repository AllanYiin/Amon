"""Built-in tooling registry and handlers."""

from __future__ import annotations

from pathlib import Path

from .audit import FileAuditSink, default_audit_log_path
from .policy import ToolPolicy, WorkspaceGuard
from .registry import ToolRegistry
from .builtins.artifacts import register_artifacts_tools
from .builtins.audit_tools import register_audit_tools
from .builtins.filesystem import register_filesystem_tools
from .builtins.memory import MemoryStore, register_memory_tools
from .builtins.process import register_process_tools
from .builtins.sandbox import register_sandbox_tools
from .builtins.terminal import register_terminal_tools
from .builtins.web import WebPolicy, register_web_tools


def build_registry(workspace_root: Path) -> ToolRegistry:
    registry = ToolRegistry(
        policy=ToolPolicy(
            allow=(
                "filesystem.read",
                "filesystem.list",
                "filesystem.grep",
                "filesystem.glob",
                "memory.search",
            ),
            ask=(
                "filesystem.write",
                "filesystem.move",
                "filesystem.copy",
                "web.fetch",
                "web.search",
                "sandbox.run",
            ),
            deny=(
                "filesystem.delete",
                "process.exec",
                "terminal.exec",
                "terminal.session.start",
                "terminal.session.exec",
                "terminal.session.stop",
            ),
        ),
        workspace_guard=WorkspaceGuard(workspace_root=workspace_root),
        audit_sink=FileAuditSink(default_audit_log_path()),
    )
    register_builtin_tools(registry, workspace_root=workspace_root)
    return registry


def register_builtin_tools(registry: ToolRegistry, *, workspace_root: Path | None = None) -> None:
    workspace_root = workspace_root or Path.cwd()
    register_filesystem_tools(registry)
    register_process_tools(registry)
    register_sandbox_tools(registry, project_path=workspace_root, config={})
    register_terminal_tools(registry)
    register_web_tools(registry, policy=WebPolicy())
    register_memory_tools(registry, store=MemoryStore(base_dir=Path("~/.amon/memory").expanduser()))
    register_artifacts_tools(registry, guard=registry.workspace_guard)
    register_audit_tools(
        registry,
        log_path=default_audit_log_path(),
        guard=registry.workspace_guard,
    )
