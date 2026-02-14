"""Typed schemas for sandbox runner API payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class SandboxInputFile(TypedDict):
    path: str
    content_b64: str


class SandboxRunRequest(TypedDict):
    language: str
    code: str
    timeout_s: int
    input_files: list[SandboxInputFile]


class SandboxOutputFile(TypedDict):
    path: str
    content_b64: str
    size: int


class SandboxRunResponse(TypedDict, total=False):
    id: str
    exit_code: int
    timed_out: bool
    duration_ms: int
    stdout: str
    stderr: str
    output_files: list[SandboxOutputFile]


@dataclass(frozen=True)
class SandboxArtifact:
    path: str
    size: int
