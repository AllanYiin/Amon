"""Sandbox execution service with durable execution records."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from amon.fs.atomic import atomic_write_text

from .client import SandboxRunnerClient, parse_runner_settings
from .config_keys import parse_sandbox_config
from .path_rules import validate_relative_path
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
    output_prefix: str | None = None,
    timeout_s: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run code via sandbox runner and persist request/result/artifact records."""

    run_step_dir, artifacts_dir = ensure_run_step_dirs(project_path, run_id, step_id)

    normalized_language = str(language).strip().lower()
    if normalized_language not in {"python", "bash"}:
        raise ValueError("language 只支援 python 或 bash")

    code_filename = "code.py" if normalized_language == "python" else "code.sh"
    code_path = run_step_dir / code_filename
    atomic_write_text(code_path, code + "\n")

    runtime = parse_sandbox_config(config)
    settings = parse_runner_settings(config)
    client = SandboxRunnerClient(settings)

    packed_inputs, input_meta = pack_input_files(project_path, input_paths or [], limits=runtime.limits)

    request_record = {
        "run_id": run_id,
        "step_id": step_id,
        "language": normalized_language,
        "timeout_s": timeout_s or settings.timeout_s,
        "input_files": input_meta.get("files", []),
        "input_total_bytes": input_meta.get("total_bytes", 0),
    }
    write_json(run_step_dir / "request.json", request_record)

    result = client.run_code(
        language=normalized_language,
        code=code,
        timeout_s=timeout_s,
        input_files=packed_inputs,
    )

    output_base = _resolve_output_base(
        project_path=project_path.resolve(),
        default_dir=artifacts_dir,
        output_prefix=output_prefix,
    )
    rewritten = rewrite_output_paths(result.get("output_files", []), output_base)
    _ensure_output_targets(
        project_root=project_path.resolve(),
        rewritten_output_files=rewritten,
        overwrite=overwrite,
    )
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
    manifest_path = project_path.resolve() / output_base / "manifest.json"
    write_json(manifest_path, manifest)

    return {
        "run_id": run_id,
        "step_id": step_id,
        "exit_code": result_record["exit_code"],
        "timed_out": result_record["timed_out"],
        "duration_ms": result_record["duration_ms"],
        "stdout": result_record["stdout"],
        "stderr": result_record["stderr"],
        "manifest_path": str(manifest_path.resolve()),
        "written_files": [str(path.resolve()) for path in written],
        "outputs": outputs_meta,
    }


def _ensure_output_targets(*, project_root: Path, rewritten_output_files: list[dict[str, Any]], overwrite: bool) -> None:
    if overwrite:
        return
    for item in rewritten_output_files:
        rel_path = validate_relative_path(str(item.get("path", "")))
        target = (project_root / rel_path).resolve()
        if target.exists():
            raise FileExistsError(f"output 檔案已存在，請設定 overwrite=true：{rel_path}")


def _file_metadata(path: Path, project_root: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": path.resolve().relative_to(project_root).as_posix(),
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _resolve_output_base(*, project_path: Path, default_dir: Path, output_prefix: str | None) -> str:
    if output_prefix:
        normalized = validate_relative_path(output_prefix.rstrip("/"))
    else:
        normalized = default_dir.relative_to(project_path).as_posix()

    if not any(normalized == prefix.rstrip("/") or normalized.startswith(prefix.rstrip("/") + "/") for prefix in _ALLOWED_PREFIXES):
        raise ValueError("output_prefix 不在允許前綴內（docs/、audits/）")
    return normalized
