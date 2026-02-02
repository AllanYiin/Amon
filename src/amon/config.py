"""Configuration helpers for Amon."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

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
            "default_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "timeout_s": 60,
        },
        "local": {
            "type": "openai_compatible",
            "base_url": "http://localhost:8000/v1",
            "model": "local-model",
            "default_model": "local-model",
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


def _assign_sources(value: Any, source: str) -> Any:
    if isinstance(value, dict):
        return {key: _assign_sources(val, source) for key, val in value.items()}
    return source


def _merge_with_sources(
    base: dict[str, Any],
    sources: dict[str, Any],
    updates: Mapping[str, Any],
    source: str,
) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict) and isinstance(sources.get(key), dict):
            _merge_with_sources(base[key], sources[key], value, source)
        else:
            base[key] = value
            sources[key] = _assign_sources(value, source)


def annotate_config(effective: Any, sources: Any) -> Any:
    if isinstance(effective, dict) and isinstance(sources, dict):
        return {key: annotate_config(effective[key], sources.get(key)) for key in effective}
    return {"value": effective, "source": sources}


@dataclass
class ConfigResolution:
    effective: dict[str, Any]
    sources: dict[str, Any]

    def annotated(self) -> dict[str, Any]:
        return annotate_config(self.effective, self.sources)


class ConfigLoader:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or self._resolve_data_dir()

    def load_global(self) -> dict[str, Any]:
        return read_yaml(self._global_config_path())

    def load_project(self, project_id: str) -> dict[str, Any]:
        return read_yaml(self._project_config_path(project_id))

    def resolve(
        self,
        project_id: str | None = None,
        cli_overrides: Mapping[str, Any] | None = None,
    ) -> ConfigResolution:
        effective = deepcopy(DEFAULT_CONFIG)
        sources = _assign_sources(DEFAULT_CONFIG, "default")

        global_config = self.load_global()
        _merge_with_sources(effective, sources, global_config, "global")

        if project_id:
            project_config = self.load_project(project_id)
            _merge_with_sources(effective, sources, project_config, "project")

        if cli_overrides:
            _merge_with_sources(effective, sources, cli_overrides, "cli")

        return ConfigResolution(effective=effective, sources=sources)

    @staticmethod
    def _resolve_data_dir() -> Path:
        env_path = os.environ.get("AMON_HOME")
        if env_path:
            return Path(env_path).expanduser()
        return Path("~/.amon").expanduser()

    def _global_config_path(self) -> Path:
        return self.data_dir / "config.yaml"

    def _project_config_path(self, project_id: str) -> Path:
        return self.data_dir / "projects" / project_id / DEFAULT_CONFIG["projects"]["config_name"]
