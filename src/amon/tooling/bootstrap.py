"""Registry bootstrap for builtin tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit import FileAuditSink, default_audit_log_path
from .builtins.artifacts import register_artifacts_tools
from .builtins.audit_tools import register_audit_tools
from .builtins.filesystem import register_filesystem_tools
from .builtins.memory import MemoryStore, register_memory_tools
from amon.sandbox.service import run_sandbox_step

from .builtins.process import register_process_tools
from .builtins.sandbox import register_sandbox_tools
from .builtins.terminal import build_sandbox_terminal_executor, register_terminal_tools
from .builtins.web import WebPolicy, register_web_tools
from .policy import ToolPolicy, WorkspaceGuard
from .registry import ToolRegistry


DEFAULT_ALLOW = (
    "filesystem.read",
    "filesystem.list",
    "filesystem.glob",
    "filesystem.grep",
    "memory.get",
    "memory.search",
    "artifacts.write_text",
    "artifacts.write_file",
)
DEFAULT_ASK = (
    "filesystem.write",
    "filesystem.patch",
    "filesystem.delete",
    "process.exec",
    "process.spawn",
    "terminal.exec",
    "terminal.session.start",
    "terminal.session.exec",
    "terminal.session.stop",
    "sandbox.run",
    "process.kill",
    "memory.put",
    "memory.delete",
    "web.fetch",
    "web.search",
    "audit.export",
)
DEFAULT_DENY: tuple[str, ...] = ()


def build_default_registry(workspace_root: Path, config: dict[str, Any] | None = None) -> ToolRegistry:
    config = config or {}
    allow = tuple(config.get("allow", DEFAULT_ALLOW))
    ask = tuple(config.get("ask", DEFAULT_ASK))
    deny = tuple(config.get("deny", DEFAULT_DENY))
    policy = ToolPolicy(allow=allow, ask=ask, deny=deny)
    guard = WorkspaceGuard(workspace_root=workspace_root)
    audit_path = config.get("audit_log_path")
    audit_sink = config.get("audit_sink") or FileAuditSink(
        audit_path if audit_path else default_audit_log_path()
    )
    registry = ToolRegistry(policy=policy, workspace_guard=guard, audit_sink=audit_sink)

    register_filesystem_tools(registry)
    register_process_tools(
        registry,
        allowlist=tuple(config.get("process_allowlist", ())),
    )
    register_sandbox_tools(registry, project_path=workspace_root, config=config)

    sandbox_features = config.get("sandbox", {}).get("runner", {}).get("features", {}) if isinstance(config.get("sandbox", {}), dict) else {}
    use_sandbox_for_terminal = bool(sandbox_features.get("use_for_terminal", False))
    sandbox_executor = None
    if use_sandbox_for_terminal:
        sandbox_executor = build_sandbox_terminal_executor(
            project_path=workspace_root,
            config=config,
            run_step=run_sandbox_step,
        )

    register_terminal_tools(
        registry,
        allowlist=tuple(config.get("terminal_allowlist", config.get("tooling", {}).get("terminal", {}).get("allowlist", ()))),
        sandbox_executor=sandbox_executor,
    )
    register_web_tools(
        registry,
        policy=WebPolicy(
            allowlist=tuple(config.get("web_allowlist", ())),
            denylist=tuple(config.get("web_denylist", ())),
        ),
    )
    memory_dir = config.get("memory_dir")
    store = MemoryStore(base_dir=Path(memory_dir) if memory_dir else _default_memory_dir())
    register_memory_tools(registry, store=store)
    register_artifacts_tools(registry, guard=guard)
    register_audit_tools(registry, log_path=audit_path, guard=guard)
    return registry


def _default_memory_dir() -> Path:
    base_dir = Path("~/.amon").expanduser()
    return base_dir / "memory"
