"""Configuration helpers for Amon."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "amon": {
        "data_dir": "~/.amon",
        "default_mode": "single",
        "provider": "openai",
        "ui": {"theme": "light", "streaming": True},
    },
    "paths": {
        "skills_dir": "~/.amon/skills",
        "python_env": "~/.amon/python_env",
        "node_env": "~/.amon/node_env",
    },
    "providers": {
        "openai": {
            "type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "timeout_s": 60,
        },
        "local": {
            "type": "openai_compatible",
            "base_url": "http://localhost:8000/v1",
            "model": "local-model",
            "api_key_env": "LOCAL_LLM_API_KEY",
            "timeout_s": 60,
        },
    },
    "projects": {"config_name": "amon.project.yaml"},
    "skills": {
        "global_dir": "~/.amon/skills",
        "project_dir_rel": ".claude/skills",
    },
    "mcp": {
        "servers": {},
        "allowed_tools": [],
    },
    "billing": {"enabled": True, "currency": "USD"},
}


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"讀取設定檔失敗：{path}") from exc


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"寫入設定檔失敗：{path}") from exc


def set_config_value(config: dict[str, Any], key_path: str, value: Any) -> dict[str, Any]:
    parts = key_path.split(".")
    cursor = config
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value
    return config


def get_config_value(config: dict[str, Any], key_path: str) -> Any:
    cursor: Any = config
    for part in key_path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise KeyError(f"找不到設定鍵：{key_path}")
        cursor = cursor[part]
    return cursor
