"""Process builtin tools."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import os
from pathlib import Path
import shlex
import subprocess
from typing import Any

from ..types import ToolCall, ToolResult, ToolSpec


@dataclass
class _ProcessHandle:
    process: subprocess.Popen[str]
    command: str
    cwd: str | None = None


_PROCESS_REGISTRY: dict[int, _ProcessHandle] = {}


def spec_process_exec() -> ToolSpec:
    return ToolSpec(
        name="process.exec",
        description="Execute a command and return stdout/stderr.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeout": {"type": "number", "minimum": 0},
                "env": {"type": "object"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def handle_process_exec(call: ToolCall, *, allowlist: tuple[str, ...] = ()) -> ToolResult:
    command = call.args.get("command")
    if not isinstance(command, str) or not command:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 command 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if allowlist and not _matches_allowlist(command, allowlist):
        return ToolResult(
            content=[{"type": "text", "text": "指令不在允許清單內。"}],
            is_error=True,
            meta={"status": "not_allowed"},
        )
    cwd = call.args.get("cwd")
    timeout = call.args.get("timeout")
    env = call.args.get("env")
    if env is not None and not isinstance(env, dict):
        return ToolResult(
            content=[{"type": "text", "text": "env 參數必須是物件。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        result = subprocess.run(
            shlex.split(command),
            cwd=str(cwd) if cwd else None,
            env=_merge_env(env),
            timeout=float(timeout) if timeout is not None else None,
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
        meta={"returncode": result.returncode},
    )


def spec_process_spawn() -> ToolSpec:
    return ToolSpec(
        name="process.spawn",
        description="Spawn a command in the background and return a pid.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "env": {"type": "object"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def handle_process_spawn(call: ToolCall, *, allowlist: tuple[str, ...] = ()) -> ToolResult:
    command = call.args.get("command")
    if not isinstance(command, str) or not command:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 command 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if allowlist and not _matches_allowlist(command, allowlist):
        return ToolResult(
            content=[{"type": "text", "text": "指令不在允許清單內。"}],
            is_error=True,
            meta={"status": "not_allowed"},
        )
    cwd = call.args.get("cwd")
    env = call.args.get("env")
    if env is not None and not isinstance(env, dict):
        return ToolResult(
            content=[{"type": "text", "text": "env 參數必須是物件。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        process = subprocess.Popen(
            shlex.split(command),
            cwd=str(cwd) if cwd else None,
            env=_merge_env(env),
            text=True,
        )
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"啟動失敗：{exc}"}],
            is_error=True,
            meta={"status": "spawn_failed"},
        )
    handle = _ProcessHandle(process=process, command=command, cwd=str(cwd) if cwd else None)
    _PROCESS_REGISTRY[process.pid] = handle
    return ToolResult(
        content=[{"type": "text", "text": f"已啟動：{process.pid}"}],
        meta={"pid": process.pid},
    )


def spec_process_status() -> ToolSpec:
    return ToolSpec(
        name="process.status",
        description="Check status of a spawned process.",
        input_schema={
            "type": "object",
            "properties": {
                "pid": {"type": "integer"},
            },
            "required": ["pid"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_process_status(call: ToolCall) -> ToolResult:
    pid = call.args.get("pid")
    if not isinstance(pid, int):
        return ToolResult(
            content=[{"type": "text", "text": "缺少 pid 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    handle = _PROCESS_REGISTRY.get(pid)
    if handle:
        returncode = handle.process.poll()
        status = "running" if returncode is None else "exited"
        return ToolResult(
            content=[{"type": "text", "text": f"{pid}: {status}"}],
            meta={"pid": pid, "status": status, "returncode": returncode},
        )
    if _pid_exists(pid):
        return ToolResult(
            content=[{"type": "text", "text": f"{pid}: running"}],
            meta={"pid": pid, "status": "running"},
        )
    return ToolResult(
        content=[{"type": "text", "text": f"{pid}: not found"}],
        is_error=True,
        meta={"pid": pid, "status": "not_found"},
    )


def spec_process_kill() -> ToolSpec:
    return ToolSpec(
        name="process.kill",
        description="Terminate a process by pid.",
        input_schema={
            "type": "object",
            "properties": {
                "pid": {"type": "integer"},
                "signal": {"type": "integer", "default": 15},
            },
            "required": ["pid"],
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def handle_process_kill(call: ToolCall) -> ToolResult:
    pid = call.args.get("pid")
    if not isinstance(pid, int):
        return ToolResult(
            content=[{"type": "text", "text": "缺少 pid 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    signal = int(call.args.get("signal", 15))
    handle = _PROCESS_REGISTRY.get(pid)
    try:
        if handle:
            handle.process.terminate()
            return ToolResult(
                content=[{"type": "text", "text": f"已終止：{pid}"}],
                meta={"pid": pid, "status": "terminated"},
            )
        os.kill(pid, signal)
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"終止失敗：{exc}"}],
            is_error=True,
            meta={"status": "kill_failed"},
        )
    return ToolResult(
        content=[{"type": "text", "text": f"已送出 signal {signal} 至 {pid}"}],
        meta={"pid": pid, "status": "signaled", "signal": signal},
    )


def register_process_tools(registry: Any, *, allowlist: tuple[str, ...] = ()) -> None:
    registry.register(spec_process_exec(), lambda call: handle_process_exec(call, allowlist=allowlist))
    registry.register(spec_process_spawn(), lambda call: handle_process_spawn(call, allowlist=allowlist))
    registry.register(spec_process_status(), handle_process_status)
    registry.register(spec_process_kill(), handle_process_kill)


def _merge_env(env: dict[str, str] | None) -> dict[str, str]:
    base = os.environ.copy()
    if not env:
        return base
    for key, value in env.items():
        if value is None:
            continue
        base[str(key)] = str(value)
    return base


def _matches_allowlist(command: str, allowlist: tuple[str, ...]) -> bool:
    return any(fnmatch(command, pattern) for pattern in allowlist)


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
