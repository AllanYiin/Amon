"""Policy guard for router results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from amon.fs.safety import canonicalize_path

from .router_types import RouterResult

RISKY_TOKENS = {"delete", "overwrite", "schedule", "tool_forge", "刪除", "覆寫", "排程", "工具偽造"}


def apply_policy_guard(
    result: RouterResult,
    commands_registry: list[dict[str, Any]],
    allowed_paths: list[str],
    confidence_threshold: float = 0.6,
) -> RouterResult:
    if result.type == "chat_response":
        return result

    if result.confidence < confidence_threshold:
        return _reject(result, "信心不足，請求澄清")

    if result.type == "command_plan" and not result.api:
        return _reject(result, "缺少 API，已拒絕")

    if result.api and not _is_registered_api(result.api, commands_registry):
        return _reject(result, "未註冊 API，已拒絕")

    if result.api and _is_risky(result.api, result.args):
        return _require_confirm(result, "高風險操作，需確認")

    if _has_disallowed_path(result.args, allowed_paths):
        return _reject(result, "路徑不允許操作，已拒絕")

    return result


def _is_registered_api(api_name: str, commands_registry: list[dict[str, Any]]) -> bool:
    return api_name in {command.get("name") for command in commands_registry}


def _is_risky(api_name: str, args: dict[str, Any]) -> bool:
    text = f"{api_name} {args}"
    return any(token in text for token in RISKY_TOKENS)


def _has_disallowed_path(args: dict[str, Any], allowed_paths: list[str]) -> bool:
    path_values = _collect_path_values(args)
    if not path_values:
        return False
    allowed = [Path(path) for path in allowed_paths]
    for value in path_values:
        try:
            canonicalize_path(Path(value), allowed)
        except (PermissionError, ValueError, OSError):
            return True
    return False


def _collect_path_values(data: Any) -> list[str]:
    values: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if _looks_like_path_key(str(key)) and isinstance(value, str):
                values.append(value)
            values.extend(_collect_path_values(value))
    elif isinstance(data, list):
        for item in data:
            values.extend(_collect_path_values(item))
    return values


def _looks_like_path_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in {"path", "file", "dir", "folder"})


def _reject(result: RouterResult, reason: str) -> RouterResult:
    return RouterResult(type="chat_response", confidence=result.confidence, reason=reason)


def _require_confirm(result: RouterResult, reason: str) -> RouterResult:
    return RouterResult(
        type=result.type,
        confidence=result.confidence,
        api=result.api,
        args=result.args,
        requires_confirm=True,
        reason=reason,
    )
