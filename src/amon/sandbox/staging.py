"""Shared staging and policy helpers for sandbox file exchange."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from .client import decode_output_files
from .config_keys import DEFAULT_SANDBOX_CONFIG, LIMITS, RUNNER_SECTION
from .path_rules import validate_relative_path


def pack_input_files(
    project_path: Path,
    rel_paths: list[str],
    limits: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pack project-relative files into runner input_files payload with policy checks."""

    base = project_path.resolve()
    applied_limits = _resolve_limits(limits)

    max_files = int(applied_limits.get("max_input_files", 0) or 0)
    if max_files and len(rel_paths) > max_files:
        raise ValueError("input_files 數量超過限制")

    input_files: list[dict[str, Any]] = []
    files_meta: list[dict[str, Any]] = []
    total_bytes = 0

    for rel in rel_paths:
        runner_path = validate_relative_path(rel)
        source = (base / runner_path).resolve()
        if base not in source.parents and source != base:
            raise ValueError("input path 超出專案目錄")
        if not source.is_file():
            raise FileNotFoundError(f"找不到輸入檔案：{runner_path}")

        content = source.read_bytes()
        total_bytes += len(content)
        input_files.append(
            {
                "path": runner_path,
                "content_b64": _b64(content),
            }
        )
        files_meta.append(
            {
                "path": runner_path,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    max_total_kb = float(applied_limits.get("max_input_total_kb", 0) or 0)
    if max_total_kb and total_bytes > (max_total_kb * 1024):
        raise ValueError("input_files 總大小超過限制")

    return input_files, {"files": files_meta, "total_bytes": total_bytes}


def rewrite_output_paths(output_files: list[dict[str, Any]], output_prefix: str) -> list[dict[str, Any]]:
    """Rewrite runner output paths under a project-relative output prefix."""

    normalized_prefix = _normalize_prefix(output_prefix)
    rewritten: list[dict[str, Any]] = []

    for item in output_files:
        rel = validate_relative_path(str(item.get("path", "")))
        combined = f"{normalized_prefix}/{rel}" if normalized_prefix else rel
        safe_path = validate_relative_path(combined)
        rewritten.append({**item, "path": safe_path})

    return rewritten


def unpack_output_files(
    project_path: Path,
    output_files: list[dict[str, Any]],
    allowed_prefixes: list[str],
) -> list[Path]:
    """Validate output prefixes then safely unpack files into project path."""

    normalized_prefixes = _normalize_allowed_prefixes(allowed_prefixes)

    for item in output_files:
        rel = validate_relative_path(str(item.get("path", "")))
        if not _matches_allowed_prefix(rel, normalized_prefixes):
            raise ValueError(f"output path 不在允許前綴內：{rel}")

    return decode_output_files(output_files, project_path.resolve())


def _resolve_limits(limits: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if limits is None:
        defaults = DEFAULT_SANDBOX_CONFIG.get(RUNNER_SECTION, {}).get(LIMITS, {})
        if isinstance(defaults, Mapping):
            return defaults
        return {}
    return limits


def _normalize_prefix(prefix: str) -> str:
    raw = (prefix or "").strip().replace("\\", "/")
    if not raw:
        return ""
    return validate_relative_path(raw.rstrip("/"))


def _normalize_allowed_prefixes(prefixes: list[str]) -> list[str]:
    normalized: list[str] = []
    for prefix in prefixes:
        normalized.append(_normalize_prefix(prefix))
    return normalized


def _matches_allowed_prefix(path: str, prefixes: list[str]) -> bool:
    for prefix in prefixes:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _b64(content: bytes) -> str:
    import base64

    return base64.b64encode(content).decode("ascii")
