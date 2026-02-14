"""Typed models for sandbox runner API."""

from __future__ import annotations

from typing import TypedDict


class RunInputFile(TypedDict):
    path: str
    content_b64: str


class RunOutputFile(TypedDict):
    path: str
    content_b64: str
    size: int


class RunRequest(TypedDict):
    language: str
    code: str
    timeout_s: int
    input_files: list[RunInputFile]


class RunResponse(TypedDict):
    id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    output_files: list[RunOutputFile]
