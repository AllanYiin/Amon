"""Sandbox configuration keys and defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SANDBOX_SECTION = "sandbox"
ENABLED = "enabled"
RUNNER_URL = "runner_url"
DEFAULT_IMAGE = "default_image"
TIMEOUT_SECONDS = "timeout_seconds"
MEMORY_MB = "memory_mb"
CPU_CORES = "cpu_cores"
PIDS_LIMIT = "pids_limit"
MAX_OUTPUT_TOTAL_MB = "max_output_total_mb"
MAX_STDOUT_KB = "max_stdout_kb"
MAX_STDERR_KB = "max_stderr_kb"


DEFAULT_SANDBOX_CONFIG: dict[str, Any] = {
    ENABLED: False,
    RUNNER_URL: "http://127.0.0.1:8088",
    DEFAULT_IMAGE: "python:3.12-slim",
    TIMEOUT_SECONDS: 30,
    MEMORY_MB: 512,
    CPU_CORES: 1.0,
    PIDS_LIMIT: 128,
    MAX_OUTPUT_TOTAL_MB: 20,
    MAX_STDOUT_KB: 256,
    MAX_STDERR_KB: 256,
}


@dataclass(frozen=True)
class SandboxRuntimeConfig:
    enabled: bool
    runner_url: str
    default_image: str
    timeout_seconds: int
    memory_mb: int
    cpu_cores: float
    pids_limit: int
    max_output_total_mb: int
    max_stdout_kb: int
    max_stderr_kb: int


def parse_sandbox_config(config: Mapping[str, Any]) -> SandboxRuntimeConfig:
    """Parse effective sandbox config from merged amon config payload."""
    section = config.get(SANDBOX_SECTION, {}) if isinstance(config, Mapping) else {}
    if not isinstance(section, Mapping):
        section = {}

    values = {**DEFAULT_SANDBOX_CONFIG, **section}
    return SandboxRuntimeConfig(
        enabled=bool(values[ENABLED]),
        runner_url=str(values[RUNNER_URL]),
        default_image=str(values[DEFAULT_IMAGE]),
        timeout_seconds=int(values[TIMEOUT_SECONDS]),
        memory_mb=int(values[MEMORY_MB]),
        cpu_cores=float(values[CPU_CORES]),
        pids_limit=int(values[PIDS_LIMIT]),
        max_output_total_mb=int(values[MAX_OUTPUT_TOTAL_MB]),
        max_stdout_kb=int(values[MAX_STDOUT_KB]),
        max_stderr_kb=int(values[MAX_STDERR_KB]),
    )
