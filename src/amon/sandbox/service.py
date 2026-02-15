"""Sandbox execution service with durable execution records."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from amon.fs.atomic import atomic_write_text

from .client import SandboxRunnerClient, parse_runner_settings
from .config_keys import parse_sandbox_config
from .records import ensure_run_step_dirs, truncate_text, write_json
from .staging import pack_input_files, rewrite_output_paths, unpack_output_files

_ALLOWED_PREFIXES = ["docs/", "audits/"]


def run_sandbox_step(
    *,
    project_path: Path,
    config: Mapping[str, Any],
    run_id: str,
    step_id: str,
    language: str,
    code: str,
    input_paths: list[str] | None = None,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    """Run code via sandbox runner and persist request/result/artifact records."""

    run_step_dir, artifacts_dir = ensure_run_step_dirs(project_path, run_id, step_id)

    code_path = run_step_dir / "code.py"
    atomic_write_text(code_path, code + "\n")

    runtime = parse_sandbox_config(config)
    settings = parse_runner_settings(config)
    client = SandboxRunnerClient(settings)

    packed_inputs, input_meta = pack_input_files(project_path, input_paths or [], limits=runtime.limits)

    request_record = {
        "run_id": run_id,
        "step_id": step_id,
        "language": language,
        "timeout_s": timeout_s or settings.timeout_s,
        "input_files": input_meta.get("files", []),
        "input_total_bytes": input_meta.get("total_bytes", 0),
    }
    write_json(run_step_dir / "request.json", request_record)

    result = client.run_code(
        language=language,
        code=code,
        timeout_s=timeout_s,
        input_files=packed_inputs,
    )

    rewritten = rewrite_output_paths(result.get("output_files", []), artifacts_dir.relative_to(project_path.resolve()).as_posix())
    written = unpack_output_files(project_path, rewritten, allowed_prefixes=_ALLOWED_PREFIXES)

    result_record = {
        "exit_code": result.get("exit_code"),
        "timed_out": bool(result.get("timed_out", False)),
        "duration_ms": result.get("duration_ms"),
        "stdout": truncate_text(str(result.get("stdout", "")), runtime.max_stdout_kb),
        "stderr": truncate_text(str(result.get("stderr", "")), runtime.max_stderr_kb),
        "request_id": result.get("request_id"),
        "job_id": result.get("job_id") or result.get("id"),
    }
    write_json(run_step_dir / "result.json", result_record)

    outputs_meta = [_file_metadata(path, project_path.resolve()) for path in written]
    manifest = {
        "run_id": run_id,
        "step_id": step_id,
        "outputs": outputs_meta,
        "result": {
            "exit_code": result_record["exit_code"],
            "timed_out": result_record["timed_out"],
            "duration_ms": result_record["duration_ms"],
        },
    }
    write_json(artifacts_dir / "manifest.json", manifest)

    return {
        "run_id": run_id,
        "step_id": step_id,
        "exit_code": result_record["exit_code"],
        "timed_out": result_record["timed_out"],
        "duration_ms": result_record["duration_ms"],
        "stdout": result_record["stdout"],
        "stderr": result_record["stderr"],
        "manifest_path": str((artifacts_dir / "manifest.json").resolve()),
        "outputs": outputs_meta,
    }


def _file_metadata(path: Path, project_root: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": path.resolve().relative_to(project_root).as_posix(),
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
