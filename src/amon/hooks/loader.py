"""Hook loader and validator."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .types import Hook, HookAction, HookFilter, HookPolicy


logger = logging.getLogger(__name__)


def _resolve_hooks_dir(data_dir: Path | None = None) -> Path:
    if data_dir:
        return data_dir / "hooks"
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser() / "hooks"
    return Path("~/.amon").expanduser() / "hooks"


def _ensure_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _validate_hook(hook_id: str, payload: dict[str, Any]) -> Hook:
    event_types = _ensure_list(payload.get("event_types"))
    if not event_types:
        raise ValueError("event_types 不可為空")

    filters_payload = payload.get("filter") or {}
    if not isinstance(filters_payload, dict):
        raise ValueError("filter 必須為物件")

    min_size = filters_payload.get("min_size")
    if min_size is not None:
        try:
            min_size = int(min_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("min_size 必須為整數") from exc

    ignore_actors = _ensure_list(filters_payload.get("ignore_actors"))
    filters = HookFilter(
        path_glob=filters_payload.get("path_glob"),
        min_size=min_size,
        mime=filters_payload.get("mime"),
        ignore_actors=ignore_actors,
    )

    action_payload = payload.get("action") or {}
    if not isinstance(action_payload, dict):
        raise ValueError("action 必須為物件")
    action_type = action_payload.get("type")
    if not action_type:
        raise ValueError("action.type 不可為空")
    tool_name = action_payload.get("tool") or action_payload.get("tool_name")
    if action_type == "tool.call" and not tool_name:
        raise ValueError("tool.call 必須提供 tool 或 tool_name")
    action_args = action_payload.get("args") or {}
    if not isinstance(action_args, dict):
        raise ValueError("action.args 必須為物件")

    policy_payload = payload.get("policy") or {}
    if policy_payload and not isinstance(policy_payload, dict):
        raise ValueError("policy 必須為物件")
    policy = HookPolicy(require_confirm=bool(policy_payload.get("require_confirm", False)))

    dedupe_key = payload.get("dedupe_key")
    if dedupe_key is not None and not isinstance(dedupe_key, str):
        raise ValueError("dedupe_key 必須為字串")

    cooldown_seconds = payload.get("cooldown_seconds")
    if cooldown_seconds is not None:
        try:
            cooldown_seconds = int(cooldown_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("cooldown_seconds 必須為整數") from exc

    max_concurrency = payload.get("max_concurrency")
    if max_concurrency is not None:
        try:
            max_concurrency = int(max_concurrency)
        except (TypeError, ValueError) as exc:
            raise ValueError("max_concurrency 必須為整數") from exc
        if max_concurrency < 1:
            raise ValueError("max_concurrency 必須大於 0")

    return Hook(
        hook_id=hook_id,
        event_types=event_types,
        filters=filters,
        action=HookAction(type=str(action_type), tool=str(tool_name) if tool_name else None, args=action_args),
        policy=policy,
        dedupe_key=str(dedupe_key) if dedupe_key is not None else None,
        cooldown_seconds=cooldown_seconds,
        max_concurrency=max_concurrency,
        raw=payload,
    )


def load_hook(path: Path) -> Hook:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"讀取 hook 失敗：{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("hook YAML 必須為物件")
    return _validate_hook(path.stem, payload)


def load_hooks(data_dir: Path | None = None) -> list[Hook]:
    hooks_dir = _resolve_hooks_dir(data_dir)
    if not hooks_dir.exists():
        return []
    hooks: list[Hook] = []
    for path in sorted(hooks_dir.glob("*.yaml")):
        try:
            hooks.append(load_hook(path))
        except ValueError as exc:
            logger.error("Hook %s 讀取失敗：%s", path, exc, exc_info=True)
    return hooks
