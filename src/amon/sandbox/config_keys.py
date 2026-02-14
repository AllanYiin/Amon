"""Sandbox configuration keys and defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SANDBOX_SECTION = "sandbox"
RUNNER_SECTION = "runner"
ENABLED = "enabled"
RUNNER_URL = "runner_url"
DEFAULT_IMAGE = "default_image"
BASE_URL = "base_url"
TIMEOUT_SECONDS = "timeout_s"
API_KEY_ENV = "api_key_env"
LIMITS = "limits"
FEATURES = "features"

DEFAULT_SANDBOX_CONFIG: dict[str, Any] = {
    RUNNER_SECTION: {
        BASE_URL: "http://127.0.0.1:8088",
        TIMEOUT_SECONDS: 30,
        API_KEY_ENV: None,
        LIMITS: {
            "max_input_files": 32,
            "max_input_total_kb": 5120,
            "max_output_files": 32,
            "max_output_total_kb": 5120,
        },
        FEATURES: {
            "enabled": False,
            "allow_artifact_write": False,
        },
    }
}


@dataclass(frozen=True)
class SandboxRuntimeConfig:
    enabled: bool
    runner_url: str
    default_image: str
    base_url: str
    timeout_seconds: int
    api_key_env: str | None
    memory_mb: int
    cpu_cores: float
    pids_limit: int
    max_output_total_mb: int
    max_stdout_kb: int
    max_stderr_kb: int
    limits: Mapping[str, Any]
    features: Mapping[str, Any]


def parse_sandbox_config(config: Mapping[str, Any]) -> SandboxRuntimeConfig:
    """Parse effective sandbox config from merged amon config payload."""
    section = config.get(SANDBOX_SECTION, {}) if isinstance(config, Mapping) else {}
    runner = section.get(RUNNER_SECTION, {}) if isinstance(section, Mapping) else {}
    if not isinstance(runner, Mapping):
        runner = {}

    defaults = DEFAULT_SANDBOX_CONFIG[RUNNER_SECTION]
    merged_limits = {**defaults[LIMITS], **(runner.get(LIMITS, {}) if isinstance(runner.get(LIMITS), Mapping) else {})}
    merged_features = {
        **defaults[FEATURES],
        **(runner.get(FEATURES, {}) if isinstance(runner.get(FEATURES), Mapping) else {}),
    }

    return SandboxRuntimeConfig(
        enabled=bool(section.get(ENABLED, merged_features.get("enabled", False))),
        runner_url=str(section.get(RUNNER_URL, runner.get(BASE_URL, defaults[BASE_URL]))),
        default_image=str(section.get(DEFAULT_IMAGE, "python:3.12-slim")),
        base_url=str(runner.get(BASE_URL, defaults[BASE_URL])),
        timeout_seconds=int(runner.get(TIMEOUT_SECONDS, defaults[TIMEOUT_SECONDS])),
        api_key_env=runner.get(API_KEY_ENV) or None,
        memory_mb=int(section.get("memory_mb", 512)),
        cpu_cores=float(section.get("cpu_cores", 1.0)),
        pids_limit=int(section.get("pids_limit", 128)),
        max_output_total_mb=int(section.get("max_output_total_mb", 20)),
        max_stdout_kb=int(section.get("max_stdout_kb", 256)),
        max_stderr_kb=int(section.get("max_stderr_kb", 256)),
        limits=merged_limits,
        features=merged_features,
    )
