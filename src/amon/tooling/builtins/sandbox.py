"""Sandbox builtin tools."""

from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

from amon.sandbox.service import run_sandbox_step

from ..types import ToolCall, ToolResult, ToolSpec


def spec_sandbox_run() -> ToolSpec:
    return ToolSpec(
        name="sandbox.run",
        description="Run python/bash code in isolated sandbox runner.",
        input_schema={
            "type": "object",
            "properties": {
                "language": {"type": "string", "enum": ["python", "bash"]},
                "code": {"type": "string"},
                "input_paths": {"type": "array", "items": {"type": "string"}},
                "output_prefix": {"type": "string"},
                "timeout_s": {"type": "integer", "minimum": 1, "maximum": 120},
            },
            "required": ["language", "code"],
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def handle_sandbox_run(call: ToolCall, *, project_path: Path, config: dict[str, Any]) -> ToolResult:
    language = str(call.args.get("language", "")).strip().lower()
    code = call.args.get("code")
    if language not in {"python", "bash"}:
        return ToolResult(content=[{"type": "text", "text": "language 只支援 python 或 bash。"}], is_error=True, meta={"status": "invalid_args"})
    if not isinstance(code, str) or not code.strip():
        return ToolResult(content=[{"type": "text", "text": "缺少 code 參數。"}], is_error=True, meta={"status": "invalid_args"})

    input_paths = call.args.get("input_paths")
    if input_paths is not None and not isinstance(input_paths, list):
        return ToolResult(content=[{"type": "text", "text": "input_paths 必須是字串陣列。"}], is_error=True, meta={"status": "invalid_args"})

    run_id = call.run_id or f"tooling_{uuid.uuid4().hex[:8]}"
    step_id = call.node_id or f"sandbox_{uuid.uuid4().hex[:8]}"
    output_prefix = call.args.get("output_prefix")
    if not isinstance(output_prefix, str) or not output_prefix.strip():
        output_prefix = f"audits/artifacts/{run_id}/{step_id}/"

    timeout_s = call.args.get("timeout_s")
    if timeout_s is not None:
        try:
            timeout_s = int(timeout_s)
        except (TypeError, ValueError):
            return ToolResult(content=[{"type": "text", "text": "timeout_s 必須為整數。"}], is_error=True, meta={"status": "invalid_args"})

    try:
        result = run_sandbox_step(
            project_path=project_path,
            config=config,
            run_id=run_id,
            step_id=step_id,
            language=language,
            code=code,
            input_paths=[str(item) for item in (input_paths or [])],
            output_prefix=output_prefix,
            timeout_s=timeout_s,
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(content=[{"type": "text", "text": f"sandbox 執行失敗：{exc}"}], is_error=True, meta={"status": "exec_failed"})

    output_text = "\n".join([str(result.get("stdout", "")), str(result.get("stderr", ""))]).strip()
    return ToolResult(
        content=[{"type": "text", "text": output_text}],
        is_error=int(result.get("exit_code") or 0) != 0,
        meta={
            "exit_code": result.get("exit_code"),
            "timed_out": bool(result.get("timed_out", False)),
            "duration_ms": result.get("duration_ms"),
            "manifest_path": result.get("manifest_path"),
            "written_files": result.get("written_files", []),
            "outputs": result.get("outputs", []),
        },
    )


def register_sandbox_tools(registry: Any, *, project_path: Path, config: dict[str, Any]) -> None:
    registry.register(spec_sandbox_run(), lambda call: handle_sandbox_run(call, project_path=project_path, config=config))
