"""Tool management utilities for Amon."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Event
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .fs.safety import canonicalize_path, make_change_plan, require_confirm


@dataclass
class ToolSpec:
    name: str
    version: str
    inputs_schema: dict[str, Any]
    outputs_schema: dict[str, Any]
    risk_level: str
    allowed_paths: list[str]


class ToolingError(RuntimeError):
    """Tooling error."""


TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")


def load_tool_spec(tool_dir: Path) -> ToolSpec:
    tool_yaml = tool_dir / "tool.yaml"
    if not tool_yaml.exists():
        raise ToolingError(f"找不到 tool.yaml：{tool_yaml}")
    try:
        data = yaml.safe_load(tool_yaml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ToolingError(f"讀取 tool.yaml 失敗：{tool_yaml}") from exc
    missing = [
        key
        for key in ["name", "version", "inputs_schema", "outputs_schema", "risk_level", "allowed_paths"]
        if key not in data
    ]
    if missing:
        raise ToolingError(f"tool.yaml 缺少欄位：{', '.join(missing)}")
    allowed_paths = data.get("allowed_paths")
    if not isinstance(allowed_paths, list) or any(not isinstance(path, str) for path in allowed_paths):
        raise ToolingError("tool.yaml allowed_paths 必須為字串陣列")
    return ToolSpec(
        name=str(data["name"]),
        version=str(data["version"]),
        inputs_schema=data["inputs_schema"] or {},
        outputs_schema=data["outputs_schema"] or {},
        risk_level=str(data["risk_level"]),
        allowed_paths=list(allowed_paths or []),
    )


def validate_inputs_schema(schema: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    if not isinstance(schema, dict):
        return []
    if not isinstance(payload, dict):
        return ["payload 必須為物件"]
    schema_type = schema.get("type")
    if schema_type and schema_type != "object":
        return [f"inputs_schema type 不支援：{schema_type}"]
    errors: list[str] = []
    required = schema.get("required") or []
    if isinstance(required, list):
        for key in required:
            if key not in payload:
                errors.append(f"缺少必要欄位：{key}")
    properties = schema.get("properties") or {}
    if isinstance(properties, dict):
        for key, definition in properties.items():
            if key not in payload:
                continue
            expected = definition.get("type") if isinstance(definition, dict) else None
            if expected:
                if not _matches_type(payload[key], expected):
                    errors.append(f"欄位型別錯誤：{key} 需為 {expected}")
    return errors


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def ensure_tool_name(name: str) -> None:
    if not TOOL_NAME_RE.match(name):
        raise ToolingError("工具名稱僅允許英數、底線、連字號，且需 2-64 字元")


def write_tool_spec(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    except OSError as exc:
        raise ToolingError(f"寫入 tool.yaml 失敗：{path}") from exc


def run_tool_process(
    tool_path: Path,
    payload: dict[str, Any],
    env: dict[str, str],
    cwd: Path | None,
    timeout_s: int = 60,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    input_payload = json.dumps(payload, ensure_ascii=False)
    try:
        process = subprocess.Popen(
            [sys.executable, str(tool_path)],
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(cwd) if cwd else None,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolingError(f"執行工具失敗：{tool_path}") from exc
    start = time.monotonic()
    stdout = ""
    stderr = ""
    remaining_input: str | None = input_payload
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(process.communicate, remaining_input)
            while True:
                try:
                    stdout, stderr = future.result(timeout=0.1)
                    break
                except FutureTimeoutError:
                    remaining_input = None
                    if cancel_event and cancel_event.is_set():
                        process.kill()
                        stdout, stderr = future.result(timeout=2)
                        raise ToolingError("工具執行已取消")
                    if timeout_s and (time.monotonic() - start) > timeout_s:
                        process.kill()
                        stdout, stderr = future.result(timeout=2)
                        raise ToolingError("工具執行逾時")
                    continue
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolingError(f"執行工具失敗：{tool_path}") from exc
    if process.returncode != 0:
        raise ToolingError(f"工具執行失敗：{stderr.strip()}")
    try:
        return json.loads(stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ToolingError("工具輸出非 JSON") from exc


def build_confirm_plan(tool_name: str, risk_level: str) -> str:
    return make_change_plan(
        [
            {
                "action": "執行工具",
                "target": tool_name,
                "detail": f"risk_level={risk_level}",
            }
        ]
    )


def resolve_allowed_paths(
    raw_paths: list[str],
    project_path: Path | None,
    project_allowed: list[Path],
) -> list[Path]:
    resolved: list[Path] = []
    for entry in raw_paths:
        path = Path(entry)
        if not path.is_absolute():
            if project_path:
                path = project_path / path
            else:
                path = Path(entry).expanduser()
        resolved.append(path)
    canonical: list[Path] = []
    for target in resolved:
        canonical.append(canonicalize_path(target, project_allowed))
    return canonical


def format_registry_entry(
    tool_spec: ToolSpec,
    tool_dir: Path,
    scope: str,
    project_id: str | None,
) -> dict[str, Any]:
    return {
        "name": tool_spec.name,
        "version": tool_spec.version,
        "path": str(tool_dir),
        "scope": scope,
        "project_id": project_id,
        "registered_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def build_tool_env(
    log_dir: Path,
    allowed_paths: list[Path],
    project_path: Path | None,
) -> dict[str, str]:
    env = os.environ.copy()
    env["AMON_TOOL_LOG_DIR"] = str(log_dir)
    env["AMON_ALLOWED_PATHS"] = json.dumps([str(path) for path in allowed_paths], ensure_ascii=False)
    if project_path:
        env["AMON_PROJECT_PATH"] = str(project_path)
    return env
