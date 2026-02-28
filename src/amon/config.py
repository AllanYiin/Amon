"""Configuration helpers for Amon."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .fs.atomic import atomic_write_text
from .fs.safety import validate_project_id

DEFAULT_CONFIG: dict[str, Any] = {
    "amon": {
        "data_dir": "~/.amon",
        "default_mode": "single",
        "provider": "openai",
        "planner": {
            "enabled": True,
            "preview_only": False,
        },
        "tools": {
            "unified_dispatch": False,
        },
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
            "model": "gpt-5.2",
            "default_model": "gpt-5.2",
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
        "selected": [],
    },
    "tools": {
        "global_dir": "~/.amon/tools",
        "project_dir_rel": "tools",
        "allowed_paths": ["workspace"],
    },
    "mcp": {
        "servers": {},
        "allowed_tools": [],
        "denied_tools": [],
    },
    "billing": {
        "enabled": True,
        "currency": "USD",
        "daily_budget": None,
        "per_project_budget": None,
    },
    "sandbox": {
        "runner": {
            "base_url": "http://127.0.0.1:8088",
            "timeout_s": 30,
            "api_key_env": None,
            "limits": {
                "max_input_files": 32,
                "max_input_total_kb": 5120,
                "max_output_files": 32,
                "max_output_total_kb": 5120,
            },
            "features": {
                "enabled": True,
                "allow_artifact_write": False,
            },
        }
    },
}


def resolve_system_prompt(config: Mapping[str, Any] | None) -> str:
    """Resolve merged system prompt from canonical and legacy keys.

    Canonical key is ``prompts.system``. Legacy keys ``agent.system_prompt`` and
    ``chat.system_prompt`` are still accepted for backward compatibility.
    """

    if not isinstance(config, Mapping):
        return ""
    prompts = config.get("prompts") if isinstance(config.get("prompts"), Mapping) else {}
    canonical = str((prompts or {}).get("system") or "").strip()
    if canonical:
        return canonical
    agent = config.get("agent") if isinstance(config.get("agent"), Mapping) else {}
    agent_value = str((agent or {}).get("system_prompt") or "").strip()
    if agent_value:
        return agent_value
    chat = config.get("chat") if isinstance(config.get("chat"), Mapping) else {}
    return str((chat or {}).get("system_prompt") or "").strip()


def normalize_system_prompt_aliases(effective: dict[str, Any], sources: dict[str, Any]) -> None:
    """Write merged prompt back to canonical ``prompts.system`` while preserving source."""

    resolved = resolve_system_prompt(effective)
    if not resolved:
        return
    prompts_cfg = effective.setdefault("prompts", {})
    if not isinstance(prompts_cfg, dict):
        prompts_cfg = {}
        effective["prompts"] = prompts_cfg
    prompts_sources = sources.setdefault("prompts", {})
    if not isinstance(prompts_sources, dict):
        prompts_sources = {}
        sources["prompts"] = prompts_sources
    if str(prompts_cfg.get("system") or "").strip():
        return
    prompts_cfg["system"] = resolved
    for section, key in (("agent", "system_prompt"), ("chat", "system_prompt")):
        section_sources = sources.get(section)
        if isinstance(section_sources, Mapping):
            source_value = section_sources.get(key)
            if source_value:
                prompts_sources["system"] = source_value
                return
    prompts_sources["system"] = "default"


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
        atomic_write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
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

        normalize_system_prompt_aliases(effective, sources)

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
        validate_project_id(project_id)
        config_name = DEFAULT_CONFIG["projects"]["config_name"]
        direct_path = self.data_dir / "projects" / project_id / config_name
        if direct_path.exists():
            return direct_path
        projects_dir = self.data_dir / "projects"
        if projects_dir.exists():
            for candidate in projects_dir.iterdir():
                if not candidate.is_dir():
                    continue
                config_path = candidate / config_name
                if not config_path.exists():
                    continue
                config = read_yaml(config_path)
                amon_cfg = config.get("amon", {}) if isinstance(config, dict) else {}
                if str(amon_cfg.get("project_id") or "").strip() == project_id:
                    return config_path
        return direct_path
