"""Sandbox design-time interfaces (no runtime side effects in this stage)."""

from .client import (
    SandboxClientError,
    SandboxHTTPError,
    SandboxProtocolError,
    SandboxRunnerClient,
    SandboxRunnerSettings,
    SandboxTimeoutError,
    build_input_file,
    decode_output_files,
    parse_runner_settings,
)
from .config_keys import (
    API_KEY_ENV,
    BASE_URL,
    DEFAULT_SANDBOX_CONFIG,
    FEATURES,
    LIMITS,
    RUNNER_SECTION,
    SANDBOX_SECTION,
    TIMEOUT_SECONDS,
    SandboxRuntimeConfig,
    parse_sandbox_config,
)
from .path_rules import validate_relative_path
from .records import ensure_run_step_dirs, truncate_text, write_json
from .service import run_sandbox_step
from .staging import pack_input_files, rewrite_output_paths, unpack_output_files
from .types import SandboxArtifact, SandboxRunRequest, SandboxRunResponse

__all__ = [
    "SANDBOX_SECTION",
    "SandboxClientError",
    "SandboxHTTPError",
    "SandboxProtocolError",
    "SandboxRunnerClient",
    "SandboxRunnerSettings",
    "SandboxTimeoutError",
    "RUNNER_SECTION",
    "BASE_URL",
    "TIMEOUT_SECONDS",
    "API_KEY_ENV",
    "LIMITS",
    "FEATURES",
    "DEFAULT_SANDBOX_CONFIG",
    "SandboxRuntimeConfig",
    "build_input_file",
    "decode_output_files",
    "parse_runner_settings",
    "parse_sandbox_config",
    "validate_relative_path",
    "SandboxArtifact",
    "SandboxRunRequest",
    "SandboxRunResponse",
    "pack_input_files",
    "rewrite_output_paths",
    "unpack_output_files",
    "write_json",
    "ensure_run_step_dirs",
    "truncate_text",
    "run_sandbox_step",
]
