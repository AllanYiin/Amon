"""Typed schemas for sandbox runner API payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class SandboxLimits(TypedDict):
    timeout_seconds: int
    cpu_cores: float
    memory_mb: int
    pids: int
    max_stdout_kb: int
    max_stderr_kb: int
    max_output_total_mb: int


class SandboxRunRequest(TypedDict):
    request_id: str
    project_id: str
    image: str
    command: list[str]
    working_dir: str
    env: dict[str, str]
    input_files: list[str]
    output_files: list[str]
    limits: SandboxLimits


class SandboxOutputFile(TypedDict):
    path: str
    size: int
    sha256: str
    mime: str


class SandboxTruncated(TypedDict):
    stdout: bool
    stderr: bool


class SandboxError(TypedDict):
    code: str
    message: str


class SandboxRunResponse(TypedDict, total=False):
    request_id: str
    status: str
    exit_code: int
    timed_out: bool
    started_at: str
    finished_at: str
    stdout: str
    stderr: str
    truncated: SandboxTruncated
    outputs: list[SandboxOutputFile]
    error: SandboxError


@dataclass(frozen=True)
class SandboxArtifact:
    path: str
    size: int
    sha256: str
    mime: str
