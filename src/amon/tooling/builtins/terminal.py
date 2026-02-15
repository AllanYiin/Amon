"""Terminal builtin tool with shell semantics."""

from __future__ import annotations

import os
from shutil import which
import subprocess
import threading
import uuid
from typing import Any

from ..types import ToolCall, ToolResult, ToolSpec


_DONE_PREFIX = "__AMON_DONE__:"
_DEFAULT_MAX_OUTPUT_CHARS = 12_000


class _TerminalSession:
    def __init__(self, process: subprocess.Popen[str], shell: str, max_output_chars: int) -> None:
        self.process = process
        self.shell = shell
        self.max_output_chars = max_output_chars
        self.lock = threading.Lock()


_SESSION_REGISTRY: dict[str, _TerminalSession] = {}
_SESSION_REGISTRY_LOCK = threading.Lock()


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


def spec_terminal_session_start() -> ToolSpec:
    return ToolSpec(
        name="terminal.session.start",
        description="Start a stateful interactive shell session.",
        input_schema={
            "type": "object",
            "properties": {
                "cwd": {"type": "string"},
                "env": {"type": "object"},
                "shell": {"type": "string"},
                "max_output_chars": {"type": "integer", "minimum": 256, "maximum": 100000},
            },
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def spec_terminal_session_exec() -> ToolSpec:
    return ToolSpec(
        name="terminal.session.exec",
        description="Execute a command inside a stateful terminal session.",
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "command": {"type": "string"},
            },
            "required": ["session_id", "command"],
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def spec_terminal_session_stop() -> ToolSpec:
    return ToolSpec(
        name="terminal.session.stop",
        description="Stop a stateful terminal session.",
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
            },
            "required": ["session_id"],
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


def handle_terminal_session_start(call: ToolCall, *, allowlist: tuple[str, ...] = ()) -> ToolResult:
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

    max_output_chars = int(call.args.get("max_output_chars") or _DEFAULT_MAX_OUTPUT_CHARS)
    if max_output_chars < 256:
        max_output_chars = 256

    try:
        process = subprocess.Popen(
            [shell_binary, "--noprofile", "--norc", "-i"],
            cwd=_as_cwd(call.args.get("cwd")),
            env=_merge_env(env),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"啟動 session 失敗：{exc}"}],
            is_error=True,
            meta={"status": "exec_failed"},
        )

    session = _TerminalSession(process=process, shell=shell_binary, max_output_chars=max_output_chars)
    session_id = str(uuid.uuid4())
    with _SESSION_REGISTRY_LOCK:
        _SESSION_REGISTRY[session_id] = session

    return ToolResult(
        content=[{"type": "text", "text": session_id}],
        meta={"session_id": session_id, "shell": shell_binary, "max_output_chars": max_output_chars},
    )


def handle_terminal_session_exec(call: ToolCall, *, allowlist: tuple[str, ...] = ()) -> ToolResult:
    session_id = call.args.get("session_id")
    command = call.args.get("command")
    if not isinstance(session_id, str) or not session_id:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 session_id 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(command, str) or not command:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 command 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if allowlist and not _matches_allowlist(command, allowlist):
        return ToolResult(
            content=[{"type": "text", "text": "command 不在 allowlist。"}],
            is_error=True,
            meta={"status": "forbidden", "reason": "not_in_allowlist"},
        )

    with _SESSION_REGISTRY_LOCK:
        session = _SESSION_REGISTRY.get(session_id)
    if session is None:
        return ToolResult(
            content=[{"type": "text", "text": "找不到 terminal session。"}],
            is_error=True,
            meta={"status": "not_found", "session_id": session_id},
        )

    done_marker = f"{_DONE_PREFIX}{uuid.uuid4().hex}"
    truncated = False
    chunks: list[str] = []

    with session.lock:
        process = session.process
        if process.poll() is not None:
            _remove_session(session_id)
            return ToolResult(
                content=[{"type": "text", "text": "terminal session 已結束。"}],
                is_error=True,
                meta={"status": "session_closed", "session_id": session_id},
            )
        if process.stdin is None or process.stdout is None:
            _remove_session(session_id)
            return ToolResult(
                content=[{"type": "text", "text": "terminal session I/O 不可用。"}],
                is_error=True,
                meta={"status": "session_closed", "session_id": session_id},
            )

        process.stdin.write(f"{command}\n")
        process.stdin.write(f"echo {done_marker}:$?\n")
        process.stdin.flush()

        returncode = -1
        while True:
            line = process.stdout.readline()
            if line == "":
                _remove_session(session_id)
                return ToolResult(
                    content=[{"type": "text", "text": "terminal session 已中斷。"}],
                    is_error=True,
                    meta={"status": "session_closed", "session_id": session_id},
                )

            if done_marker in line:
                marker_index = line.find(done_marker)
                if marker_index > 0:
                    chunks.append(line[:marker_index])
                rc_text = line[marker_index + len(done_marker) + 1 :].strip()
                try:
                    returncode = int(rc_text)
                except ValueError:
                    returncode = -1
                break

            chunks.append(line)
            if sum(len(item) for item in chunks) > session.max_output_chars:
                truncated = True
                break

        if truncated:
            while True:
                line = process.stdout.readline()
                if line == "" or done_marker in line:
                    if line and done_marker in line:
                        rc_text = line.split(f"{done_marker}:", 1)[-1].strip()
                        try:
                            returncode = int(rc_text)
                        except ValueError:
                            returncode = -1
                    break

    output = "".join(chunks)
    if len(output) > session.max_output_chars:
        output = output[: session.max_output_chars]
    if truncated:
        output = f"{output}\n...[output truncated]"

    return ToolResult(
        content=[{"type": "text", "text": output.strip()}],
        meta={
            "session_id": session_id,
            "returncode": returncode,
            "truncated": truncated,
            "max_output_chars": session.max_output_chars,
        },
    )


def handle_terminal_session_stop(call: ToolCall) -> ToolResult:
    session_id = call.args.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 session_id 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )

    with _SESSION_REGISTRY_LOCK:
        session = _SESSION_REGISTRY.pop(session_id, None)
    if session is None:
        return ToolResult(
            content=[{"type": "text", "text": "找不到 terminal session。"}],
            is_error=True,
            meta={"status": "not_found", "session_id": session_id},
        )

    with session.lock:
        _cleanup_session_process(session.process)

    return ToolResult(content=[{"type": "text", "text": "ok"}], meta={"session_id": session_id, "stopped": True})


def register_terminal_tools(registry: Any, *, allowlist: tuple[str, ...] = ()) -> None:
    registry.register(spec_terminal_exec(), handle_terminal_exec)
    registry.register(spec_terminal_session_start(), lambda call: handle_terminal_session_start(call, allowlist=allowlist))
    registry.register(spec_terminal_session_exec(), lambda call: handle_terminal_session_exec(call, allowlist=allowlist))
    registry.register(spec_terminal_session_stop(), handle_terminal_session_stop)


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


def _matches_allowlist(command: str, allowlist: tuple[str, ...]) -> bool:
    from fnmatch import fnmatch

    return any(fnmatch(command, pattern) for pattern in allowlist)


def _cleanup_session_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    if process.stdin is not None:
        process.stdin.close()
    if process.stdout is not None:
        process.stdout.close()


def _remove_session(session_id: str) -> None:
    with _SESSION_REGISTRY_LOCK:
        session = _SESSION_REGISTRY.pop(session_id, None)
    if session is None:
        return
    with session.lock:
        _cleanup_session_process(session.process)
