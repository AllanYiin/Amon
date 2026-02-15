"""Terminal builtin tool with shell semantics."""

from __future__ import annotations

import os
from shutil import which
import subprocess
from typing import Any

from ..types import ToolCall, ToolResult, ToolSpec


def spec_terminal_exec() -> ToolSpec:
    return ToolSpec(
        name="terminal.exec",
        description="Execute a shell command (supports pipes/redirection/&&).",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeout": {"type": "number", "minimum": 0},
                "env": {"type": "object"},
                "shell": {"type": "string"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def handle_terminal_exec(call: ToolCall) -> ToolResult:
    command = call.args.get("command")
    if not isinstance(command, str) or not command:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 command 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    env = call.args.get("env")
    if env is not None and not isinstance(env, dict):
        return ToolResult(
            content=[{"type": "text", "text": "env 參數必須是物件。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )

    shell_binary = _resolve_shell_binary(call.args.get("shell"))
    if shell_binary is None:
        return ToolResult(
            content=[{"type": "text", "text": "找不到可用 shell（預期 bash 或 sh）。"}],
            is_error=True,
            meta={"status": "exec_failed"},
        )

    try:
        result = subprocess.run(
            [shell_binary, "-lc", command],
            cwd=_as_cwd(call.args.get("cwd")),
            env=_merge_env(env),
            timeout=float(call.args["timeout"]) if call.args.get("timeout") is not None else None,
            text=True,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"執行失敗：{exc}"}],
            is_error=True,
            meta={"status": "exec_failed"},
        )

    output = "\n".join([result.stdout or "", result.stderr or ""]).strip()
    return ToolResult(
        content=[{"type": "text", "text": output}],
        meta={
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "shell": shell_binary,
        },
    )


def register_terminal_tools(registry: Any) -> None:
    registry.register(spec_terminal_exec(), handle_terminal_exec)


def _resolve_shell_binary(shell: Any) -> str | None:
    if isinstance(shell, str) and shell:
        requested = shell.strip()
        candidate = which(requested)
        if candidate:
            return candidate
    for fallback in ("bash", "sh"):
        candidate = which(fallback)
        if candidate:
            return candidate
    return None


def _merge_env(env: dict[str, str] | None) -> dict[str, str]:
    merged = os.environ.copy()
    if not env:
        return merged
    for key, value in env.items():
        if value is None:
            continue
        merged[str(key)] = str(value)
    return merged


def _as_cwd(cwd: Any) -> str | None:
    if cwd is None:
        return None
    return str(cwd)
