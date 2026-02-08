"""Policy and workspace guard for tooling."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

from .types import ToolCall


Decision = str


@dataclass(frozen=True)
class ToolPolicy:
    """Policy matching for tool execution decisions."""

    allow: tuple[str, ...] = ()
    ask: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    def decide(self, call: ToolCall) -> Decision:
        if _matches_any(call, self.deny):
            return "deny"
        if _matches_any(call, self.ask):
            return "ask"
        if _matches_any(call, self.allow):
            return "allow"
        return "deny"


_DEFAULT_DENY_GLOBS = (
    "**/.env",
    "**/.env.*",
    "**/.ssh/**",
    "**/*.pem",
    "**/*.key",
    "**/secrets/**",
    "**/secrets.*",
    "**/*secret*",
)


@dataclass(frozen=True)
class WorkspaceGuard:
    """Guards filesystem access to a workspace root."""

    workspace_root: Path
    deny_path_globs: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_DENY_GLOBS)

    def assert_in_workspace(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser().resolve()
        root = self.workspace_root.expanduser().resolve()
        if not _is_relative_to(resolved, root):
            raise ValueError(f"Path is outside workspace: {resolved}")
        relative = resolved.relative_to(root).as_posix()
        for pattern in self.deny_path_globs:
            if fnmatch(relative, pattern) or fnmatch(resolved.as_posix(), pattern):
                raise ValueError(f"Path is denied by policy: {resolved}")
        return resolved


def _matches_any(call: ToolCall, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        if _matches_pattern(call, pattern):
            return True
    return False


def _matches_pattern(call: ToolCall, pattern: str) -> bool:
    if pattern.startswith("process.exec:"):
        if call.tool != "process.exec":
            return False
        cmd_glob = pattern.split(":", 1)[1]
        command = call.args.get("command")
        if not isinstance(command, str):
            return False
        return fnmatch(command, cmd_glob)
    return fnmatch(call.tool, pattern)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
