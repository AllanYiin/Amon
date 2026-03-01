"""Policy and workspace guard for tooling."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

from .types import Decision, ToolCall


@dataclass(frozen=True)
class ToolPolicy:
    """Policy matching for tool execution decisions (glob-style rules)."""

    allow: tuple[str, ...] = ()
    ask: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    def decide(self, call: ToolCall) -> Decision:
        if _first_match(call, self.deny):
            return "deny"
        if _first_match(call, self.ask):
            return "ask"
        if _first_match(call, self.allow):
            return "allow"
        return "deny"

    def explain(self, call: ToolCall) -> tuple[Decision, str]:
        deny_match = _first_match(call, self.deny)
        if deny_match:
            return "deny", f"符合 deny 規則：{deny_match}"
        ask_match = _first_match(call, self.ask)
        if ask_match:
            return "ask", f"符合 ask 規則：{ask_match}"
        allow_match = _first_match(call, self.allow)
        if allow_match:
            return "allow", f"符合 allow 規則：{allow_match}"
        return "deny", "未命中任何 allow 規則，預設拒絕"


_DEFAULT_DENY_GLOBS = (
    "**/.env",
    "**/.env.*",
    "**/.git/**",
    "**/.ssh/**",
    "**/*id_rsa*",
    "**/*.pem",
    "**/*.key",
    "**/secrets/**",
    "**/secrets.*",
    "**/*secret*",
    "**/*token*",
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
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            relative = os.path.relpath(
                _normalize_path_text(resolved),
                _normalize_path_text(root),
            ).replace("\\", "/")
        for pattern in self.deny_path_globs:
            if fnmatch(relative, pattern) or fnmatch(resolved.as_posix(), pattern):
                raise ValueError(f"Path is denied by policy: {resolved}")
        return resolved


def _first_match(call: ToolCall, patterns: Iterable[str]) -> str | None:
    for pattern in patterns:
        if _matches_pattern(call, pattern):
            return pattern
    return None


def _matches_pattern(call: ToolCall, pattern: str) -> bool:
    command = call.args.get("command") or call.args.get("cmd")
    command_pattern_prefix = f"{call.tool}:"
    if isinstance(command, str) and pattern.startswith(command_pattern_prefix):
        cmd_glob = pattern[len(command_pattern_prefix) :]
        return fnmatch(command, cmd_glob)
    return fnmatch(call.tool, pattern)


def _is_relative_to(path: Path, root: Path) -> bool:
    path_text = _normalize_path_text(path)
    root_text = _normalize_path_text(root)
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False

def _normalize_path_text(path: str | Path) -> str:
    text = os.path.abspath(str(path))
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    return os.path.normcase(os.path.normpath(text))
