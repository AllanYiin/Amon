"""Core filesystem operations for Amon."""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from collections import Counter
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import importlib.resources as importlib_resources
from pathlib import Path
from typing import Any
import unicodedata
from zoneinfo import ZoneInfo
import urllib.error
import urllib.request

import yaml

from .config import DEFAULT_CONFIG, deep_merge, default_system_prompt, get_config_value, read_yaml, set_config_value, write_yaml
from .fs.atomic import atomic_write_text, file_lock
from .fs.safety import canonicalize_path, make_change_plan, require_confirm
from .fs.trash import trash_move, trash_restore
from .events import emit_event
from .graph_presets import (
    build_self_critique_graph_payload,
    build_single_graph_payload,
    build_team_graph_payload,
    team_role_prototypes_json,
)
from .logging import log_billing, log_event
from .logging_utils import setup_logger
from .llm_request_log import append_llm_request, build_llm_request_payload
from .mcp_client import MCPClientError, MCPServerConfig, MCPStdioClient
from .planning import generate_plan_with_llm
from .models import (
    ProviderError,
    build_provider,
    decode_reasoning_chunk,
    encode_reasoning_chunk,
    encode_stream_event,
)
from .project_registry import ProjectRegistry, load_project_config
from .taskgraph3.amon_node_runner import AmonNodeRunner
from .taskgraph3.payloads import (
    AgentTaskConfig,
    InputBinding,
    SandboxRunConfig,
    TaskDisplayMetadata,
    TaskSpec,
    ToolCallSpec,
    ToolTaskConfig,
    task_spec_from_payload,
)
from .taskgraph3.runtime import TaskGraph3RunResult, TaskGraph3Runtime
from .taskgraph3.schema import ArtifactNode, GateNode, GateRoute, GraphDefinition, GraphEdge, GroupNode, TaskNode
from .taskgraph3.serialize import dumps_graph_definition
from .taskgraph3.validate import graph_definition_from_payload
from .sandbox.service import run_sandbox_step
from .tooling import (
    ToolingError,
    build_confirm_plan,
    build_tool_env,
    ensure_tool_name,
    format_registry_entry,
    load_tool_spec,
    resolve_allowed_paths,
    run_tool_process,
    write_tool_spec,
)
from .tooling.native import compute_tool_sha256, parse_native_manifest, scan_native_tools
from .tooling.builtin import build_registry
from .tooling.types import ToolCall
from .skills import build_skill_archive, build_system_prefix_injection
from .token_counter import count_non_dialogue_tokens
from .core_tool_templates import (
    render_native_tool_readme,
    render_native_tool_template,
    render_native_tool_test,
    render_tool_readme,
    render_tool_template,
    render_tool_test,
)


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    path: str
    created_at: str
    updated_at: str
    status: str
    trash_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "path": self.path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "trash_path": self.trash_path,
        }


class AmonCore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or self._resolve_data_dir()
        self.logs_dir = self.data_dir / "logs"
        self.cache_dir = self.data_dir / "cache"
        self.projects_dir = self.data_dir / "projects"
        self.trash_dir = self.data_dir / "trash"
        self.skills_dir = self.data_dir / "skills"
        self.tools_dir = self.data_dir / "tools"
        self.templates_dir = self.data_dir / "templates"
        self.schedules_dir = self.data_dir / "schedules"
        self.python_env_dir = self.data_dir / "python_env"
        self.node_env_dir = self.data_dir / "node_env"
        self.billing_log = self.logs_dir / "billing.log"
        self.logger = setup_logger("amon", self.logs_dir)
        # Backward-compatible registry handle for UI/legacy callers.
        self.tool_registry = build_registry(Path.cwd())
        self.project_registry = ProjectRegistry(
            self.projects_dir,
            slug_builder=self._generate_project_slug,
            logger=self.logger,
        )

    def ensure_base_structure(self) -> None:
        for path in [
            self.data_dir,
            self.logs_dir,
            self.cache_dir,
            self.projects_dir,
            self.trash_dir,
            self.skills_dir,
            self.tools_dir,
            self.templates_dir,
            self.schedules_dir,
            self.python_env_dir,
            self.node_env_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "mcp").mkdir(parents=True, exist_ok=True)
        self._touch_log(self.logs_dir / "amon.log")
        if not self.billing_log.exists():
            try:
                self._atomic_write_text(self.billing_log, "")
            except OSError as exc:
                self.logger.error("建立 billing.log 失敗：%s", exc, exc_info=True)
                raise
        config_path = self._global_config_path()
        if not config_path.exists():
            write_yaml(config_path, self._initial_config())
        trash_manifest = self.trash_dir / "manifest.json"
        if not trash_manifest.exists():
            try:
                self._atomic_write_text(
                    trash_manifest,
                    json.dumps({"entries": []}, ensure_ascii=False, indent=2),
                )
            except OSError as exc:
                self.logger.error("建立回收桶清單失敗：%s", exc, exc_info=True)
                raise
        registry_path = self.cache_dir / "tool_registry.json"
        if not registry_path.exists():
            try:
                self._atomic_write_text(registry_path, json.dumps({"tools": []}, ensure_ascii=False, indent=2))
            except OSError as exc:
                self.logger.error("建立工具 registry 失敗：%s", exc, exc_info=True)
                raise
        self._sync_tool_registry(registry_path)
        toolforge_index = self._toolforge_index_path()
        if not toolforge_index.exists():
            try:
                self._atomic_write_text(toolforge_index, json.dumps({"tools": []}, ensure_ascii=False, indent=2))
            except OSError as exc:
                self.logger.error("建立 toolforge index 失敗：%s", exc, exc_info=True)
                raise
        schedules_path = self.schedules_dir / "schedules.json"
        if not schedules_path.exists():
            try:
                self._atomic_write_text(schedules_path, json.dumps({"schedules": []}, ensure_ascii=False, indent=2))
            except OSError as exc:
                self.logger.error("建立排程資料失敗：%s", exc, exc_info=True)
                raise
        self._ensure_global_skills_installed()

    def _sync_tool_registry(self, registry_path: Path) -> None:
        from .tooling.builtin import build_registry

        try:
            data = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"tools": []}
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取工具 registry 失敗：%s", exc, exc_info=True)
            raise

        existing_tools = [item for item in data.get("tools", []) if isinstance(item, dict)]
        preserved_tools = [
            item
            for item in existing_tools
            if item.get("scope") not in {"builtin", "global", "project"} or item.get("kind") not in {"builtin", "native"}
        ]
        registered_at_map = {
            (str(item.get("name")), str(item.get("scope")), item.get("project_id")): str(item.get("registered_at"))
            for item in existing_tools
            if item.get("registered_at")
        }

        builtin_registry = build_registry(Path.cwd())
        builtin_entries: list[dict[str, Any]] = []
        for spec in sorted(builtin_registry.list_specs(), key=lambda item: item.name):
            tool_name = f"builtin:{spec.name}"
            builtin_entries.append(
                {
                    "name": tool_name,
                    "version": str((spec.annotations or {}).get("version") or "builtin"),
                    "path": f"builtin://{spec.name}",
                    "scope": "builtin",
                    "kind": "builtin",
                    "project_id": None,
                    "status": "active",
                    "registered_at": registered_at_map.get((tool_name, "builtin", None)) or self._now(),
                }
            )

        native_status_lookup = self._toolforge_status_lookup()
        native_entries = []
        for entry in scan_native_tools(self._native_tool_base_dirs(None), status_lookup=native_status_lookup):
            native_entries.append(
                {
                    "name": f"native:{entry.name}",
                    "version": entry.version,
                    "path": str(entry.path),
                    "scope": entry.scope,
                    "kind": "native",
                    "project_id": entry.project_id,
                    "status": entry.status,
                    "sha256": entry.sha256,
                    "risk": entry.risk,
                    "default_permission": entry.default_permission,
                    "registered_at": registered_at_map.get((f"native:{entry.name}", entry.scope, entry.project_id)) or self._now(),
                }
            )

        data["tools"] = preserved_tools + builtin_entries + native_entries
        try:
            self._atomic_write_text(registry_path, json.dumps(data, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入工具 registry 失敗：%s", exc, exc_info=True)
            raise

    def initialize(self) -> None:
        try:
            self.ensure_base_structure()
            self.scan_skills()
        except OSError as exc:
            self.logger.error("初始化 Amon 失敗：%s", exc, exc_info=True)
            raise

    def _ensure_global_skills_installed(self) -> None:
        try:
            skills_package = importlib_resources.files("amon").joinpath("resources", "skills")
        except (ModuleNotFoundError, FileNotFoundError, OSError) as exc:
            self.logger.warning("找不到內建 skills 來源資料夾：%s", exc, exc_info=True)
            return

        try:
            bundled_entries = sorted(skills_package.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            self.logger.warning("列出內建 skills 來源失敗：%s", exc, exc_info=True)
            return

        if not bundled_entries:
            self.logger.warning("找不到內建 skills 來源資料夾：%s", skills_package)
            return

        for entry in bundled_entries:
            try:
                if entry.is_dir():
                    target_file = self.skills_dir / f"{entry.name}.skill"
                    if target_file.exists():
                        continue
                    with importlib_resources.as_file(entry) as source_dir:
                        build_skill_archive(source_dir, target_file)
                elif entry.is_file() and entry.name.endswith(".skill"):
                    target_file = self.skills_dir / entry.name
                    if target_file.exists():
                        continue
                    with importlib_resources.as_file(entry) as source_file:
                        shutil.copy2(source_file, target_file)
                else:
                    continue
            except OSError as exc:
                self.logger.error("安裝內建 skill 失敗：%s -> %s (%s)", entry, target_file, exc, exc_info=True)
                raise

        self._deduplicate_global_skill_folders()

    def _deduplicate_global_skill_folders(self) -> None:
        """保留 .skill 封包，移除同名且重覆的解包資料夾。"""
        archive_names = {path.stem for path in self.skills_dir.glob("*.skill") if path.is_file()}
        for name in archive_names:
            folder_path = self.skills_dir / name
            skill_file = folder_path / "SKILL.md"
            if not (folder_path.is_dir() and skill_file.exists()):
                continue
            try:
                shutil.rmtree(folder_path)
                self.logger.info("已移除重覆的 skills 解包資料夾：%s", folder_path)
            except OSError as exc:
                self.logger.error("移除重覆 skills 資料夾失敗：%s (%s)", folder_path, exc, exc_info=True)
                raise

    def create_project(self, name: str) -> ProjectRecord:
        self.ensure_base_structure()
        project_id = self._generate_project_id(name)
        existing_dir_names = {path.name for path in self.projects_dir.iterdir() if path.is_dir()}
        project_slug = self._generate_project_slug(name, existing_dir_names)
        project_path = self.projects_dir / project_slug

        if project_path.exists():
            raise FileExistsError(f"專案已存在：{project_slug}")

        try:
            self._create_project_structure(project_path)
            self._write_project_config(project_path, name, project_id, project_slug)
            self._ensure_project_id_alias(project_path, project_id)
        except OSError as exc:
            self.logger.error("建立專案資料夾失敗：%s", exc, exc_info=True)
            raise

        timestamp = self._now()
        record = ProjectRecord(
            project_id=project_id,
            name=name,
            path=str(project_path),
            created_at=timestamp,
            updated_at=timestamp,
            status="active",
        )
        self._save_record(record)
        log_event(
            {
                "level": "INFO",
                "event": "project_create",
                "project_id": project_id,
                "project_name": name,
            }
        )
        emit_event(
            {
                "type": "project.create",
                "scope": "project",
                "project_id": project_id,
                "actor": "system",
                "payload": {"project_name": name},
                "risk": "low",
            }
        )
        self.logger.info("已建立專案 %s (%s)", name, project_id)
        return record

    def list_projects(self, include_deleted: bool = False) -> list[ProjectRecord]:
        self.project_registry.scan()
        records = self._load_records()
        records_by_id = {record.project_id: record for record in records}

        merged: list[ProjectRecord] = []
        for meta in self.project_registry.list_projects():
            project_id = str(meta.get("project_id") or "")
            if not project_id:
                continue
            existing = records_by_id.get(project_id)
            if existing is not None:
                existing.path = str(meta.get("project_path") or existing.path)
                if not existing.name:
                    existing.name = str(meta.get("project_name") or project_id)
                merged.append(existing)
                continue
            timestamp = self._now()
            merged.append(
                ProjectRecord(
                    project_id=project_id,
                    name=str(meta.get("project_name") or project_id),
                    path=str(meta.get("project_path") or ""),
                    created_at=timestamp,
                    updated_at=timestamp,
                    status="active",
                )
            )

        if include_deleted:
            for record in records:
                if record.status == "deleted" and record.project_id not in {item.project_id for item in merged}:
                    merged.append(record)

        if merged:
            merged = sorted(merged, key=lambda item: item.project_id)
            self._write_records(merged)

        log_event(
            {
                "level": "INFO",
                "event": "project_list",
                "include_deleted": include_deleted,
                "count": len(merged),
            }
        )
        if include_deleted:
            return merged
        return [record for record in merged if record.status == "active"]

    def get_project(self, project_id: str) -> ProjectRecord:
        for record in self.list_projects(include_deleted=True):
            if record.project_id == project_id:
                return record
        raise KeyError(f"找不到專案：{project_id}")

    def update_project_name(self, project_id: str, new_name: str) -> ProjectRecord:
        records = self._load_records()
        for record in records:
            if record.project_id == project_id:
                record.name = new_name
                record.updated_at = self._now()
                self._update_project_config(Path(record.path), new_name)
                self._write_records(records)
                log_event(
                    {
                        "level": "INFO",
                        "event": "project_update",
                        "project_id": project_id,
                        "project_name": new_name,
                    }
                )
                emit_event(
                    {
                        "type": "project.update",
                        "scope": "project",
                        "project_id": project_id,
                        "actor": "system",
                        "payload": {"project_name": new_name},
                        "risk": "low",
                    }
                )
                self.logger.info("已更新專案名稱 %s (%s)", new_name, project_id)
                return record
        raise KeyError(f"找不到專案：{project_id}")

    def delete_project(self, project_id: str) -> ProjectRecord:
        records = self._load_records()
        for record in records:
            if record.project_id == project_id:
                if record.status == "deleted":
                    raise ValueError("專案已在回收桶")
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                trash_path = self.trash_dir / f"{project_id}_{timestamp}"
                self._safe_move(Path(record.path), trash_path, "刪除專案")
                record.status = "deleted"
                record.trash_path = str(trash_path)
                record.updated_at = self._now()
                self._write_records(records)
                self._append_trash_entry(record, trash_path)
                log_event(
                    {
                        "level": "INFO",
                        "event": "project_delete",
                        "project_id": project_id,
                        "project_name": record.name,
                        "trash_path": str(trash_path),
                    }
                )
                emit_event(
                    {
                        "type": "project.delete",
                        "scope": "project",
                        "project_id": project_id,
                        "actor": "system",
                        "payload": {"project_name": record.name, "trash_path": str(trash_path)},
                        "risk": "medium",
                    }
                )
                self.logger.info("已刪除專案 %s (%s)", record.name, project_id)
                return record
        raise KeyError(f"找不到專案：{project_id}")

    def restore_project(self, project_id: str) -> ProjectRecord:
        records = self._load_records()
        for record in records:
            if record.project_id == project_id:
                if record.status != "deleted" or not record.trash_path:
                    raise ValueError("專案不在回收桶")
                original_path = Path(record.path)
                alias_path = self.projects_dir / project_id
                if alias_path.is_symlink():
                    alias_path.unlink()
                if original_path.exists():
                    raise FileExistsError("專案路徑已存在，無法還原")
                self._safe_move(Path(record.trash_path), original_path, "還原專案")
                self._ensure_project_id_alias(original_path, project_id)
                record.status = "active"
                record.trash_path = None
                record.path = str(original_path)
                record.updated_at = self._now()
                self._write_records(records)
                self._mark_trash_restored(project_id)
                log_event(
                    {
                        "level": "INFO",
                        "event": "project_restore",
                        "project_id": project_id,
                        "project_name": record.name,
                    }
                )
                emit_event(
                    {
                        "type": "project.restore",
                        "scope": "project",
                        "project_id": project_id,
                        "actor": "system",
                        "payload": {"project_name": record.name},
                        "risk": "low",
                    }
                )
                self.logger.info("已還原專案 %s (%s)", record.name, project_id)
                return record
        raise KeyError(f"找不到專案：{project_id}")

    def load_config(self, project_path: Path | None = None) -> dict[str, Any]:
        self.ensure_base_structure()
        global_config = deep_merge(DEFAULT_CONFIG, read_yaml(self._global_config_path()))
        if not project_path:
            return global_config
        project_config = read_yaml(project_path / self._project_config_name())
        return deep_merge(global_config, project_config)

    def get_config_value(self, key_path: str, project_path: Path | None = None) -> Any:
        config = self.load_config(project_path)
        return get_config_value(config, key_path)

    def set_config_value(self, key_path: str, value: Any, project_path: Path | None = None) -> None:
        self.ensure_base_structure()
        config_path = self._global_config_path() if project_path is None else project_path / self._project_config_name()
        lock_path = config_path.with_suffix(f"{config_path.suffix}.lock")
        with file_lock(lock_path):
            current = read_yaml(config_path)
            updated = set_config_value(current, key_path, value)
            write_yaml(config_path, updated)

    @staticmethod
    def _emit_stream_event(stream_handler, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if not callable(stream_handler):
            return
        try:
            stream_handler(encode_stream_event(event_type, payload))
        except Exception:
            logging.getLogger(__name__).debug("stream event dropped: %s", event_type, exc_info=True)

    def run_agent_task(
        self,
        prompt: str,
        project_path: Path | None,
        model: str | None = None,
        system_prompt: str | None = None,
        mode: str = "single",
        stream_handler=None,
        skill_names: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        config = self.load_config(project_path)
        project_id, _ = self.resolve_project_identity(project_path)
        budget_status = self._evaluate_budget(config, project_id=project_id)
        if budget_status["exceeded"]:
            if mode == "single":
                message = "提醒：已超過用量上限，single 仍可執行，但 self_critique/team 會被拒絕。"
                print(message)
                self._log_budget_event(budget_status, mode="single", project_id=project_id, action="allow")
            else:
                self._log_budget_event(budget_status, mode=mode, project_id=project_id, action="reject")
                raise RuntimeError(f"已超過用量上限，拒絕執行 {mode}")
        provider_name = config.get("amon", {}).get("provider", "openai")
        provider_cfg = config.get("providers", {}).get(provider_name, {})
        provider_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
        provider = build_provider(provider_cfg, model=provider_model)
        base_system_message = self._build_system_message(
            prompt,
            project_path,
            config=config,
            skill_names=skill_names,
            allowed_tools=allowed_tools,
            stream_handler=stream_handler,
            run_id=run_id,
            node_id=node_id,
            thread_id=thread_id,
            request_id=request_id,
        )
        system_message = f"{base_system_message}\n\n{system_prompt}" if system_prompt else base_system_message
        user_prompt = prompt
        if prompt.startswith("/"):
            user_prompt = " ".join(prompt.split()[1:]).strip()
        messages = [{"role": "system", "content": system_message}]
        messages.extend(self._normalize_chat_history(conversation_history))
        messages.append({"role": "user", "content": user_prompt or prompt})
        web_context = self._auto_web_search_context(
            user_prompt or prompt,
            project_path=project_path,
            config=config,
            allowed_tools=allowed_tools,
            stream_handler=stream_handler,
            run_id=run_id,
            node_id=node_id,
            thread_id=thread_id,
            request_id=request_id,
        )
        if web_context:
            messages.insert(1, {"role": "system", "content": web_context})
        response_text = ""
        session_id = uuid.uuid4().hex
        session_path = self._prepare_session_path(project_path, session_id)
        self._record_llm_request(
            project_path=project_path,
            provider_name=provider_name,
            provider_model=provider_model,
            project_id=project_id,
            run_id=run_id,
            thread_id=thread_id,
            node_id=node_id,
            request_id=request_id,
            source="run_agent_task",
            stage="node_agent" if node_id else mode,
            messages=messages,
            prompt_text=user_prompt or prompt,
            metadata={
                "mode": mode,
                "session_id": session_id,
                "history_count": len(self._normalize_chat_history(conversation_history)),
                "has_web_context": bool(web_context),
                "has_custom_system_prompt": bool(system_prompt),
            },
        )
        log_event(
            {
                "level": "INFO",
                "event": "run_single_start",
                "provider": provider_name,
                "model": provider_model,
                "session_id": session_id,
                "project_id": project_id,
            }
        )
        self._append_session_event(
            session_path,
            {
                "event": "prompt",
                "role": "user",
                "content": user_prompt or prompt,
                "provider": provider_name,
                "model": provider_model,
            },
            session_id=session_id,
        )
        try:
            for index, token in enumerate(provider.generate_stream(messages, model=provider_model)):
                is_reasoning, reasoning_text = decode_reasoning_chunk(token)
                if is_reasoning:
                    if stream_handler:
                        stream_handler(token)
                    self._append_session_event(
                        session_path,
                        {
                            "event": "reasoning_chunk",
                            "index": index,
                            "content": reasoning_text,
                            "provider": provider_name,
                            "model": provider_model,
                        },
                        session_id=session_id,
                    )
                    continue
                print(token, end="", flush=True)
                response_text += token
                if stream_handler:
                    stream_handler(token)
                self._append_session_event(
                    session_path,
                    {
                        "event": "chunk",
                        "index": index,
                        "content": token,
                        "provider": provider_name,
                        "model": provider_model,
                    },
                    session_id=session_id,
                )
            print("")
        except ProviderError as exc:
            self.logger.error("模型執行失敗：%s", exc, exc_info=True)
            raise
        self._append_session_event(
            session_path,
            {
                "event": "final",
                "content": response_text,
                "provider": provider_name,
                "model": provider_model,
            },
            session_id=session_id,
        )
        log_event(
            {
                "level": "INFO",
                "event": "run_single_complete",
                "provider": provider_name,
                "model": provider_model,
                "session_id": session_id,
                "project_id": project_id,
            }
        )
        self._log_billing(
            config,
            provider_name,
            provider_model,
            prompt,
            response_text,
            session_id=session_id,
            project_id=project_id,
            project_path=project_path,
            run_id=run_id,
            node_id=node_id,
            thread_id=thread_id,
            mode=mode,
        )
        return response_text

    def _record_llm_request(
        self,
        *,
        project_path: Path | None,
        provider_name: str,
        provider_model: str | None,
        project_id: str | None,
        run_id: str | None,
        thread_id: str | None,
        node_id: str | None,
        request_id: str | None,
        source: str,
        stage: str | None,
        messages: list[dict[str, Any]] | None,
        prompt_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if project_path is None:
            return
        payload = build_llm_request_payload(
            source=source,
            provider=provider_name,
            model=provider_model,
            project_id=project_id,
            run_id=run_id,
            thread_id=thread_id,
            node_id=node_id,
            request_id=request_id,
            stage=stage,
            messages=messages,
            prompt_text=prompt_text,
            metadata=metadata,
        )
        try:
            append_llm_request(project_path, payload)
        except OSError as exc:
            self.logger.warning("寫入 llm request trace 失敗：%s", exc)


    def _normalize_chat_history(self, history: list[dict[str, str]] | None) -> list[dict[str, str]]:
        if not history:
            return []
        normalized: list[dict[str, str]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role not in {"user", "assistant"}:
                continue
            if not isinstance(content, str):
                continue
            cleaned = content.strip()
            if not cleaned:
                continue
            normalized.append({"role": role, "content": cleaned})
        return normalized

    def _auto_web_search_context(
        self,
        prompt: str,
        *,
        project_path: Path | None,
        config: dict[str, Any],
        allowed_tools: list[str] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        enabled = bool(config.get("amon", {}).get("auto_web_search", True))
        if not enabled:
            return ""
        if allowed_tools is not None:
            allowed = {str(item).strip() for item in allowed_tools if str(item).strip()}
            if not allowed.intersection({"web.search", "web.fetch", "web.better_search"}):
                return ""
        if not self._prompt_requires_web_search(prompt):
            return ""
        try:
            from .tooling.builtin import build_registry
            from .tooling.policy import ToolPolicy
            from .tooling.types import ToolCall

            workspace_root = project_path or Path.cwd()
            project_id, _ = self.resolve_project_identity(project_path)
            registry = build_registry(workspace_root)
            policy = registry.policy
            allow = tuple(dict.fromkeys((*policy.allow, "web.search", "web.fetch")))
            ask = tuple(rule for rule in policy.ask if rule not in {"web.search", "web.fetch"})
            registry.policy = ToolPolicy(allow=allow, ask=ask, deny=policy.deny)
            tool_event_base = {
                "name": "web.search",
                "route": "builtin",
                "source": "auto_web_search",
                "run_id": run_id,
                "node_id": node_id,
                "thread_id": thread_id,
                "request_id": request_id,
            }
            log_event(
                {
                    "level": "INFO",
                    "event": "tool_call",
                    "project_id": project_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "node_id": node_id,
                    "request_id": request_id,
                    "tool_name": "web.search",
                    "route": "builtin",
                    "stage": "start",
                    "source": "auto_web_search",
                }
            )
            self._emit_stream_event(stream_handler, "tool_call", {**tool_event_base, "stage": "start", "status": "running"})
            result = registry.call(
                ToolCall(
                    tool="web.search",
                    args={"query": prompt, "max_results": 5},
                    caller="agent",
                    project_id=project_id,
                )
            )
            status = str((result.meta or {}).get("status") or ("error" if result.is_error else "ok"))
            log_event(
                {
                    "level": "INFO",
                    "event": "tool_call",
                    "project_id": project_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "node_id": node_id,
                    "request_id": request_id,
                    "tool_name": "web.search",
                    "route": "builtin",
                    "stage": "complete",
                    "status": status,
                    "source": "auto_web_search",
                    "is_error": bool(result.is_error),
                }
            )
            self._emit_stream_event(
                stream_handler,
                "tool_call",
                {
                    **tool_event_base,
                    "stage": "complete",
                    "status": status,
                    "is_error": bool(result.is_error),
                },
            )
            if result.is_error:
                self.logger.info("自動 web.search 未提供結果：%s", result.meta.get("status"))
                return ""
            payload = result.as_text().strip()
            if not payload:
                return ""
            return (
                "以下是剛剛使用 web.search 取得的參考資料，請先引用這些結果再回答，"
                "若內容不足再明確說明限制。\n"
                f"```json\n{payload}\n```"
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("自動 web.search 失敗：%s", exc, exc_info=True)
            return ""

    def _prompt_requires_web_search(self, prompt: str) -> bool:
        normalized = unicodedata.normalize("NFKC", prompt).strip().lower()
        if not normalized:
            return False
        keywords = (
            "搜尋",
            "查詢",
            "最新",
            "新聞",
            "資料來源",
            "網路",
            "上網",
            "search",
            "google",
            "wikipedia",
            "duckduckgo",
            "cite",
        )
        return any(keyword in normalized for keyword in keywords)

    def run_single(
        self,
        prompt: str,
        project_path: Path | None = None,
        model: str | None = None,
        skill_names: list[str] | None = None,
    ) -> str:
        if not project_path:
            self.ensure_base_structure()
            temp_root = self.data_dir / "temp_runs"
            temp_root.mkdir(parents=True, exist_ok=True)
            project_path = Path(tempfile.mkdtemp(prefix="single-", dir=str(temp_root)))
        lock_context = self._project_lock(project_path, "single") if project_path else nullcontext()
        with lock_context:
            graph = self._build_single_graph()
            graph_path = self._write_graph_resolved(
                project_path,
                graph,
                {"prompt": prompt, "mode": "single", "model": model or "", "skill_names": skill_names or []},
                mode="single",
            )
            result = self.run_graph(project_path=project_path, graph_path=graph_path)
            return self._load_graph_primary_output(result.run_dir)

    def run_single_stream(
        self,
        prompt: str,
        project_path: Path,
        model: str | None = None,
        stream_handler=None,
        skill_names: list[str] | None = None,
        run_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> tuple[TaskGraph3RunResult, str]:
        if not project_path:
            raise ValueError("執行 stream 需要指定專案")
        lock_context = self._project_lock(project_path, "single") if project_path else nullcontext()
        with lock_context:
            graph = self._build_single_graph()
            graph_path = self._write_graph_resolved(
                project_path,
                graph,
                {"prompt": prompt, "mode": "single", "model": model or "", "skill_names": skill_names or []},
                mode="single",
            )
            variables: dict[str, Any] = {"conversation_history": conversation_history or []}
            if thread_id:
                variables["thread_id"] = thread_id
            result = self.run_graph(
                project_path=project_path,
                graph_path=graph_path,
                variables=variables,
                stream_handler=stream_handler,
                run_id=run_id,
                thread_id=thread_id,
                request_id=request_id,
            )
            response = self._load_graph_primary_output(result.run_dir)
            return result, response

    def run_self_critique(
        self,
        prompt: str,
        project_path: Path | None = None,
        model: str | None = None,
        skill_names: list[str] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        if not project_path:
            raise ValueError("執行 self_critique 需要指定專案")
        with self._project_lock(project_path, "self_critique"):
            config = self.load_config(project_path)
            project_id, _ = self.resolve_project_identity(project_path)
            budget_status = self._evaluate_budget(config, project_id=project_id)
            if budget_status["exceeded"]:
                self._log_budget_event(budget_status, mode="self_critique", project_id=project_id, action="reject")
                raise RuntimeError("已超過用量上限，拒絕執行 self_critique")
            docs_dir = project_path / "docs"
            draft_path, reviews_dir, final_path, version = self._resolve_doc_paths(docs_dir)
            log_event(
                {
                    "level": "INFO",
                    "event": "self_critique_start",
                    "doc_version": version,
                    "project_id": project_id,
                }
            )
            graph = self._build_self_critique_graph()
            graph_path = self._write_graph_resolved(
                project_path,
                graph,
                {
                    "prompt": prompt,
                    "mode": "self_critique",
                    "draft_path": str(draft_path.relative_to(project_path)),
                    "reviews_dir": str(reviews_dir.relative_to(project_path)),
                    "final_path": str(final_path.relative_to(project_path)),
                    "model": model or "",
                    "skill_names": skill_names or [],
                },
                mode="self_critique",
            )
            self.run_graph(project_path=project_path, graph_path=graph_path, stream_handler=stream_handler, run_id=run_id, thread_id=thread_id, request_id=request_id)
            log_event(
                {
                    "level": "INFO",
                    "event": "self_critique_complete",
                    "doc_version": version,
                    "project_id": project_id,
                }
            )
            return final_path.read_text(encoding="utf-8")

    def run_team(
        self,
        prompt: str,
        project_path: Path | None = None,
        model: str | None = None,
        skill_names: list[str] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        if not project_path:
            raise ValueError("執行 team 需要指定專案")
        with self._project_lock(project_path, "team"):
            config = self.load_config(project_path)
            project_id, _ = self.resolve_project_identity(project_path)
            budget_status = self._evaluate_budget(config, project_id=project_id)
            if budget_status["exceeded"]:
                self._log_budget_event(budget_status, mode="team", project_id=project_id, action="reject")
                raise RuntimeError("已超過用量上限，拒絕執行 team")
            docs_dir = project_path / "docs"
            log_event(
                {
                    "level": "INFO",
                    "event": "team_start",
                    "project_id": project_id,
                }
            )
            docs_dir.mkdir(parents=True, exist_ok=True)
            provider_name = config.get("amon", {}).get("provider", "openai")
            provider_cfg = config.get("providers", {}).get(provider_name, {})
            continuation_context = self._collect_mnt_data_handover_context(project_path)
            graph = self._build_team_graph()
            graph_path = self._write_graph_resolved(
                project_path,
                graph,
                {
                    "prompt": prompt,
                    "mode": "team",
                    "model": model or "",
                    "skill_names": skill_names or [],
                    "continuation_context": continuation_context,
                    "team_role_prototypes_json": team_role_prototypes_json(),
                },
                mode="team",
            )
            self.run_graph(project_path=project_path, graph_path=graph_path, stream_handler=stream_handler, run_id=run_id, thread_id=thread_id, request_id=request_id)
            tasks_dir = project_path / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)
            self._sync_team_tasks(project_path, tasks_dir, docs_dir)
            final_text = (docs_dir / "final.md").read_text(encoding="utf-8")
            log_event(
                {
                    "level": "INFO",
                    "event": "team_complete",
                    "project_id": project_id,
                }
            )
            return final_text

    def generate_plan_docs(
        self,
        message: str,
        *,
        project_path: Path,
        project_id: str | None = None,
        llm_client=None,
        model: str | None = None,
        available_tools: list[dict[str, Any]] | None = None,
        available_skills: list[dict[str, Any]] | None = None,
        run_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ):
        """Generate TaskGraph v3 and materialize docs/plan.json + docs/TODO.md."""
        if available_tools is None:
            available_tools = self.describe_available_tools(project_id=project_id)
        available_skills = self._merge_planning_available_skills(available_skills, project_path)
        planning_tools = self._select_planning_tools(message, available_tools)

        plan = generate_plan_with_llm(
            message,
            project_id=project_id,
            llm_client=llm_client,
            model=model,
            available_tools=planning_tools,
            available_skills=available_skills,
            project_path=project_path,
            run_id=run_id,
            thread_id=thread_id,
            request_id=request_id,
        )
        plan = self._postprocess_planner_graph(plan, message=message, available_tools=planning_tools)
        docs_dir = project_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        plan_json = dumps_graph_definition(plan)
        todo_markdown = self._render_todo_markdown_from_v3(plan, objective=message)

        plan_path = docs_dir / "plan.json"
        todo_path = docs_dir / "TODO.md"
        self._atomic_write_text(plan_path, plan_json)
        self._atomic_write_text(todo_path, todo_markdown)

        plan_hash = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()
        payload = {
            "plan_hash": plan_hash,
            "node_count": len(plan.nodes),
            "objective": message,
            "output_paths": ["docs/plan.json", "docs/TODO.md"],
        }
        log_event(
            {
                "level": "INFO",
                "event": "plan_generated",
                "project_id": project_id or self.resolve_project_identity(project_path)[0],
                "payload": payload,
            }
        )
        emit_event(
            {
                "type": "plan_generated",
                "scope": "planning",
                "project_id": project_id or self.resolve_project_identity(project_path)[0],
                "actor": "system",
                "payload": payload,
                "risk": "low",
            }
        )
        return plan

    def _render_todo_markdown_from_v3(self, graph: GraphDefinition, *, objective: str) -> str:
        lines: list[str] = [f"# TODO Plan: {objective}", ""]
        for node in graph.nodes:
            if not isinstance(node, TaskNode):
                continue
            summary = (node.task_spec.display.summary or "").strip() if node.task_spec and node.task_spec.display else ""
            todo_hint = (node.task_spec.display.todo_hint or "").strip() if node.task_spec and node.task_spec.display else ""
            dod_summary = todo_hint or "（未提供 DoD）"
            skill_summary = "、".join(self._task_skill_names(node)) or "（未綁定 skill）"
            lines.append(f"- [ ] {node.id} {node.title or (node.task_spec.display.label if node.task_spec and node.task_spec.display else '')}".rstrip())
            lines.append(f"  - Goal: {summary or '（未提供目標）'}")
            lines.append(f"  - Skill: {skill_summary}")
            lines.append(f"  - DoD: {dod_summary}")
        return "\n".join(lines) + "\n"

    def _build_quick_todo_markdown(self, objective: str, *, available_tools: list[dict[str, Any]] | None = None) -> str:
        key_concepts = self._extract_planning_keywords(objective, limit=4)
        planning_tools = self._select_planning_tools(objective, available_tools or self.describe_available_tools())
        tool_names = [str(item.get("name") or "") for item in planning_tools[:6] if str(item.get("name") or "").strip()]
        concept_text = "、".join(key_concepts) if key_concepts else "任務目標、限制條件、輸出格式"
        tool_text = "、".join(tool_names) if tool_names else "web.search、web.fetch"
        lines = [
            f"# TODO Plan: {objective}",
            "",
            "- [ ] concept_alignment 概念對齊與關鍵概念查證",
            f"  - Goal: 先釐清「{concept_text}」的定義、邊界與常見歧義，再開始詳細規劃。",
            "  - Skill: concept-alignment",
            "  - DoD: 產出關鍵概念、查詢方向、資料可信度與後續規劃注意事項。",
            "- [ ] taskgraph_outline 任務骨架與依賴切分",
            "  - Goal: 先切出主要任務節點、順序與完成條件。",
            "  - Skill: problem-decomposer",
            "  - DoD: 每個節點都有目標、DoD、工具範圍與必要輸出。",
            "- [ ] taskgraph_detail TaskGraph v3 詳細設計",
            "  - Goal: 補全節點 prompt、可用工具、邊與執行順序。",
            "  - DoD: 產出可執行的 taskgraph.v3 JSON。",
            "- [ ] run_execute 依圖執行與整理回覆",
            "  - Goal: 按節點執行、更新狀態並彙整結果。",
            "  - DoD: 回傳最終回覆、產物摘要與耗時分解。",
            "",
            f"> 關鍵概念：{concept_text}",
            f"> 初步工具範圍：{tool_text}",
            "",
        ]
        return "\n".join(lines)

    def _materialize_quick_todo_preview(
        self,
        objective: str,
        *,
        project_path: Path,
        project_id: str | None = None,
        available_tools: list[dict[str, Any]] | None = None,
    ) -> str:
        docs_dir = project_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        todo_markdown = self._build_quick_todo_markdown(objective, available_tools=available_tools)
        self._atomic_write_text(docs_dir / "TODO.md", todo_markdown)
        emit_event(
            {
                "type": "plan_generated",
                "scope": "planning",
                "project_id": project_id or self.resolve_project_identity(project_path)[0],
                "actor": "system",
                "payload": {
                    "objective": objective,
                    "preview": True,
                    "output_paths": ["docs/TODO.md"],
                },
                "risk": "low",
            }
        )
        return todo_markdown

    def _extract_planning_keywords(self, text: str, *, limit: int = 6) -> list[str]:
        normalized = unicodedata.normalize("NFKC", str(text or ""))
        candidates = re.findall(r"[A-Za-z][A-Za-z0-9_.-]{2,}|[\u4e00-\u9fff]{2,8}", normalized)
        stopwords = {
            "請幫我",
            "幫我",
            "需要",
            "進行",
            "產出",
            "請先",
            "任務",
            "流程",
            "規劃",
            "設計",
            "詳細",
            "完整",
            "todo",
            "task",
            "graph",
        }
        results: list[str] = []
        seen: set[str] = set()
        for token in candidates:
            cleaned = token.strip().strip(".,:;()[]{}")
            lowered = cleaned.lower()
            if not cleaned or cleaned in stopwords or lowered in seen:
                continue
            seen.add(lowered)
            results.append(cleaned)
            if len(results) >= limit:
                break
        return results

    def _select_planning_tools(self, objective: str, available_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not available_tools:
            return []
        normalized = unicodedata.normalize("NFKC", str(objective or "")).lower()
        categories = {
            "research": {"web.search", "web.fetch", "web.better_search"},
            "code": {
                "filesystem.list",
                "filesystem.read",
                "filesystem.grep",
                "filesystem.glob",
                "filesystem.patch",
                "filesystem.write",
                "terminal.exec",
                "process.exec",
                "sandbox.run",
                "artifacts.preview_diff",
            },
            "artifacts": {"artifacts.write_text", "artifacts.write_file", "artifacts.preview_diff"},
            "memory": {"memory.search", "memory.get", "memory.put"},
            "audit": {"audit.log_query", "audit.export"},
        }
        selected = set(categories["research"])
        if any(token in normalized for token in {"code", "程式", "修改", "修正", "檔案", "bug", "test", "測試", "repo", "專案"}):
            selected.update(categories["code"])
        if any(token in normalized for token in {"文件", "報告", "markdown", "文檔", "輸出", "artifact"}):
            selected.update(categories["artifacts"])
        if any(token in normalized for token in {"記憶", "記錄", "脈絡", "上下文", "memory"}):
            selected.update(categories["memory"])
        if any(token in normalized for token in {"稽核", "審核", "audit", "log", "記錄查詢"}):
            selected.update(categories["audit"])
        narrowed = [item for item in available_tools if str(item.get("name") or "") in selected]
        return narrowed or list(available_tools)

    def _postprocess_planner_graph(
        self,
        graph: GraphDefinition,
        *,
        message: str,
        available_tools: list[dict[str, Any]],
    ) -> GraphDefinition:
        tool_names = {str(item.get("name") or "") for item in available_tools if str(item.get("name") or "").strip()}
        nodes = list(graph.nodes)
        edges = list(graph.edges)
        incoming_control: dict[str, int] = {node.id: 0 for node in nodes}
        for edge in edges:
            if edge.edge_type == "CONTROL":
                incoming_control[edge.to_node] = incoming_control.get(edge.to_node, 0) + 1
        root_targets = [
            node.id
            for node in nodes
            if node.id != "concept_alignment"
            and node.node_type in {"TASK", "GATE", "GROUP"}
            and incoming_control.get(node.id, 0) == 0
        ]
        if not any(node.id == "concept_alignment" for node in nodes):
            keywords = self._extract_planning_keywords(message, limit=5)
            keyword_text = "、".join(keywords) if keywords else "任務目標、限制條件、輸出格式"
            concept_tools = [name for name in ("web.better_search", "web.search", "web.fetch") if name in tool_names]
            nodes.insert(
                0,
                TaskNode(
                    id="concept_alignment",
                    title="概念對齊",
                    task_spec=TaskSpec(
                        executor="agent",
                        agent=AgentTaskConfig(
                            prompt=(
                                "請先做概念對齊。"
                                f"先抽取任務中的關鍵概念：{keyword_text}。"
                                "請用關鍵字策略先搜尋並整理：名詞定義、範圍邊界、易混淆點、目前版本差異、"
                                "接下來規劃 TaskGraph 時應注意的限制。"
                                "若資料不足，請明確標記限制與待補證據。"
                            ),
                            instructions="輸出請使用繁體中文，並先給概念摘要，再給規劃注意事項。",
                            allowed_tools=concept_tools,
                        ),
                        display=TaskDisplayMetadata(
                            label="概念對齊",
                            summary="先查證關鍵概念與限制，避免後續節點設計偏題。",
                            todo_hint="完成關鍵概念、風險與查詢摘要。",
                            tags=["concept_alignment", "research"],
                        ),
                    ),
                ),
            )
            for target_id in root_targets:
                edges.append(GraphEdge(from_node="concept_alignment", to_node=target_id, edge_type="CONTROL", kind="DEPENDS_ON"))
        control_predecessors = self._build_control_predecessors(edges)
        problem_decomposer_bound = False
        for node in nodes:
            if not isinstance(node, TaskNode) or node.task_spec.executor != "agent" or node.task_spec.agent is None:
                continue
            if node.id == "concept_alignment":
                self._bind_agent_skills(node, "concept-alignment")
            elif not problem_decomposer_bound and self._is_todo_planning_task(node):
                self._bind_agent_skills(node, "problem-decomposer")
                problem_decomposer_bound = True
            if node.id != "concept_alignment":
                binding_spec = self._select_planner_context_binding(node.id, control_predecessors)
                if binding_spec is not None:
                    binding_key, binding_from_node, prompt_prefix = binding_spec
                    has_context_binding = any(
                        binding.source == "upstream"
                        and binding.from_node == binding_from_node
                        and binding.key == binding_key
                        for binding in node.task_spec.input_bindings
                    )
                    if not has_context_binding:
                        node.task_spec.input_bindings.append(
                            InputBinding(
                                source="upstream",
                                key=binding_key,
                                from_node=binding_from_node,
                                port="raw",
                            )
                        )
                    prompt_text = node.task_spec.agent.prompt or ""
                    if f"${{{binding_key}}}" not in prompt_text:
                        node.task_spec.agent.prompt = f"{prompt_prefix}{prompt_text}" if prompt_text else prompt_prefix.rstrip()
            if node.task_spec.agent.allowed_tools:
                continue
            node.task_spec.agent.allowed_tools = self._suggest_agent_tools_for_task(
                " ".join(
                    filter(
                        None,
                        [
                            node.title,
                            node.task_spec.agent.prompt or "",
                            node.task_spec.agent.instructions or "",
                            node.task_spec.display.summary or "",
                            node.task_spec.display.todo_hint or "",
                        ],
                    )
                ),
                available_tools,
            )
        return GraphDefinition(
            id=graph.id,
            version=graph.version,
            name=graph.name,
            description=graph.description,
            status=graph.status,
            created_at=graph.created_at,
            updated_at=graph.updated_at,
            created_by=graph.created_by,
            updated_by=graph.updated_by,
            entity_version=graph.entity_version,
            nodes=nodes,
            edges=edges,
            metadata=graph.metadata,
            runtime_capabilities=graph.runtime_capabilities,
        )

    @staticmethod
    def _planning_default_skill_names() -> list[str]:
        return ["concept-alignment", "problem-decomposer"]

    def _merge_planning_available_skills(
        self,
        available_skills: list[dict[str, Any]] | None,
        project_path: Path | None,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for skill in available_skills or []:
            name = str(skill.get("name") or "").strip()
            if name and name not in seen:
                merged.append(skill)
                seen.add(name)
        for skill in self._load_skills(self._planning_default_skill_names(), project_path, ignore_missing=True):
            name = str(skill.get("name") or "").strip()
            if name and name not in seen:
                merged.append(skill)
                seen.add(name)
        return merged

    @staticmethod
    def _bind_agent_skills(node: TaskNode, *skill_names: str) -> None:
        if node.task_spec.agent is None:
            return
        existing = list(node.task_spec.agent.skills)
        for skill_name in skill_names:
            trimmed = str(skill_name).strip()
            if trimmed and trimmed not in existing:
                existing.append(trimmed)
        node.task_spec.agent.skills = existing
        if node.task_spec.display:
            tags = list(node.task_spec.display.tags)
            for skill_name in skill_names:
                trimmed = str(skill_name).strip()
                if trimmed and trimmed not in tags:
                    tags.append(trimmed)
            node.task_spec.display.tags = tags

    @staticmethod
    def _is_todo_planning_task(node: TaskNode) -> bool:
        agent = node.task_spec.agent
        if agent is None:
            return False
        normalized = unicodedata.normalize(
            "NFKC",
            " ".join(
                filter(
                    None,
                    [
                        node.id,
                        node.title,
                        node.task_spec.display.label if node.task_spec.display else "",
                        node.task_spec.display.summary if node.task_spec.display else "",
                        node.task_spec.display.todo_hint if node.task_spec.display else "",
                        agent.prompt or "",
                        agent.instructions or "",
                    ],
                )
            ),
        ).lower()
        strong_tokens = {
            "taskgraph_outline",
            "todo",
            "todolist",
            "待辦",
            "骨架",
            "拆解",
            "分解",
            "依賴",
            "wbs",
            "issue tree",
            "problem decomposition",
            "problem-decomposer",
        }
        return any(token in normalized for token in strong_tokens)

    @staticmethod
    def _task_skill_names(node: TaskNode) -> list[str]:
        if node.task_spec.agent is not None:
            return [name for name in node.task_spec.agent.skills if str(name).strip()]
        if node.task_spec.tool is not None:
            return [name for name in node.task_spec.tool.skills if str(name).strip()]
        return []

    @staticmethod
    def _build_control_predecessors(edges: list[GraphEdge]) -> dict[str, list[str]]:
        predecessors: dict[str, list[str]] = {}
        for edge in edges:
            if edge.edge_type != "CONTROL":
                continue
            predecessors.setdefault(edge.to_node, []).append(edge.from_node)
        return predecessors

    @staticmethod
    def _select_planner_context_binding(
        node_id: str,
        control_predecessors: dict[str, list[str]],
    ) -> tuple[str, str, str] | None:
        predecessors = [item for item in control_predecessors.get(node_id, []) if item]
        non_concept_predecessors = [item for item in predecessors if item != "concept_alignment"]
        if len(non_concept_predecessors) == 1:
            return (
                "upstream_context",
                non_concept_predecessors[0],
                "前置節點輸出摘要：\n${upstream_context}\n\n"
                "請直接完成本節點交付物，不要重複需求釐清、概念對齊或研究起手式。\n\n",
            )
        if not non_concept_predecessors and "concept_alignment" in predecessors:
            return (
                "concept_alignment_context",
                "concept_alignment",
                "前置概念摘要（僅作背景，勿重複概念對齊）：\n${concept_alignment_context}\n\n",
            )
        return None

    def _suggest_agent_tools_for_task(self, text: str, available_tools: list[dict[str, Any]]) -> list[str]:
        available_names = {str(item.get("name") or "") for item in available_tools if str(item.get("name") or "").strip()}
        normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
        selected: list[str] = []

        def _add(*names: str) -> None:
            for name in names:
                if name in available_names and name not in selected:
                    selected.append(name)

        if any(token in normalized for token in {"概念", "查證", "搜尋", "研究", "資料來源", "比較", "最新", "search", "cite"}):
            _add("web.better_search", "web.search", "web.fetch")
        if any(token in normalized for token in {"檔案", "程式", "修改", "修正", "讀取", "掃描", "patch", "file", "code", "test", "測試"}):
            _add(
                "filesystem.list",
                "filesystem.read",
                "filesystem.grep",
                "filesystem.glob",
                "filesystem.patch",
                "filesystem.write",
                "terminal.exec",
                "process.exec",
                "sandbox.run",
                "artifacts.preview_diff",
            )
        if any(token in normalized for token in {"輸出", "文件", "報告", "markdown", "artifact"}):
            _add("artifacts.write_text", "artifacts.write_file", "artifacts.preview_diff")
        if any(token in normalized for token in {"記憶", "上下文", "脈絡", "memory"}):
            _add("memory.search", "memory.get", "memory.put")
        if any(token in normalized for token in {"審核", "稽核", "audit", "log"}):
            _add("audit.log_query", "audit.export")
        return selected

    def run_plan_execute_stream(
        self,
        prompt: str,
        *,
        project_path: Path,
        project_id: str | None = None,
        model: str | None = None,
        llm_client=None,
        available_tools: list[dict[str, Any]] | None = None,
        available_skills: list[dict[str, Any]] | None = None,
        stream_handler=None,
        todo_handler=None,
        run_id: str | None = None,
        thread_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        request_id: str | None = None,
    ) -> tuple[TaskGraph3RunResult, str]:
        planning_stream_closed = False

        def _emit_planning_progress(text: str) -> None:
            nonlocal planning_stream_closed
            if not callable(stream_handler):
                return
            if planning_stream_closed:
                return
            try:
                stream_handler(encode_reasoning_chunk(text))
            except (ConnectionAbortedError, BrokenPipeError):
                planning_stream_closed = True
                self.logger.info("planning progress stream closed: client disconnected")
            except Exception:
                planning_stream_closed = True
                self.logger.exception("planning progress stream failed unexpectedly")

        def _run_with_heartbeat(step_name: str, action, *, interval_s: float = 3.0):
            if not callable(stream_handler):
                return action()

            done_event = threading.Event()
            started_at = time.monotonic()

            def _heartbeat() -> None:
                while not done_event.wait(interval_s):
                    if planning_stream_closed:
                        done_event.set()
                        break
                    elapsed_s = int(time.monotonic() - started_at)
                    _emit_planning_progress(f"{step_name}，已等待 {elapsed_s} 秒…")

            worker = threading.Thread(target=_heartbeat, daemon=True)
            worker.start()
            try:
                return action()
            finally:
                done_event.set()
                worker.join(timeout=0.2)

        config = self.load_config(project_path)
        planner_enabled = self._coerce_config_bool(config.get("amon", {}).get("planner", {}).get("enabled", True))
        if not planner_enabled:
            project_identity = project_id or self.resolve_project_identity(project_path)[0]
            self.logger.warning("planner 設定為 disabled，但 task graph v3 已強制啟用（project_id=%s）", project_identity)
            log_event(
                {
                    "level": "WARNING",
                    "event": "graph_force_enable_planner",
                    "project_id": project_identity,
                    "reason": "planner disabled in config but ignored by task graph v3",
                }
            )
            emit_event(
                {
                    "type": "graph_force_enable_planner",
                    "scope": "planning",
                    "project_id": project_identity,
                    "actor": "system",
                    "payload": {"reason": "planner disabled in config but ignored by task graph v3"},
                    "risk": "low",
                }
            )

        phase_metrics: dict[str, int] = {}
        overall_started_at = time.monotonic()
        resolved_project_id = project_id or project_path.name
        if available_tools is None:
            available_tools = self.describe_available_tools(project_id=resolved_project_id)

        _emit_planning_progress("正在產生 TODO 初稿…")
        phase_started_at = time.monotonic()
        quick_todo_markdown = self._materialize_quick_todo_preview(
            prompt,
            project_path=project_path,
            project_id=resolved_project_id,
            available_tools=available_tools,
        )
        phase_metrics["todo_bootstrap_ms"] = int((time.monotonic() - phase_started_at) * 1000)
        if callable(todo_handler):
            try:
                todo_handler(quick_todo_markdown)
            except Exception:
                self.logger.exception("todo preview handler failed unexpectedly")

        _emit_planning_progress("TODO 初稿已產生，正在設計詳細任務計畫…")
        phase_started_at = time.monotonic()
        plan = _run_with_heartbeat(
            "任務計畫產生中",
            lambda: self.generate_plan_docs(
                prompt,
                project_path=project_path,
                project_id=resolved_project_id,
                llm_client=llm_client,
                model=model,
                available_tools=available_tools,
                available_skills=available_skills,
                run_id=run_id,
                thread_id=thread_id,
                request_id=request_id,
            ),
        )
        phase_metrics["plan_generation_ms"] = int((time.monotonic() - phase_started_at) * 1000)

        _emit_planning_progress("任務計畫已產生，正在準備執行圖…")
        phase_started_at = time.monotonic()
        plan_graph_payload = json.loads(dumps_graph_definition(plan))
        phase_metrics["compile_graph_ms"] = int((time.monotonic() - phase_started_at) * 1000)
        emit_event(
            {
                "type": "plan_compiled",
                "scope": "planning",
                "project_id": project_id or self.resolve_project_identity(project_path)[0],
                "actor": "system",
                "payload": {
                    "node_count": len(plan_graph_payload.get("nodes", [])),
                    "edge_count": len(plan_graph_payload.get("edges", [])),
                },
                "risk": "low",
            }
        )
        graph_path = self._write_graph_resolved(
            project_path,
            plan_graph_payload,
            {},
            mode="taskgraph.v3",
        )
        _emit_planning_progress("執行圖準備完成，開始執行任務…")
        phase_started_at = time.monotonic()
        runtime_variables: dict[str, Any] = {}
        if conversation_history:
            runtime_variables["conversation_history"] = conversation_history
        if thread_id:
            runtime_variables["thread_id"] = thread_id
        result = _run_with_heartbeat(
            "任務執行中",
            lambda: self.run_graph(
                project_path=project_path,
                graph_path=graph_path,
                variables=runtime_variables,
                stream_handler=stream_handler,
                run_id=run_id,
                thread_id=thread_id,
                request_id=request_id,
            ),
        )
        phase_metrics["run_graph_ms"] = int((time.monotonic() - phase_started_at) * 1000)
        _emit_planning_progress("任務已執行完成，正在整理結果…")
        phase_metrics["total_ms"] = int((time.monotonic() - overall_started_at) * 1000)
        setattr(result, "phase_metrics", phase_metrics)
        setattr(result, "execution_route", "planner")
        setattr(result, "planner_enabled", True)
        return result, self._load_graph_primary_output(result.run_dir)

    def run_graph_stream(
        self,
        prompt: str,
        *,
        project_path: Path,
        project_id: str | None = None,
        model: str | None = None,
        llm_client=None,
        available_tools: list[dict[str, Any]] | None = None,
        available_skills: list[dict[str, Any]] | None = None,
        stream_handler=None,
        todo_handler=None,
        run_id: str | None = None,
        thread_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        request_id: str | None = None,
    ) -> tuple[TaskGraph3RunResult, str]:
        return self.run_plan_execute_stream(
            prompt,
            project_path=project_path,
            project_id=project_id,
            model=model,
            llm_client=llm_client,
            available_tools=available_tools,
            available_skills=available_skills,
            stream_handler=stream_handler,
            todo_handler=todo_handler,
            run_id=run_id,
            thread_id=thread_id,
            conversation_history=conversation_history,
            request_id=request_id,
        )

    def run_graph_response(
        self,
        prompt: str,
        *,
        project_path: Path,
        project_id: str | None = None,
        model: str | None = None,
        llm_client=None,
        available_tools: list[dict[str, Any]] | None = None,
        available_skills: list[dict[str, Any]] | None = None,
        stream_handler=None,
    ) -> str:
        _, response = self.run_graph_stream(
            prompt,
            project_path=project_path,
            project_id=project_id,
            model=model,
            llm_client=llm_client,
            available_tools=available_tools,
            available_skills=available_skills,
            stream_handler=stream_handler,
        )
        return response

    @staticmethod
    def _coerce_config_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"", "0", "false", "no", "off"}:
                return False
            if normalized in {"1", "true", "yes", "on"}:
                return True
        return bool(value)

    def _collect_mnt_data_handover_context(self, project_path: Path) -> str:
        docs_dir = project_path / "docs"
        if not docs_dir.exists():
            return "未找到專案 docs 資料夾，視為首次執行。"

        summary_lines: list[str] = [f"- docs（project: {project_path.name}）"]
        key_files = [
            docs_dir / "TODO.md",
            docs_dir / "ProjectManager.md",
            docs_dir / "final.md",
        ]
        try:
            child_names = sorted(path.name for path in docs_dir.iterdir())[:12]
        except OSError as exc:
            self.logger.warning("掃描專案 docs 失敗：%s", exc)
            return "掃描專案 docs 失敗，請在回覆中聲明無法接續既有文件。"
        if child_names:
            summary_lines.append(f"  - 目錄內容預覽：{', '.join(child_names)}")

        for key_file in key_files:
            if not key_file.exists() or not key_file.is_file():
                continue
            try:
                preview = key_file.read_text(encoding="utf-8")[:300].replace("\n", " ")
            except OSError:
                preview = "（讀取失敗）"
            summary_lines.append(f"  - {key_file.relative_to(project_path)}: {preview}")

        if len(summary_lines) == 1:
            summary_lines.append("  - 尚未找到 TODO.md / ProjectManager.md / final.md")
        return "\n".join(summary_lines)

    def export_project(self, project_id: str, output_path: Path) -> Path:
        record = self.get_project(project_id)
        project_path = Path(record.path)
        if not project_path.exists():
            raise FileNotFoundError(f"專案路徑不存在：{project_path}")
        output_path = output_path.expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload_paths = [
            project_path / "amon.project.yaml",
            project_path / "docs",
            project_path / "tasks",
            project_path / "sessions",
            project_path / "logs",
        ]
        base_prefix = project_id
        try:
            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in payload_paths:
                    self._add_export_path(archive, path, base_prefix, project_path)
        except OSError as exc:
            self.logger.error("匯出專案失敗：%s", exc, exc_info=True)
            raise
        log_event(
            {
                "level": "INFO",
                "event": "project_export",
                "project_id": project_id,
                "output_path": str(output_path),
            }
        )
        return output_path

    def _build_single_graph(self) -> dict[str, Any]:
        return build_single_graph_payload()

    def _build_self_critique_graph(self) -> dict[str, Any]:
        return build_self_critique_graph_payload()

    def _build_team_graph(self) -> dict[str, Any]:
        return build_team_graph_payload()

    def _write_graph_resolved(
        self,
        project_path: Path,
        graph: dict[str, Any],
        variables: dict[str, Any],
        mode: str,
    ) -> Path:
        graphs_dir = project_path / ".amon" / "graphs"
        graphs_dir.mkdir(parents=True, exist_ok=True)
        resolved = {
            "version": "taskgraph.v3",
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
            "variables": variables,
        }
        graph_path = graphs_dir / f"{mode}_graph.resolved.json"
        atomic_write_text(graph_path, json.dumps(resolved, ensure_ascii=False, indent=2))
        return graph_path

    def _load_graph_primary_output(self, run_dir: Path) -> str:
        state_path = run_dir / "state.json"
        if not state_path.exists():
            return ""
        state = json.loads(state_path.read_text(encoding="utf-8"))
        project_path = run_dir.parents[2]
        for node_state in state.get("nodes", {}).values():
            output = node_state.get("output") or {}
            output_path = output.get("output_path") or output.get("path")
            if output_path:
                target = project_path / output_path
                if target.exists():
                    return target.read_text(encoding="utf-8")
        return ""

    def _sync_team_tasks(self, project_path: Path, tasks_dir: Path, docs_dir: Path) -> None:
        tasks_source = docs_dir / "tasks.json"
        if not tasks_source.exists():
            raise FileNotFoundError("找不到 tasks.json，請確認 team graph 是否成功產生。")
        tasks_payload = self._parse_tasks_payload(tasks_source.read_text(encoding="utf-8"))
        if not tasks_payload.get("tasks"):
            tasks_payload["tasks"] = [
                {
                    "task_id": "t0",
                    "title": "預設任務",
                    "requiredCapabilities": [],
                    "status": "done",
                    "attempts": 0,
                    "feedback": None,
                }
            ]
        for task in tasks_payload["tasks"]:
            task.setdefault("task_id", "t0")
            task.setdefault("title", "未命名任務")
            task.setdefault("status", "done")
            task.setdefault("requiredCapabilities", [])
            task.setdefault("attempts", 0)
            task.setdefault("feedback", None)
        tasks_path = tasks_dir / "tasks.json"
        atomic_write_text(tasks_path, json.dumps(tasks_payload, ensure_ascii=False, indent=2))

    def _parse_tasks_payload(self, text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    payload = json.loads(text[start : end + 1])
                    if isinstance(payload, dict):
                        return payload
                except json.JSONDecodeError:
                    pass
        return {"tasks": []}

    def run_graph(
        self,
        project_path: Path,
        graph_path: Path,
        variables: dict[str, Any] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        request_id: str | None = None,
        thread_id: str | None = None,
    ) -> TaskGraph3RunResult:
        if not project_path:
            raise ValueError("執行 graph 需要指定專案")
        try:
            graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 graph 失敗：%s", exc, exc_info=True)
            raise

        if not isinstance(graph_payload, dict) or str(graph_payload.get("version") or "") != "taskgraph.v3":
            raise ValueError("Unsupported graph format: only taskgraph.v3 is supported.")

        effective_run_id = run_id or uuid.uuid4().hex
        runtime_vars = dict(graph_payload.get("variables", {})) if isinstance(graph_payload.get("variables"), dict) else {}
        if variables:
            runtime_vars.update(variables)

        graph = self._to_taskgraph3_definition(graph_payload)
        runtime = TaskGraph3Runtime(project_path=project_path, graph=graph, run_id=effective_run_id)
        node_runner = AmonNodeRunner(
            core=self,
            project_path=project_path,
            run_id=effective_run_id,
            variables=runtime_vars,
            stream_handler=stream_handler,
            request_id=request_id,
            thread_id=thread_id,
        )
        result = runtime.run(node_runner.run_task)
        return result

    def _to_taskgraph3_definition(self, payload: dict[str, Any]) -> GraphDefinition:
        return graph_definition_from_payload(payload)

    def _to_taskgraph3_node(self, raw: dict[str, Any]):
        node_type = str(raw.get("node_type") or "").upper()
        node_id = str(raw.get("id") or "")
        title = str(raw.get("title") or "")

        if node_type == "GATE":
            routes: list[GateRoute] = []
            for route in raw.get("routes", []):
                if not isinstance(route, dict):
                    continue
                routes.append(GateRoute(on_outcome=str(route.get("onOutcome") or "default"), to_node=str(route.get("toNode") or "")))
            return GateNode(id=node_id, title=title, routes=routes)

        if node_type == "GROUP":
            children = [str(item) for item in raw.get("children", []) if str(item).strip()]
            return GroupNode(id=node_id, title=title, children=children)

        if node_type == "ARTIFACT":
            return ArtifactNode(id=node_id, title=title)

        if isinstance(raw.get("taskSpec"), dict):
            spec = raw["taskSpec"]
            return TaskNode(
                id=node_id,
                title=title,
                execution=str(raw.get("execution") or "SINGLE"),
                execution_config=raw.get("executionConfig") if isinstance(raw.get("executionConfig"), dict) else None,
                task_spec=task_spec_from_payload(spec),
            )
        raise ValueError(f"Unsupported node payload: node_id={node_id}")

    def run_taskgraph3(
        self,
        prompt: str,
        *,
        project_path: Path,
        project_id: str | None = None,
        model: str | None = None,
        llm_client=None,
        skill_names: list[str] | None = None,
    ) -> str:
        resolved_project_id = project_id or self.resolve_project_identity(project_path)[0]
        available_tools = self.describe_available_tools(project_id=resolved_project_id)
        available_skills = self._load_skills(
            self._normalize_skill_names(skill_names),
            project_path,
            ignore_missing=True,
        )
        return self.run_graph_response(
            prompt,
            project_path=project_path,
            project_id=resolved_project_id,
            available_tools=available_tools,
            available_skills=available_skills,
            llm_client=llm_client,
            model=model,
        )

    def get_run_status(self, project_path: Path, run_id: str) -> dict[str, Any]:
        if not project_path:
            raise ValueError("查詢 run 狀態需要指定專案")
        run_dir = project_path / ".amon" / "runs" / run_id
        state_path = run_dir / "state.json"
        if not state_path.exists():
            return {"run_id": run_id, "status": "not_found"}
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 run 狀態失敗：%s", exc, exc_info=True)
            raise
        return payload

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        from amon.jobs.runner import status_job

        status = status_job(job_id, data_dir=self.data_dir)
        return {
            "job_id": status.job_id,
            "status": status.status,
            "last_heartbeat_ts": status.last_heartbeat_ts,
            "last_error": status.last_error,
            "last_event_id": status.last_event_id,
        }

    def create_graph_template(self, project_id: str, run_id: str, name: str | None = None) -> dict[str, Any]:
        self.ensure_base_structure()
        project_path = self.get_project_path(project_id)
        resolved_path = project_path / ".amon" / "runs" / run_id / "graph.resolved.json"
        if not resolved_path.exists():
            raise FileNotFoundError("找不到 graph.resolved.json")
        try:
            resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 graph.resolved.json 失敗：%s", exc, exc_info=True)
            raise
        template_id = uuid.uuid4().hex
        template_dir = self.templates_dir / template_id
        template_dir.mkdir(parents=True, exist_ok=False)
        template_schema = self._build_template_schema({})
        payload = {
            "template_id": template_id,
            "name": name or f"{project_id}-{run_id}",
            "project_id": project_id,
            "source_run_id": run_id,
            "created_at": self._now(),
            "variables_schema": template_schema,
            "version": "taskgraph.v3",
            "metadata": resolved.get("metadata"),
            "nodes": resolved.get("nodes", []),
            "edges": resolved.get("edges", []),
            "variables": resolved.get("variables", {}),
        }
        template_path = template_dir / "graph.template.json"
        schema_path = template_dir / "schema.json"
        self._atomic_write_text(template_path, json.dumps(payload, ensure_ascii=False, indent=2))
        self._atomic_write_text(schema_path, json.dumps(template_schema, ensure_ascii=False, indent=2))
        return {"template_id": template_id, "path": str(template_path), "schema_path": str(schema_path)}

    def parametrize_graph_template(self, template_id: str, json_path: str, var_name: str) -> dict[str, Any]:
        template_path = self._template_path(template_id)
        try:
            payload = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 graph.template.json 失敗：%s", exc, exc_info=True)
            raise
        schema = self._load_template_schema(template_path, payload)
        tokens = self._parse_json_path(json_path)
        parent, last_token = self._locate_json_target(payload, tokens)
        try:
            original_value = parent[last_token]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("JSONPath 指向的欄位不存在") from exc
        placeholder = f"{{{{{var_name}}}}}"
        parent[last_token] = placeholder
        schema = self._merge_template_schema(schema, var_name, original_value)
        payload["variables_schema"] = schema
        schema_path = template_path.parent / "schema.json"
        self._atomic_write_text(template_path, json.dumps(payload, ensure_ascii=False, indent=2))
        self._atomic_write_text(schema_path, json.dumps(schema, ensure_ascii=False, indent=2))
        return {"template_id": template_id, "path": str(template_path), "schema_path": str(schema_path)}

    def run_graph_template(self, template_id: str, variables: dict[str, Any] | None = None) -> TaskGraph3RunResult:
        template_path = self._template_path(template_id)
        try:
            payload = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 graph.template.json 失敗：%s", exc, exc_info=True)
            raise
        project_id = payload.get("project_id")
        if not project_id:
            raise ValueError("template 缺少 project_id")
        schema = self._load_template_schema(template_path, payload)
        variables = variables or {}
        variables = self._apply_schema_defaults(schema, variables)
        if str(payload.get("version") or "") != "taskgraph.v3":
            raise ValueError("Unsupported graph format: only taskgraph.v3 is supported.")
        graph = {
            "version": "taskgraph.v3",
            "nodes": payload.get("nodes", []),
            "edges": payload.get("edges", []),
            "variables": payload.get("variables", {}),
        }
        resolved_graph = self._resolve_template_values(graph, variables)
        template_dir = template_path.parent
        rendered_path = template_dir / "graph.rendered.json"
        self._atomic_write_text(rendered_path, json.dumps(resolved_graph, ensure_ascii=False, indent=2))
        project_path = self.get_project_path(project_id)
        return self.run_graph(project_path=project_path, graph_path=rendered_path, variables=variables)

    def _template_path(self, template_id: str) -> Path:
        template_path = self.templates_dir / template_id / "graph.template.json"
        if not template_path.exists():
            raise FileNotFoundError("找不到 graph.template.json")
        return template_path

    def _build_template_schema(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {"type": "object", "required": [], "properties": properties}

    def _normalize_template_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        if "properties" in schema or "required" in schema:
            schema.setdefault("type", "object")
            schema.setdefault("properties", {})
            schema.setdefault("required", [])
            return schema
        properties = {}
        for name, entry in schema.items():
            if isinstance(entry, dict):
                properties[name] = entry
            else:
                properties[name] = {"type": entry}
        required = list(properties.keys())
        return {"type": "object", "required": required, "properties": properties}

    def _merge_template_schema(self, schema: dict[str, Any], var_name: str, original_value: Any) -> dict[str, Any]:
        schema = self._normalize_template_schema(schema)
        properties = schema.setdefault("properties", {})
        properties[var_name] = {
            "type": self._infer_schema_type(original_value),
            "default": original_value,
        }
        required = schema.setdefault("required", [])
        if var_name not in required:
            required.append(var_name)
        return schema

    def _load_template_schema(self, template_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        schema_path = template_path.parent / "schema.json"
        if schema_path.exists():
            try:
                schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
                return self._normalize_template_schema(schema_payload)
            except (OSError, json.JSONDecodeError) as exc:
                self.logger.error("讀取 schema.json 失敗：%s", exc, exc_info=True)
                raise
        return self._normalize_template_schema(payload.get("variables_schema", {}))

    def _apply_schema_defaults(self, schema: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
        schema = self._normalize_template_schema(schema)
        properties = schema.get("properties", {})
        merged = dict(variables)
        for name, entry in properties.items():
            if name not in merged and isinstance(entry, dict) and "default" in entry:
                merged[name] = entry["default"]
        missing = [name for name in schema.get("required", []) if name not in merged]
        if missing:
            raise ValueError(f"template 缺少變數：{', '.join(missing)}")
        return merged

    def _resolve_template_values(self, payload: Any, variables: dict[str, Any]) -> Any:
        if isinstance(payload, dict):
            return {key: self._resolve_template_values(value, variables) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self._resolve_template_values(item, variables) for item in payload]
        if isinstance(payload, str):
            return self._replace_placeholders(payload, variables)
        return payload

    def _replace_placeholders(self, text: str, variables: dict[str, Any]) -> str:
        updated = text
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            updated = updated.replace(placeholder, "" if value is None else str(value))
        return updated

    def _parse_json_path(self, json_path: str) -> list[Any]:
        if not json_path:
            raise ValueError("JSONPath 不可為空")
        path = json_path.strip()
        if path.startswith("$"):
            path = path[1:]
        if path.startswith("."):
            path = path[1:]
        tokens: list[Any] = []
        index = 0
        while index < len(path):
            if path[index] == ".":
                index += 1
                continue
            if path[index] == "[":
                end = path.find("]", index)
                if end == -1:
                    raise ValueError("JSONPath 缺少 ]")
                raw = path[index + 1 : end].strip()
                if (raw.startswith("\"") and raw.endswith("\"")) or (raw.startswith("'") and raw.endswith("'")):
                    raw = raw[1:-1]
                    tokens.append(raw)
                elif raw.isdigit():
                    tokens.append(int(raw))
                elif raw:
                    tokens.append(raw)
                else:
                    raise ValueError("JSONPath 索引不可為空")
                index = end + 1
                continue
            next_index = index
            while next_index < len(path) and path[next_index] not in ".[" :
                next_index += 1
            token = path[index:next_index]
            if not token:
                raise ValueError("JSONPath 片段不可為空")
            tokens.append(token)
            index = next_index
        if not tokens:
            raise ValueError("JSONPath 不可為空")
        return tokens

    def _locate_json_target(self, payload: Any, tokens: list[Any]) -> tuple[Any, Any]:
        current = payload
        for token in tokens[:-1]:
            if isinstance(token, int):
                if not isinstance(current, list) or token >= len(current):
                    raise ValueError("JSONPath 指向的陣列不存在")
                current = current[token]
            else:
                if not isinstance(current, dict) or token not in current:
                    raise ValueError("JSONPath 指向的欄位不存在")
                current = current[token]
        return current, tokens[-1]

    def _infer_schema_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int) and not isinstance(value, bool):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        if value is None:
            return "null"
        return "string"

    def run_eval(self, suite: str = "basic") -> dict[str, Any]:
        if suite != "basic":
            raise ValueError(f"不支援的評測套件：{suite}")
        self.ensure_base_structure()
        project_name = f"eval-basic-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        project = self.create_project(project_name)
        project_path = Path(project.path)
        self.set_config_value("amon.provider", "openai", project_path=project_path)
        log_event(
            {
                "level": "INFO",
                "event": "eval_start",
                "suite": suite,
                "project_id": project.project_id,
            }
        )

        results: list[dict[str, Any]] = []
        failures: list[str] = []
        tasks = [
            ("single", "請輸出評測訊息。"),
            ("self_critique", "請建立評測草稿。"),
            ("team", "請完成評測任務。"),
        ]
        for mode, task_prompt in tasks:
            try:
                if mode == "single":
                    self.run_single(task_prompt, project_path=project_path)
                elif mode == "self_critique":
                    self.run_self_critique(task_prompt, project_path=project_path)
                elif mode == "team":
                    self.run_team(task_prompt, project_path=project_path)
                else:
                    raise ValueError(f"未知模式：{mode}")
                results.append({"task": mode, "status": "passed"})
            except Exception as exc:  # noqa: BLE001
                results.append({"task": mode, "status": "failed", "error": str(exc)})
                failures.append(mode)

        checks = self._validate_eval_outputs(project_path)
        for check in checks:
            if check["status"] != "passed":
                failures.append(check["check"])

        status = "passed" if not failures else "failed"
        payload = {
            "suite": suite,
            "project_id": project.project_id,
            "status": status,
            "tasks": results,
            "checks": checks,
        }
        log_event(
            {
                "level": "INFO" if status == "passed" else "ERROR",
                "event": "eval_complete",
                "suite": suite,
                "project_id": project.project_id,
                "status": status,
            }
        )
        return payload

    def doctor(self) -> dict[str, Any]:
        self.ensure_base_structure()
        checks = {
            "root": self._doctor_root(),
            "config": self._doctor_config(),
            "model": self._doctor_model(),
            "skills_index": self._doctor_skills_index(),
            "mcp": self._doctor_mcp(),
        }
        status_order = {"ok": 0, "warning": 1, "error": 2}
        overall = max(checks.values(), key=lambda item: status_order.get(item["status"], 2))["status"]
        return {"status": overall, "checks": checks}

    def _doctor_root(self) -> dict[str, str]:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            probe_path = self.cache_dir / "doctor_probe.txt"
            self._atomic_write_text(probe_path, "ok")
            probe_path.unlink(missing_ok=True)
            return {"status": "ok", "message": "資料目錄可讀寫"}
        except OSError as exc:
            self.logger.error("doctor root 檢查失敗：%s", exc, exc_info=True)
            return {"status": "error", "message": f"資料目錄無法讀寫：{exc}"}

    def _doctor_config(self) -> dict[str, str]:
        try:
            _ = self.load_config()
            return {"status": "ok", "message": "設定檔讀取正常"}
        except Exception as exc:  # noqa: BLE001
            self.logger.error("doctor config 檢查失敗：%s", exc, exc_info=True)
            return {"status": "error", "message": f"設定檔讀取失敗：{exc}"}

    def _doctor_model(self) -> dict[str, str]:
        try:
            config = self.load_config()
            provider_name = config.get("amon", {}).get("provider", "openai")
            provider_cfg = config.get("providers", {}).get(provider_name, {})
            provider_type = provider_cfg.get("type")
            if provider_type == "mock":
                provider_cfg = {
                    "type": "openai_compatible",
                    "base_url": provider_cfg.get("base_url") or "https://api.openai.com/v1",
                    "api_key_env": provider_cfg.get("api_key_env") or "OPENAI_API_KEY",
                }
                provider_type = "openai_compatible"
            if provider_type != "openai_compatible":
                return {"status": "error", "message": f"不支援的 provider 類型：{provider_type}"}
            base_url = str(provider_cfg.get("base_url", ""))
            api_key_env = str(provider_cfg.get("api_key_env", ""))
            api_key = os.getenv(api_key_env) if api_key_env else None
            if not base_url:
                return {"status": "error", "message": "模型 base_url 未設定"}
            if not api_key:
                return {"status": "error", "message": f"缺少 API Key（請設定環境變數 {api_key_env}）"}
            request = urllib.request.Request(base_url, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
                    return {"status": "ok", "message": f"模型連線正常（HTTP {response.status}）"}
            except urllib.error.HTTPError as exc:
                return {"status": "warning", "message": f"模型連線可達但回應錯誤（HTTP {exc.code}）"}
            except urllib.error.URLError as exc:
                return {"status": "error", "message": f"模型連線失敗：{exc}"}
        except Exception as exc:  # noqa: BLE001
            self.logger.error("doctor model 檢查失敗：%s", exc, exc_info=True)
            return {"status": "error", "message": f"模型檢查失敗：{exc}"}

    def _doctor_skills_index(self) -> dict[str, str]:
        index_path = self._skills_index_path()
        legacy_path = self.cache_dir / "skills_index.json"
        if not index_path.exists() and legacy_path.exists():
            index_path = legacy_path
        if not index_path.exists():
            return {"status": "warning", "message": "尚未建立 skills index（請執行 amon skills scan）"}
        try:
            _ = json.loads(index_path.read_text(encoding="utf-8"))
            return {"status": "ok", "message": "skills index 正常"}
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("doctor skills index 檢查失敗：%s", exc, exc_info=True)
            return {"status": "error", "message": f"skills index 讀取失敗：{exc}"}

    def _doctor_mcp(self) -> dict[str, str]:
        config = self.load_config()
        servers = config.get("mcp", {}).get("servers", {}) or {}
        if not servers:
            return {"status": "warning", "message": "未設定 MCP servers"}
        registry = self.refresh_mcp_registry()
        errors = []
        for name, info in registry.get("servers", {}).items():
            if info.get("error"):
                errors.append(f"{name}: {info['error']}")
        if errors:
            return {"status": "error", "message": "MCP 檢查失敗：" + "; ".join(errors)}
        return {"status": "ok", "message": "MCP tools 連線正常"}

    def _load_tasks_payload(self, tasks_path: Path) -> dict[str, Any]:
        if not tasks_path.exists():
            return {"tasks": []}
        try:
            return json.loads(tasks_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 tasks.json 失敗：%s", exc, exc_info=True)
            raise

    def _write_tasks_payload(self, tasks_path: Path, payload: dict[str, Any]) -> None:
        try:
            self._atomic_write_text(tasks_path, json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入 tasks.json 失敗：%s", exc, exc_info=True)
            raise

    def _normalize_team_tasks(self, tasks: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id") or task.get("id") or f"task-{index}")
            title = str(task.get("title") or task.get("name") or f"任務 {index}")
            capabilities = task.get("requiredCapabilities") or task.get("required_capabilities") or task.get("capabilities")
            if isinstance(capabilities, str):
                capabilities = [capabilities]
            if not isinstance(capabilities, list):
                capabilities = []
            status = str(task.get("status") or "todo")
            attempts = int(task.get("attempts", 0) or 0)
            feedback = task.get("feedback")
            normalized.append(
                {
                    "task_id": task_id,
                    "title": title,
                    "requiredCapabilities": capabilities,
                    "status": status,
                    "attempts": attempts,
                    "feedback": feedback,
                }
            )
        if not normalized:
            normalized.append(
                {
                    "task_id": "task-1",
                    "title": "預設任務",
                    "requiredCapabilities": ["generalist"],
                    "status": "todo",
                    "attempts": 0,
                    "feedback": None,
                }
            )
        return normalized

    def _parse_json_payload(self, text: str) -> Any:
        text = text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        if "```" in text:
            for chunk in text.split("```"):
                candidate = chunk.strip()
                if not candidate:
                    continue
                lines = candidate.splitlines()
                if lines and lines[0].strip().lower() in {"json", "jsonl"}:
                    candidate = "\n".join(lines[1:]).strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        start_positions = [pos for pos in [text.find("{"), text.find("[")] if pos != -1]
        if not start_positions:
            return None
        start = min(start_positions)
        end = max(text.rfind("}"), text.rfind("]"))
        if end == -1 or end <= start:
            return None
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None

    def scan_skills(self, project_path: Path | None = None) -> list[dict[str, Any]]:
        config = self.load_config(project_path)
        skills: list[dict[str, Any]] = []
        global_dir = Path(config["skills"]["global_dir"]).expanduser()
        if global_dir.exists():
            skills.extend(self._scan_skill_dir(global_dir, source="global"))
        if project_path:
            project_dir = project_path / config["skills"]["project_dir_rel"]
            if project_dir.exists():
                skills.extend(self._scan_skill_dir(project_dir, source="project"))
        skills = sorted(skills, key=lambda item: (item.get("name", ""), item.get("source", ""), item.get("path", "")))
        index_path = self._skills_index_path()
        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write_text(index_path, json.dumps({"skills": skills}, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入技能索引失敗：%s", exc, exc_info=True)
            raise
        return skills

    def list_skills(self) -> list[dict[str, Any]]:
        index_path = self._skills_index_path()
        legacy_path = self.cache_dir / "skills_index.json"
        if not index_path.exists() and legacy_path.exists():
            index_path = legacy_path
        if not index_path.exists():
            return []
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取技能索引失敗：%s", exc, exc_info=True)
            raise
        return data.get("skills", [])

    def get_skill(self, name: str, project_path: Path | None = None) -> dict[str, Any]:
        return self.load_skill(name, project_path=project_path)

    def load_skill(
        self,
        name: str,
        project_path: Path | None = None,
        *,
        stream_handler=None,
        project_id: str | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if project_path:
            skills = self.scan_skills(project_path)
        else:
            skills = self.list_skills()
            if not skills:
                skills = self.scan_skills()
        for skill in skills:
            if skill.get("name") != name:
                continue
            if skill.get("entry_path"):
                archive_path = Path(skill["path"])
                entry_path = str(skill["entry_path"])
                try:
                    with zipfile.ZipFile(archive_path, "r") as archive:
                        content = archive.read(entry_path).decode("utf-8")
                        references = self._list_skill_references_archive(archive, entry_path)
                except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
                    self.logger.error("讀取技能壓縮檔失敗：%s", exc, exc_info=True)
                    raise
            else:
                try:
                    content = Path(skill["path"]).read_text(encoding="utf-8")
                except OSError as exc:
                    self.logger.error("讀取技能檔案失敗：%s", exc, exc_info=True)
                    raise
                references = self._list_skill_references(Path(skill["path"]).parent)
            loaded = {**skill, "content": content, "references": references}
            resolved_project_id = project_id
            if resolved_project_id is None and project_path:
                resolved_project_id = self.resolve_project_identity(project_path)[0]
            log_event(
                {
                    "level": "INFO",
                    "event": "skill_load",
                    "project_id": resolved_project_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "node_id": node_id,
                    "request_id": request_id,
                    "skill_name": str(loaded.get("name") or name),
                    "skill_source": loaded.get("source"),
                    "skill_path": loaded.get("path"),
                    "reference_count": len(references),
                }
            )
            self._emit_stream_event(
                stream_handler,
                "skill",
                {
                    "name": str(loaded.get("name") or name),
                    "source": loaded.get("source"),
                    "path": loaded.get("path"),
                    "reference_count": len(references),
                    "run_id": run_id,
                    "node_id": node_id,
                    "thread_id": thread_id,
                    "request_id": request_id,
                },
            )
            return loaded
        raise KeyError(f"找不到技能：{name}")

    def load_project_config(self, project_path: Path) -> tuple[str, str, dict[str, Any]]:
        identity = load_project_config(project_path)
        return identity.project_id, identity.project_name, identity.config

    def get_project_path(self, project_id: str) -> Path:
        self.project_registry.scan()
        try:
            return self.project_registry.get_path(project_id)
        except KeyError:
            direct_path = self.projects_dir / project_id
            if direct_path.exists():
                return direct_path
            for record in self._load_records():
                if record.project_id == project_id:
                    return Path(record.path)
            record = self.get_project(project_id)
            return Path(record.path)

    def resolve_project_identity(self, project_path: Path | None) -> tuple[str | None, str | None]:
        if not project_path:
            return None, None
        try:
            identity = load_project_config(project_path)
            return identity.project_id, identity.project_name
        except Exception:
            return project_path.name, project_path.name

    def add_allowed_tool(self, tool_name: str) -> None:
        config_path = self._global_config_path()
        config = read_yaml(config_path)
        mcp = config.setdefault("mcp", {})
        tools = mcp.setdefault("allowed_tools", [])
        if tool_name not in tools:
            tools.append(tool_name)
            write_yaml(config_path, config)

    def remove_allowed_tool(self, tool_name: str) -> None:
        config_path = self._global_config_path()
        config = read_yaml(config_path)
        mcp = config.setdefault("mcp", {})
        tools = mcp.setdefault("allowed_tools", [])
        if tool_name in tools:
            tools.remove(tool_name)
            write_yaml(config_path, config)

    def refresh_mcp_registry(self) -> dict[str, Any]:
        return self.get_mcp_registry(refresh=True)

    def get_mcp_registry(self, refresh: bool = False) -> dict[str, Any]:
        self.ensure_base_structure()
        config = self.load_config()
        servers = self._load_mcp_servers(config)
        registry = {"updated_at": self._now(), "servers": {}}
        for server in servers:
            if not refresh:
                cached = self._read_mcp_cache(server.name)
                if cached:
                    registry["servers"][server.name] = cached
                    continue
            info = self._fetch_mcp_tools(server)
            registry["servers"][server.name] = info
            self._write_mcp_cache(server.name, info)
        self._write_mcp_registry(registry)
        return registry

    def call_mcp_tool(self, server_name: str, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.ensure_base_structure()
        from .tooling.audit import FileAuditSink, default_audit_log_path
        from .tooling.types import ToolCall, ToolResult

        start = time.monotonic()
        def _duration_ms() -> int:
            return max(0, int((time.monotonic() - start) * 1000))

        audit_sink = FileAuditSink(default_audit_log_path())
        config = self.load_config()
        servers = {server.name: server for server in self._load_mcp_servers(config)}
        if server_name not in servers:
            raise KeyError(f"找不到 MCP server：{server_name}")
        server = servers[server_name]
        full_tool = f"{server_name}:{tool_name}"
        call = ToolCall(tool=full_tool, args=args, caller="mcp")
        if self._is_tool_denied(full_tool, config, server):
            result = ToolResult(
                content=[{"type": "text", "text": "DENIED_BY_POLICY: 工具已被拒絕"}],
                is_error=True,
                meta={"status": "denied"},
            )
            audit_sink.record(call, result, "deny", duration_ms=_duration_ms(), source="mcp")
            raise PermissionError("DENIED_BY_POLICY: 工具已被拒絕")
        if not self._is_tool_allowed(full_tool, config, server):
            result = ToolResult(
                content=[{"type": "text", "text": "DENIED_BY_POLICY: 工具尚未被允許"}],
                is_error=True,
                meta={"status": "denied"},
            )
            audit_sink.record(call, result, "deny", duration_ms=_duration_ms(), source="mcp")
            raise PermissionError("DENIED_BY_POLICY: 工具尚未被允許")
        if self._is_high_risk_tool(tool_name):
            plan = make_change_plan(
                [
                    {
                        "action": "執行高風險工具",
                        "target": full_tool,
                        "detail": "包含 write/delete 等可能影響資料的操作",
                    }
                ]
            )
            if not require_confirm(plan):
                log_event(
                    {
                        "level": "INFO",
                        "event": "mcp_tool_cancelled",
                        "tool_name": full_tool,
                    }
                )
                result = ToolResult(
                    content=[{"type": "text", "text": "使用者取消操作"}],
                    is_error=True,
                    meta={"status": "cancelled"},
                )
                audit_sink.record(call, result, "deny", duration_ms=_duration_ms(), source="mcp")
                raise RuntimeError("使用者取消操作")
        if server.transport != "stdio" or not server.command:
            raise RuntimeError("目前僅支援 stdio transport")
        try:
            with MCPStdioClient(server.command) as client:
                result = client.call_tool(tool_name, args)
        except MCPClientError as exc:
            self.logger.error("MCP tool 呼叫失敗：%s", exc, exc_info=True)
            error_result = ToolResult(
                content=[{"type": "text", "text": f"MCP tool 呼叫失敗：{exc}"}],
                is_error=True,
                meta={"status": "client_error"},
            )
            audit_sink.record(call, error_result, "allow", duration_ms=_duration_ms(), source="mcp")
            raise
        if result is None:
            result = {}
        elif not isinstance(result, dict):
            result = {"content": [{"type": "text", "text": str(result)}], "isError": False}
        is_error = bool(result.get("isError") or result.get("is_error"))
        formatted_result = {
            "data": result,
            "is_error": is_error,
            "meta": {"status": "error" if is_error else "ok"},
        }
        formatted_result["data_prompt"] = self._format_mcp_result(full_tool, result)

        audit_result = ToolResult(
            content=list(result.get("content") or []),
            is_error=is_error,
            meta=formatted_result["meta"],
        )
        audit_sink.record(call, audit_result, "allow", duration_ms=_duration_ms(), source="mcp")
        log_event(
            {
                "level": "INFO",
                "event": "mcp_tool_call",
                "server": server_name,
                "tool_name": tool_name,
                "is_error": is_error,
            }
        )
        return formatted_result

        raw = result if isinstance(result, dict) else {"result": result}
        is_error = bool(raw.get("is_error") or raw.get("isError"))
        content = raw.get("content")
        normalized_content = content if isinstance(content, list) else [{"type": "json", "data": raw}]
        audit_result = ToolResult(
            content=normalized_content,
            is_error=is_error,
            meta={"status": "error" if is_error else "ok"},
        )
        audit_sink.record(call, audit_result, "allow", duration_ms=_duration_ms(), source="mcp")
        log_event(
            {
                "level": "INFO",
                "event": "mcp_tool_call",
                "server": server_name,
                "tool": tool_name,
                "is_error": is_error,
            }
        )
        return {
            "is_error": is_error,
            "meta": {"status": "error" if is_error else "ok"},
            "data": raw,
            "content": normalized_content,
            "content_text": audit_result.as_text(),
            "data_prompt": json.dumps(raw, ensure_ascii=False),
        }


    def call_tool_unified(
        self,
        tool_name: str,
        args: dict[str, Any],
        project_id: str | None = None,
        timeout_s: int | None = None,
        cancel_event: threading.Event | None = None,
        stream_handler=None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        route = "toolforge"
        event_base = {
            "name": tool_name,
            "run_id": run_id,
            "node_id": node_id,
            "thread_id": thread_id,
            "request_id": request_id,
        }
        if ":" in tool_name:
            route = "mcp"
            log_event(
                {
                    "level": "INFO",
                    "event": "tool_call",
                    "project_id": project_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "node_id": node_id,
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "route": route,
                    "stage": "start",
                }
            )
            self._emit_stream_event(stream_handler, "tool_call", {**event_base, "route": route, "stage": "start", "status": "running"})
            server_name, actual_tool = tool_name.split(":", 1)
            result = self.call_mcp_tool(server_name, actual_tool, args)
        elif "." in tool_name:
            route = "builtin"
            project_path = self.get_project_path(project_id) if project_id else Path.cwd()
            registry = build_registry(project_path)
            call = ToolCall(tool=tool_name, args=args, caller="graph", project_id=project_id)
            log_event(
                {
                    "level": "INFO",
                    "event": "tool_call",
                    "project_id": project_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "node_id": node_id,
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "route": route,
                    "stage": "start",
                }
            )
            self._emit_stream_event(stream_handler, "tool_call", {**event_base, "route": route, "stage": "start", "status": "running"})
            tool_result = registry.call(call)
            result = {
                "is_error": bool(tool_result.is_error),
                "meta": dict(tool_result.meta or {}),
                "content_text": tool_result.as_text(),
                "content": list(tool_result.content or []),
            }
        else:
            result = self.run_tool(
                tool_name,
                args,
                project_id=project_id,
                timeout_s=timeout_s,
                cancel_event=cancel_event,
                stream_handler=stream_handler,
                run_id=run_id,
                node_id=node_id,
                thread_id=thread_id,
                request_id=request_id,
            )

        payload = {
            "tool_name": tool_name,
            "route": route,
            "project_id": project_id,
            "is_error": bool(result.get("is_error", False)),
            "status": (result.get("meta") or {}).get("status"),
        }
        if route in {"mcp", "builtin"}:
            log_event(
                {
                    "level": "INFO",
                    "event": "tool_call",
                    "project_id": project_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "node_id": node_id,
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "route": route,
                    "stage": "complete",
                    "status": payload["status"] or ("error" if payload["is_error"] else "ok"),
                    "is_error": payload["is_error"],
                }
            )
        log_event({"level": "INFO", "event": "tool_dispatch", **payload})
        if route in {"mcp", "builtin"}:
            self._emit_stream_event(
                stream_handler,
                "tool_call",
                {
                    **event_base,
                    "route": route,
                    "stage": "complete",
                    "status": payload["status"] or ("error" if payload["is_error"] else "ok"),
                    "is_error": payload["is_error"],
                },
            )
        emit_event(
            {
                "type": "tool_dispatch",
                "scope": "tooling",
                "project_id": project_id,
                "actor": "system",
                "payload": payload,
                "risk": "low",
            }
        )
        return result

    def describe_available_tools(self, project_id: str | None = None) -> list[dict[str, Any]]:
        project_path = self.get_project_path(project_id) if project_id else Path.cwd()
        registry = build_registry(project_path)
        builtin_tools = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                "source": "builtin",
            }
            for spec in sorted(registry.list_specs(), key=lambda item: item.name)
        ]
        toolforge_tools = [
            {
                "name": str(item.get("name") or ""),
                "description": "",
                "input_schema": {},
                "source": "toolforge",
                "scope": item.get("scope"),
            }
            for item in self.list_tools(project_id=project_id)
        ]
        try:
            mcp_registry = self.get_mcp_registry(refresh=False)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("讀取 MCP tools 失敗，改用空清單：%s", exc)
            mcp_registry = {"servers": {}}

        mcp_tools: list[dict[str, Any]] = []
        servers = mcp_registry.get("servers", {}) if isinstance(mcp_registry, dict) else {}
        for server_name, server_info in sorted(servers.items(), key=lambda item: item[0]):
            tools = server_info.get("tools", []) if isinstance(server_info, dict) else []
            for tool in tools:
                if not isinstance(tool, dict):
                    continue
                name = str(tool.get("name") or "")
                mcp_tools.append(
                    {
                        "name": f"{server_name}:{name}" if name else f"{server_name}:",
                        "description": str(tool.get("description") or ""),
                        "input_schema": tool.get("input_schema") or {},
                        "source": "mcp",
                    }
                )

        merged = builtin_tools + sorted(toolforge_tools, key=lambda item: item["name"]) + sorted(
            mcp_tools,
            key=lambda item: item["name"],
        )
        merged.sort(key=lambda item: (str(item.get("source") or ""), str(item.get("name") or "")))
        json.dumps(merged, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return merged

    def forge_tool(self, project_id: str, tool_name: str, spec: str) -> Path:
        self.ensure_base_structure()
        ensure_tool_name(tool_name)
        record = self.get_project(project_id)
        project_path = Path(record.path)
        tool_dir = project_path / "tools" / tool_name
        if tool_dir.exists():
            raise FileExistsError(f"工具已存在：{tool_name}")
        tool_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = tool_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        tool_yaml = {
            "name": tool_name,
            "version": "0.1.0",
            "inputs_schema": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "要處理的文字"}},
                "required": ["text"],
            },
            "outputs_schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            "risk_level": "low",
            "allowed_paths": ["workspace"],
        }
        tool_py = self._render_tool_template(tool_name, spec)
        readme = self._render_tool_readme(tool_name, spec)
        test_py = self._render_tool_test(tool_name)
        try:
            (tool_dir / "tool.py").write_text(tool_py, encoding="utf-8")
            write_tool_spec(tool_dir / "tool.yaml", tool_yaml)
            (tool_dir / "README.md").write_text(readme, encoding="utf-8")
            (tests_dir / "test_tool.py").write_text(test_py, encoding="utf-8")
        except OSError as exc:
            self.logger.error("建立工具失敗：%s", exc, exc_info=True)
            raise
        log_event(
            {
                "level": "INFO",
                "event": "tool_forge",
                "project_id": project_id,
                "tool_name": tool_name,
            }
        )
        return tool_dir

    def list_tools(self, project_id: str | None = None) -> list[dict[str, Any]]:
        self.ensure_base_structure()
        project_path = Path(self.get_project(project_id).path) if project_id else None
        tools: dict[str, dict[str, Any]] = {}
        for scope, base in self._tool_base_dirs(project_path):
            if not base.exists():
                continue
            for entry in sorted(base.iterdir()):
                if not entry.is_dir():
                    continue
                try:
                    spec = load_tool_spec(entry)
                except ToolingError:
                    continue
                tools[spec.name] = {
                    "name": spec.name,
                    "version": spec.version,
                    "risk_level": spec.risk_level,
                    "path": str(entry),
                    "scope": scope,
                }
        return sorted(tools.values(), key=lambda item: item["name"])

    def run_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
        project_id: str | None = None,
        *,
        project_path: Path | None = None,
        timeout_s: int | None = None,
        cancel_event: threading.Event | None = None,
        stream_handler=None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_base_structure()
        builtin_workspace = project_path or (Path(self.get_project(project_id).path) if project_id else Path.cwd())
        builtin_registry = build_registry(builtin_workspace)
        builtin_spec = builtin_registry.get_spec(tool_name)
        route = "builtin" if builtin_spec is not None else "toolforge"
        target_path = str(payload.get("path") or payload.get("root") or payload.get("cwd") or "") if isinstance(payload, dict) else ""
        resolved_project_id = project_id
        if resolved_project_id is None and project_path:
            resolved_project_id = self.resolve_project_identity(project_path)[0]
        log_event(
            {
                "level": "INFO",
                "event": "tool_call",
                "project_id": resolved_project_id,
                "run_id": run_id,
                "thread_id": thread_id,
                "node_id": node_id,
                "request_id": request_id,
                "tool_name": tool_name,
                "route": route,
                "stage": "start",
                "path": target_path or None,
            }
        )
        self._emit_stream_event(
            stream_handler,
            "tool_call",
            {
                "name": tool_name,
                "route": route,
                "stage": "start",
                "status": "running",
                "path": target_path or None,
                "run_id": run_id,
                "node_id": node_id,
                "thread_id": thread_id,
                "request_id": request_id,
            },
        )
        if builtin_spec is not None:
            call_args = dict(payload)
            for key in ("path", "root", "cwd"):
                value = call_args.get(key)
                if isinstance(value, str) and value and not Path(value).is_absolute():
                    call_args[key] = str((builtin_workspace / value).resolve())
            call = ToolCall(tool=tool_name, args=call_args, caller="taskgraph", project_id=project_id)
            result = builtin_registry.get_handler(tool_name)(call)
            normalized_result = {
                "content": result.content,
                "is_error": result.is_error,
                "meta": result.meta,
                "text": result.as_text(),
            }
            log_event(
                {
                    "level": "INFO",
                    "event": "tool_call",
                    "project_id": resolved_project_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "node_id": node_id,
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "route": route,
                    "stage": "complete",
                    "status": str((result.meta or {}).get("status") or ("error" if result.is_error else "ok")),
                    "is_error": bool(result.is_error),
                }
            )
            self._emit_stream_event(
                stream_handler,
                "tool_call",
                {
                    "name": tool_name,
                    "route": route,
                    "stage": "complete",
                    "status": str((result.meta or {}).get("status") or ("error" if result.is_error else "ok")),
                    "is_error": bool(result.is_error),
                    "run_id": run_id,
                    "node_id": node_id,
                    "thread_id": thread_id,
                    "request_id": request_id,
                },
            )
            return normalized_result
        tool_dir, scope, project_path = self._resolve_tool_dir(tool_name, project_id)
        spec = load_tool_spec(tool_dir)
        project_allowed = self._resolve_project_allowed_paths(project_path)
        resolved_allowed = resolve_allowed_paths(spec.allowed_paths, project_path, project_allowed)
        if spec.risk_level.lower() == "high":
            plan = build_confirm_plan(tool_name, spec.risk_level)
            if not require_confirm(plan):
                raise RuntimeError("已取消執行工具")
        env = build_tool_env(self.logs_dir if not project_path else project_path / "logs", resolved_allowed, project_path)
        execution_backend = str((spec.execution or {}).get("backend") or "host").strip().lower()
        if execution_backend == "sandbox":
            tool_code = (tool_dir / "tool.py").read_text(encoding="utf-8")
            payload_text = json.dumps(payload, ensure_ascii=False)
            wrapped_code = "\n".join(
                [
                    "import io",
                    "import sys",
                    f"sys.stdin = io.StringIO({payload_text!r})",
                    tool_code,
                ]
            )
            run_id = uuid.uuid4().hex
            safe_tool_name = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_name)
            output_prefix = f"docs/artifacts/{run_id}/tool_{safe_tool_name}/"
            sandbox_result = run_sandbox_step(
                project_path=project_path or self.data_dir,
                config=self.load_config(project_path),
                run_id=run_id,
                step_id=f"tool_{safe_tool_name}",
                language="python",
                code=wrapped_code,
                input_paths=[],
                output_prefix=output_prefix,
                timeout_s=timeout_s,
            )
            output = {
                "exit_code": sandbox_result.get("exit_code"),
                "timed_out": bool(sandbox_result.get("timed_out", False)),
                "duration_ms": sandbox_result.get("duration_ms"),
                "stdout": sandbox_result.get("stdout", ""),
                "stderr": sandbox_result.get("stderr", ""),
                "manifest_path": sandbox_result.get("manifest_path"),
            }
        else:
            output = run_tool_process(
                tool_dir / "tool.py",
                payload,
                env=env,
                cwd=project_path,
                timeout_s=timeout_s or 60,
                cancel_event=cancel_event,
            )
        final_project_id = self.resolve_project_identity(project_path)[0] if project_path else resolved_project_id
        log_event(
            {
                "level": "INFO",
                "event": "tool_run",
                "tool_name": tool_name,
                "scope": scope,
                "project_id": final_project_id,
            }
        )
        log_event(
            {
                "level": "INFO",
                "event": "tool_call",
                "project_id": final_project_id,
                "run_id": run_id,
                "thread_id": thread_id,
                "node_id": node_id,
                "request_id": request_id,
                "tool_name": tool_name,
                "route": route,
                "stage": "complete",
                "status": str((output.get("meta") or {}).get("status") or ("error" if output.get("is_error") else "ok")),
                "is_error": bool(output.get("is_error", False)),
            }
        )
        self._emit_stream_event(
            stream_handler,
            "tool_call",
            {
                "name": tool_name,
                "route": route,
                "stage": "complete",
                "status": str((output.get("meta") or {}).get("status") or ("error" if output.get("is_error") else "ok")),
                "is_error": bool(output.get("is_error", False)),
                "run_id": run_id,
                "node_id": node_id,
                "thread_id": thread_id,
                "request_id": request_id,
            },
        )
        return output

    def test_tool(self, tool_name: str, project_id: str | None = None) -> None:
        self.ensure_base_structure()
        tool_dir, _, project_path = self._resolve_tool_dir(tool_name, project_id)
        spec = load_tool_spec(tool_dir)
        project_allowed = self._resolve_project_allowed_paths(project_path)
        resolved_allowed = resolve_allowed_paths(spec.allowed_paths, project_path, project_allowed)
        env = build_tool_env(self.logs_dir if not project_path else project_path / "logs", resolved_allowed, project_path)
        tests_dir = tool_dir / "tests"
        if tests_dir.exists():
            test_files = [path for path in sorted(tests_dir.iterdir()) if path.suffix == ".py"]
        else:
            test_files = []
        if not test_files:
            run_tool_process(tool_dir / "tool.py", {}, env=env, cwd=project_path)
            return
        for test_path in test_files:
            try:
                result = subprocess.run(
                    [sys.executable, str(test_path)],
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=str(tool_dir),
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self.logger.error("執行測試失敗：%s", exc, exc_info=True)
                raise
            if result.returncode != 0:
                self.logger.error("工具測試失敗：%s", result.stderr.strip())
                raise RuntimeError("工具測試失敗")

    def register_tool(self, tool_name: str, project_id: str | None = None) -> dict[str, Any]:
        self.ensure_base_structure()
        self.test_tool(tool_name, project_id=project_id)
        tool_dir, scope, project_path = self._resolve_tool_dir(tool_name, project_id)
        spec = load_tool_spec(tool_dir)
        registry_path = self.cache_dir / "tool_registry.json"
        entry = format_registry_entry(spec, tool_dir, scope, self.resolve_project_identity(project_path)[0] if project_path else None)
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"tools": []}
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取工具 registry 失敗：%s", exc, exc_info=True)
            raise
        tools = [item for item in data.get("tools", []) if item.get("name") != tool_name or item.get("scope") != scope]
        tools.append(entry)
        data["tools"] = tools
        try:
            self._atomic_write_text(registry_path, json.dumps(data, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入工具 registry 失敗：%s", exc, exc_info=True)
            raise
        log_event(
            {
                "level": "INFO",
                "event": "tool_register",
                "tool_name": tool_name,
                "scope": scope,
                "project_id": self.resolve_project_identity(project_path)[0] if project_path else None,
            }
        )
        return entry

    def toolforge_init(self, name: str, base_dir: Path | None = None) -> Path:
        ensure_tool_name(name)
        root = base_dir or Path.cwd()
        tool_dir = root / name
        if tool_dir.exists():
            raise FileExistsError(f"工具資料夾已存在：{tool_dir}")
        tool_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = tool_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        tool_yaml = {
            "name": name,
            "version": "0.1.0",
            "description": f"{name} native tool",
            "risk": "low",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "要處理的文字"}},
                "required": ["text"],
            },
            "output_schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            "default_permission": "allow",
            "permissions": {"allow": [f"native:{name}"]},
            "examples": [{"name": "basic", "input": {"text": "hello"}}],
        }
        tool_py = self._render_native_tool_template(name)
        readme = self._render_native_tool_readme(name)
        test_py = self._render_native_tool_test(name)
        try:
            (tool_dir / "tool.py").write_text(tool_py, encoding="utf-8")
            (tool_dir / "tool.yaml").write_text(
                yaml.safe_dump(tool_yaml, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            (tool_dir / "README.md").write_text(readme, encoding="utf-8")
            (tests_dir / "test_tool.py").write_text(test_py, encoding="utf-8")
        except OSError as exc:
            self.logger.error("建立 toolforge 工具失敗：%s", exc, exc_info=True)
            raise
        log_event({"level": "INFO", "event": "toolforge_init", "tool_name": name})
        return tool_dir

    def toolforge_install(self, source: Path, project_id: str | None = None) -> dict[str, Any]:
        self.ensure_base_structure()
        src = source.expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"找不到工具資料夾：{src}")
        manifest, _ = parse_native_manifest(src, strict=True)
        project_path = self.get_project_path(project_id) if project_id else None
        base_dirs = self._native_tool_base_dirs(project_path)
        target_root = next(path for scope, path in base_dirs if scope == ("project" if project_path else "global"))
        target_root.mkdir(parents=True, exist_ok=True)
        dest = target_root / manifest.name
        if dest.exists():
            raise FileExistsError(f"工具已存在：{manifest.name}")
        try:
            shutil.copytree(src, dest)
        except OSError as exc:
            self.logger.error("安裝 toolforge 工具失敗：%s", exc, exc_info=True)
            raise
        entry = {
            "name": manifest.name,
            "version": manifest.version,
            "path": str(dest),
            "scope": "project" if project_path else "global",
            "project_id": self.resolve_project_identity(project_path)[0] if project_path else None,
            "sha256": compute_tool_sha256(dest),
            "risk": manifest.risk,
            "default_permission": manifest.default_permission,
            "installed_at": self._now(),
            "status": "active",
            "revoked_at": None,
        }
        self._update_toolforge_index(entry)
        self._sync_tool_registry(self.cache_dir / "tool_registry.json")
        log_event(
            {
                "level": "INFO",
                "event": "toolforge_install",
                "tool_name": manifest.name,
                "scope": entry["scope"],
            }
        )
        return entry

    def toolforge_set_status(self, name: str, status: str, project_id: str | None = None) -> dict[str, Any]:
        if status not in {"active", "disabled"}:
            raise ValueError("status 必須為 active 或 disabled")
        self.ensure_base_structure()
        project_path = self.get_project_path(project_id) if project_id else None
        scope = "project" if project_path else "global"
        index_path = self._toolforge_index_path()
        try:
            data = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"tools": []}
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 toolforge index 失敗：%s", exc, exc_info=True)
            raise
        matched = None
        for item in data.get("tools", []):
            if item.get("name") == name and item.get("scope") == scope and item.get("project_id") == (self.resolve_project_identity(project_path)[0] if project_path else None):
                item["status"] = status
                item["revoked_at"] = self._now() if status == "disabled" else None
                matched = item
                break
        if matched is None:
            raise FileNotFoundError(f"找不到工具：{name}")
        self._atomic_write_text(index_path, json.dumps(data, ensure_ascii=False, indent=2))
        self._sync_tool_registry(self.cache_dir / "tool_registry.json")
        return matched

    def toolforge_verify(self, project_id: str | None = None) -> list[dict[str, Any]]:
        report = self.toolforge_verify_report(project_id=project_id)
        return report.get("tools", [])

    def toolforge_verify_report(self, project_id: str | None = None) -> dict[str, Any]:
        self.ensure_base_structure()
        project_path = self.get_project_path(project_id) if project_id else None
        entries = scan_native_tools(
            self._native_tool_base_dirs(project_path),
            project_id=project_id,
            status_lookup=self._toolforge_status_lookup(),
        )
        results: list[dict[str, Any]] = []
        for entry in entries:
            payload = entry.to_dict()
            test_summary = self._run_toolforge_tests(entry.path)
            payload["tests"] = test_summary
            payload["status"] = entry.status
            payload["ok"] = not payload.get("violations") and test_summary.get("status") in {"passed", "skipped"}
            results.append(payload)
        summary = {
            "total": len(results),
            "ok": sum(1 for item in results if item.get("ok")),
            "failed": sum(1 for item in results if not item.get("ok")),
        }
        return {
            "status": "ok" if summary["failed"] == 0 else "failed",
            "project_id": project_id,
            "summary": summary,
            "tools": results,
            "updated_at": self._now(),
        }

    def list_native_tools(self, project_id: str | None = None) -> list[dict[str, Any]]:
        project_path = self.get_project_path(project_id) if project_id else None
        entries = scan_native_tools(
            self._native_tool_base_dirs(project_path),
            project_id=project_id,
            status_lookup=self._toolforge_status_lookup(),
        )
        return [entry.to_dict() for entry in entries]

    def native_tool_dirs(self, project_id: str | None = None) -> list[tuple[str, Path]]:
        project_path = self.get_project_path(project_id) if project_id else None
        return self._native_tool_base_dirs(project_path)

    def _tool_base_dirs(self, project_path: Path | None) -> list[tuple[str, Path]]:
        config = self.load_config(project_path)
        tools_cfg = config.get("tools", {})
        global_dir = Path(tools_cfg.get("global_dir", self.tools_dir)).expanduser()
        dirs: list[tuple[str, Path]] = [("global", global_dir)]
        if project_path:
            project_rel = tools_cfg.get("project_dir_rel", "tools")
            dirs.insert(0, ("project", project_path / project_rel))
        return dirs

    def _native_tool_base_dirs(self, project_path: Path | None) -> list[tuple[str, Path]]:
        dirs: list[tuple[str, Path]] = [("global", self.tools_dir)]
        if project_path:
            dirs.insert(0, ("project", project_path / ".amon" / "tools"))
        return dirs

    def _toolforge_index_path(self) -> Path:
        return self.cache_dir / "toolforge_index.json"

    def _update_toolforge_index(self, entry: dict[str, Any]) -> None:
        index_path = self._toolforge_index_path()
        try:
            data = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"tools": []}
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 toolforge index 失敗：%s", exc, exc_info=True)
            raise
        tools = [
            item
            for item in data.get("tools", [])
            if item.get("name") != entry.get("name")
            or item.get("scope") != entry.get("scope")
            or item.get("project_id") != entry.get("project_id")
        ]
        entry.setdefault("status", "active")
        entry.setdefault("revoked_at", None)
        tools.append(entry)
        data["tools"] = tools
        try:
            self._atomic_write_text(index_path, json.dumps(data, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入 toolforge index 失敗：%s", exc, exc_info=True)
            raise

    def _toolforge_status_lookup(self) -> dict[tuple[str, str, str | None], str]:
        index_path = self._toolforge_index_path()
        try:
            data = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"tools": []}
        except (OSError, json.JSONDecodeError):
            return {}
        lookup: dict[tuple[str, str, str | None], str] = {}
        for entry in data.get("tools", []):
            if not isinstance(entry, dict):
                continue
            key = (str(entry.get("name", "")), str(entry.get("scope", "global")), entry.get("project_id"))
            if not key[0]:
                continue
            lookup[key] = str(entry.get("status") or "active")
        return lookup

    def _run_toolforge_tests(self, tool_dir: Path) -> dict[str, Any]:
        tests_dir = tool_dir / "tests"
        if not tests_dir.exists() or not tests_dir.is_dir():
            return {"status": "skipped", "command": None, "returncode": None, "output": ""}
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
        result = subprocess.run(command, cwd=tool_dir, capture_output=True, text=True, check=False)
        output = (result.stdout or "") + (result.stderr or "")
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "command": " ".join(command),
            "returncode": result.returncode,
            "output": output.strip(),
        }

    def _resolve_tool_dir(self, tool_name: str, project_id: str | None) -> tuple[Path, str, Path | None]:
        ensure_tool_name(tool_name)
        project_path = Path(self.get_project(project_id).path) if project_id else None
        for scope, base in self._tool_base_dirs(project_path):
            candidate = base / tool_name
            if (candidate / "tool.py").exists():
                return candidate, scope, project_path
        raise FileNotFoundError(f"找不到工具：{tool_name}")

    def _resolve_project_allowed_paths(self, project_path: Path | None) -> list[Path]:
        config = self.load_config(project_path)
        allowed = config.get("tools", {}).get("allowed_paths", ["workspace"])
        resolved: list[Path] = []
        for entry in allowed:
            path = Path(entry)
            if not path.is_absolute() and project_path:
                path = project_path / path
            resolved.append(path.expanduser())
        if project_path:
            for target in resolved:
                canonicalize_path(target, [project_path])
        return resolved

    def _render_tool_template(self, tool_name: str, spec: str) -> str:
        return render_tool_template(tool_name, spec)

    def _render_tool_readme(self, tool_name: str, spec: str) -> str:
        return render_tool_readme(tool_name, spec)

    def _render_tool_test(self, tool_name: str) -> str:
        return render_tool_test(tool_name)

    def _render_native_tool_template(self, tool_name: str) -> str:
        return render_native_tool_template(tool_name)

    def _render_native_tool_readme(self, tool_name: str) -> str:
        return render_native_tool_readme(tool_name)

    def _render_native_tool_test(self, tool_name: str) -> str:
        return render_native_tool_test(tool_name)

    @staticmethod
    def _format_mcp_result(tool_name: str, result: dict[str, Any]) -> str:
        payload = json.dumps(result, ensure_ascii=False, indent=2)
        return f"[資料]\n工具：{tool_name}\n```json\n{payload}\n```"

    def _generate_project_id(self, name: str) -> str:
        short_id = uuid.uuid4().hex[:6]
        return f"project-{short_id}"

    def _generate_project_slug(self, project_name: str, existing_dir_names: set[str]) -> str:
        base_slug = self._llm_generate_project_slug(project_name) or self._fallback_project_slug(project_name)
        candidate = base_slug
        suffix = uuid.uuid4().hex[:3]
        if candidate in existing_dir_names:
            if self._contains_cjk(candidate):
                candidate = f"{candidate[:6]}·{suffix}"[:10]
            else:
                words = candidate.split("-")
                trimmed = "-".join(words[:4]) if words else "project"
                candidate = f"{trimmed}-{suffix}"
        return candidate or f"project-{suffix}"

    def _llm_generate_project_slug(self, project_name: str) -> str:
        cleaned_name = " ".join(project_name.split()).strip()
        if not cleaned_name:
            return ""
        try:
            config = self.load_config()
            provider_name = config.get("amon", {}).get("provider", "openai")
            provider_cfg = config.get("providers", {}).get(provider_name, {})
            selected_model = provider_cfg.get("default_model") or provider_cfg.get("model")
            provider = build_provider(provider_cfg, model=selected_model)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是專案命名助手。請輸出 JSON：{\"slug\":\"...\"}。"
                        "中文 slug 必須 <=10 字；英文 <=5 words。"
                        "必須語意濃縮，不可直接截斷。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"project_name": cleaned_name}, ensure_ascii=False),
                },
            ]
            chunks = []
            for token in provider.generate_stream(messages, model=selected_model):
                chunks.append(token)
            payload = json.loads("".join(chunks).strip().strip("`"))
            if not isinstance(payload, dict):
                return ""
            return self._sanitize_project_slug(str(payload.get("slug") or ""))
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("LLM 產生 project slug 失敗：%s", exc)
            return ""

    def _fallback_project_slug(self, project_name: str) -> str:
        cleaned = self._sanitize_project_slug(project_name)
        if self._contains_cjk(cleaned):
            return cleaned[:10] or "專案"
        words = [word for word in re.split(r"[^A-Za-z0-9]+", cleaned) if word]
        return "-".join(words[:5]).lower() or "project"

    def _sanitize_project_slug(self, slug: str) -> str:
        cleaned = "".join(ch for ch in slug.strip() if ch.isalnum() or ch in {"-", "_", "·", " "})
        cleaned = "-".join(part for part in cleaned.split() if part)
        if self._contains_cjk(cleaned):
            return cleaned.replace("-", "")[:10]
        return cleaned.lower()

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return any("一" <= char <= "鿿" for char in text)

    def fs_delete(self, target: str | Path) -> str | None:
        self.ensure_base_structure()
        allowed_paths = [self.projects_dir]
        canonical_target = canonicalize_path(Path(target), allowed_paths)
        if not canonical_target.exists():
            raise FileNotFoundError("找不到要刪除的路徑")
        plan = make_change_plan(
            [
                {
                    "action": "移動至回收桶",
                    "target": str(canonical_target),
                    "detail": "可透過 amon fs restore 還原",
                }
            ]
        )
        if not require_confirm(plan):
            log_event(
                {
                    "level": "INFO",
                    "event": "fs_delete_cancelled",
                    "target": str(canonical_target),
                }
            )
            return None
        trash_id = trash_move(canonical_target, self.trash_dir, self.projects_dir)
        log_event(
            {
                "level": "INFO",
                "event": "fs_delete",
                "target": str(canonical_target),
                "trash_id": trash_id,
            }
        )
        return trash_id

    def fs_restore(self, trash_id: str) -> Path:
        self.ensure_base_structure()
        manifest_path = self.trash_dir / trash_id / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError("找不到回收桶項目")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取回收桶清單失敗：%s", exc, exc_info=True)
            raise
        original_path = canonicalize_path(Path(manifest.get("original_path", "")), [self.projects_dir])
        restored_path = trash_restore(trash_id, self.trash_dir)
        if restored_path != original_path:
            self.logger.warning("還原路徑與清單不一致：%s -> %s", original_path, restored_path)
        log_event(
            {
                "level": "INFO",
                "event": "fs_restore",
                "trash_id": trash_id,
                "restored_path": str(restored_path),
            }
        )
        return restored_path


    def _ensure_project_id_alias(self, project_path: Path, project_id: str) -> None:
        alias_path = self.projects_dir / project_id
        if alias_path == project_path or alias_path.exists():
            return
        try:
            alias_path.symlink_to(project_path, target_is_directory=True)
        except OSError:
            # Windows 或受限環境可能無法建立 symlink；忽略相容別名。
            return

    def _create_project_structure(self, project_path: Path) -> None:
        (project_path / "workspace").mkdir(parents=True, exist_ok=True)
        (project_path / "docs").mkdir(parents=True, exist_ok=True)
        (project_path / "tasks").mkdir(parents=True, exist_ok=True)
        (project_path / "sessions").mkdir(parents=True, exist_ok=True)
        (project_path / "memory").mkdir(parents=True, exist_ok=True)
        (project_path / "logs").mkdir(parents=True, exist_ok=True)
        (project_path / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        (project_path / ".amon" / "locks").mkdir(parents=True, exist_ok=True)
        (project_path / ".amon" / "tools").mkdir(parents=True, exist_ok=True)
        (project_path / "tools").mkdir(parents=True, exist_ok=True)

        tasks_path = project_path / "tasks" / "tasks.json"
        if not tasks_path.exists():
            self._atomic_write_text(tasks_path, json.dumps({"tasks": []}, ensure_ascii=False, indent=2))

    def _write_project_config(self, project_path: Path, name: str, project_id: str, project_slug: str | None = None) -> None:
        config_path = project_path / "amon.project.yaml"
        config_data = {
            "amon": {
                "project_id": project_id,
                "project_name": name,
                "project_slug": project_slug or project_path.name,
                "mode": "auto",
            },
            "tools": {"allowed_paths": ["workspace"]},
        }
        self._write_yaml(config_path, config_data)

    def _update_project_config(self, project_path: Path, name: str) -> None:
        config_path = project_path / "amon.project.yaml"
        data = self._read_yaml(config_path) or {}
        data.setdefault("amon", {})
        data["amon"]["project_name"] = name
        self._write_yaml(config_path, data)

    def _save_record(self, record: ProjectRecord) -> None:
        records = self._load_records()
        records.append(record)
        self._write_records(records)

    def _load_records(self) -> list[ProjectRecord]:
        index_path = self.cache_dir / "projects_index.json"
        if not index_path.exists():
            return []
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取專案索引失敗：%s", exc, exc_info=True)
            raise
        return [ProjectRecord(**item) for item in data.get("projects", [])]

    def _write_records(self, records: list[ProjectRecord]) -> None:
        index_path = self.cache_dir / "projects_index.json"
        payload = {"projects": [record.to_dict() for record in records]}
        try:
            self._atomic_write_text(index_path, json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入專案索引失敗：%s", exc, exc_info=True)
            raise

    def _write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        try:
            self._atomic_write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        except OSError as exc:
            self.logger.error("寫入設定檔失敗：%s", exc, exc_info=True)
            raise

    def _atomic_write_text(self, path: Path, content: str) -> None:
        try:
            atomic_write_text(path, content, encoding="utf-8")
        except OSError as exc:
            self.logger.error("寫入檔案失敗：%s", exc, exc_info=True)
            raise

    def _read_yaml(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.logger.error("讀取設定檔失敗：%s", exc, exc_info=True)
            raise

    def _safe_move(self, src: Path, dest: Path, action: str) -> None:
        try:
            shutil.move(src, dest)
        except OSError as exc:
            self.logger.error("%s失敗：%s", action, exc, exc_info=True)
            raise

    def _global_config_path(self) -> Path:
        return self.data_dir / "config.yaml"

    def _initial_config(self) -> dict[str, Any]:
        return {
            "amon": {"data_dir": str(self.data_dir)},
            "paths": {
                "skills_dir": str(self.skills_dir),
                "python_env": str(self.python_env_dir),
                "node_env": str(self.node_env_dir),
            },
            "skills": {"global_dir": str(self.skills_dir)},
        }

    @staticmethod
    def _resolve_data_dir() -> Path:
        env_path = os.environ.get("AMON_HOME")
        if env_path:
            return Path(env_path).expanduser()
        return Path("~/.amon").expanduser()

    def _touch_log(self, path: Path) -> None:
        if path.exists():
            return
        try:
            self._atomic_write_text(path, "")
        except OSError as exc:
            self.logger.error("建立 %s 失敗：%s", path.name, exc, exc_info=True)
            raise

    def _mcp_registry_path(self) -> Path:
        return self.cache_dir / "mcp_registry.json"

    def _mcp_cache_dir(self) -> Path:
        return self.cache_dir / "mcp"

    def _mcp_cache_path(self, server_name: str) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", server_name)
        return self._mcp_cache_dir() / f"{safe_name}.json"

    def _project_config_name(self) -> str:
        return DEFAULT_CONFIG["projects"]["config_name"]

    def _append_trash_entry(self, record: ProjectRecord, trash_path: Path) -> None:
        manifest_path = self.trash_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取回收桶清單失敗：%s", exc, exc_info=True)
            raise
        manifest.setdefault("entries", [])
        manifest["entries"].append(
            {
                "project_id": record.project_id,
                "name": record.name,
                "original_path": record.path,
                "trash_path": str(trash_path),
                "deleted_at": self._now(),
                "restored_at": None,
            }
        )
        try:
            self._atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入回收桶清單失敗：%s", exc, exc_info=True)
            raise

    def _mark_trash_restored(self, project_id: str) -> None:
        manifest_path = self.trash_dir / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取回收桶清單失敗：%s", exc, exc_info=True)
            raise
        for entry in manifest.get("entries", []):
            if entry.get("project_id") == project_id and not entry.get("restored_at"):
                entry["restored_at"] = self._now()
        try:
            self._atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入回收桶清單失敗：%s", exc, exc_info=True)
            raise

    def _scan_skill_dir(self, base_dir: Path, source: str) -> list[dict[str, Any]]:
        skills = []
        for child in sorted(base_dir.iterdir(), key=lambda path: path.name):
            if child.is_dir():
                skill_file = child / "SKILL.md"
                if not skill_file.exists():
                    continue
                skills.append(self._read_skill(skill_file, child.name, source))
                continue
            if not (child.is_file() and child.suffix == ".skill"):
                continue
            loaded = self._read_skill_archive(child, source)
            if loaded:
                skills.append(loaded)
        return skills

    def _read_skill(self, skill_file: Path, fallback_name: str, source: str) -> dict[str, Any]:
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            self.logger.error("讀取技能檔案失敗：%s", exc, exc_info=True)
            raise
        return self._build_skill_metadata(
            content=content,
            fallback_name=fallback_name,
            source=source,
            path=skill_file,
            updated_at=datetime.fromtimestamp(skill_file.stat().st_mtime, tz=ZoneInfo("UTC")).isoformat(),
        )

    def _read_skill_archive(self, archive_path: Path, source: str) -> dict[str, Any] | None:
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                skill_entry = next((name for name in archive.namelist() if name.endswith("/SKILL.md")), "")
                if not skill_entry:
                    return None
                content = archive.read(skill_entry).decode("utf-8")
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
            self.logger.warning("讀取技能壓縮檔失敗：%s", exc, exc_info=True)
            return None
        return self._build_skill_metadata(
            content=content,
            fallback_name=archive_path.stem,
            source=source,
            path=archive_path,
            updated_at=datetime.fromtimestamp(archive_path.stat().st_mtime, tz=ZoneInfo("UTC")).isoformat(),
            entry_path=skill_entry,
        )

    def _build_skill_metadata(
        self,
        *,
        content: str,
        fallback_name: str,
        source: str,
        path: Path,
        updated_at: str,
        entry_path: str | None = None,
    ) -> dict[str, Any]:
        name = fallback_name
        description = ""
        frontmatter: dict[str, Any] = {}
        if content.startswith("---"):
            frontmatter_text, _ = self._split_frontmatter(content)
            if frontmatter_text is not None:
                try:
                    frontmatter = yaml.safe_load(frontmatter_text) or {}
                except yaml.YAMLError as exc:
                    self.logger.warning("解析技能 YAML frontmatter 失敗：%s", exc, exc_info=True)
                    frontmatter = {}
                name = frontmatter.get("name", name)
                description = frontmatter.get("description", "")
        metadata = {
            "name": name,
            "description": description,
            "path": str(path),
            "source": source,
            "updated_at": updated_at,
            "frontmatter": frontmatter,
        }
        if entry_path:
            metadata["entry_path"] = entry_path
        return metadata

    def _split_frontmatter(self, content: str) -> tuple[str | None, str]:
        if not content.startswith("---"):
            return None, content
        lines = content.splitlines()
        if len(lines) < 3:
            return None, content
        try:
            end_index = lines[1:].index("---") + 1
        except ValueError:
            return None, content
        frontmatter_text = "\n".join(lines[1:end_index])
        body = "\n".join(lines[end_index + 1 :])
        return frontmatter_text, body

    def _list_skill_references(self, skill_dir: Path) -> list[dict[str, Any]]:
        references_dir = skill_dir / "references"
        if not references_dir.exists():
            return []
        entries: list[dict[str, Any]] = []
        for path in sorted(references_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(references_dir).as_posix()
            entries.append({"path": rel_path, "size": path.stat().st_size})
            if len(entries) >= 200:
                break
        return entries

    def _list_skill_references_archive(self, archive: zipfile.ZipFile, skill_entry_path: str) -> list[dict[str, Any]]:
        skill_root = skill_entry_path.rsplit("/", 1)[0]
        references_prefix = f"{skill_root}/references/"
        entries: list[dict[str, Any]] = []
        for name in sorted(archive.namelist()):
            if not name.startswith(references_prefix) or name.endswith("/"):
                continue
            rel_path = name.removeprefix(references_prefix)
            info = archive.getinfo(name)
            entries.append({"path": rel_path, "size": info.file_size})
            if len(entries) >= 200:
                break
        return entries

    def _skills_index_path(self) -> Path:
        return self.cache_dir / "skills" / "index.json"

    def _normalize_skill_names(self, names: list[str] | None) -> list[str]:
        if not names:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for name in names:
            trimmed = str(name).strip()
            if not trimmed or trimmed in seen:
                continue
            normalized.append(trimmed)
            seen.add(trimmed)
        return normalized

    def _load_skills(
        self,
        names: list[str],
        project_path: Path | None,
        *,
        ignore_missing: bool,
    ) -> list[dict[str, Any]]:
        skills: list[dict[str, Any]] = []
        for name in names:
            try:
                skills.append(self.load_skill(name, project_path=project_path))
            except KeyError:
                if ignore_missing:
                    continue
                raise
        return skills

    def _format_skill_context(self, skills: list[dict[str, Any]]) -> str:
        return build_system_prefix_injection(skills)

    def _collect_skill_names(
        self,
        config: dict[str, Any],
        skill_names: list[str] | None,
    ) -> list[str]:
        if skill_names:
            return self._normalize_skill_names(skill_names)
        configured = config.get("skills", {}).get("selected", [])
        if isinstance(configured, list):
            return self._normalize_skill_names([str(name) for name in configured])
        return []

    def _resolve_skill_context(
        self,
        prompt: str,
        project_path: Path | None,
        *,
        config: dict[str, Any] | None = None,
        skill_names: list[str] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        config = config or self.load_config(project_path)
        selected = self._collect_skill_names(config, skill_names)
        indexed_skills = self.scan_skills(project_path) if project_path else self.list_skills() or self.scan_skills()
        by_name = {str(item.get("name")): item for item in indexed_skills}

        resolved_names: list[str] = []
        resolved_names.extend(selected)
        if prompt.startswith("/"):
            prompt_skill = prompt.split()[0].lstrip("/")
            if prompt_skill:
                resolved_names.append(prompt_skill)

        deduped_names: list[str] = []
        seen: set[str] = set()
        for name in resolved_names:
            if name in seen:
                continue
            seen.add(name)
            deduped_names.append(name)

        skills: list[dict[str, Any]] = []
        project_id = self.resolve_project_identity(project_path)[0] if project_path else None
        for name in deduped_names:
            if name not in by_name:
                continue
            skills.append(
                self.load_skill(
                    name,
                    project_path=project_path,
                    stream_handler=stream_handler,
                    project_id=project_id,
                    run_id=run_id,
                    node_id=node_id,
                    thread_id=thread_id,
                    request_id=request_id,
                )
            )
        if not skills:
            return ""
        return self._format_skill_context(skills)

    def _build_system_message(
        self,
        prompt: str,
        project_path: Path | None,
        *,
        config: dict[str, Any],
        skill_names: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        system_message = default_system_prompt()
        tool_context = self._first_party_tool_context(project_path, allowed_tools=allowed_tools)
        if tool_context:
            system_message = f"{system_message}\n\n{tool_context}"
        skill_context = self._resolve_skill_context(
            prompt,
            project_path,
            config=config,
            skill_names=skill_names,
            stream_handler=stream_handler,
            run_id=run_id,
            node_id=node_id,
            thread_id=thread_id,
            request_id=request_id,
        )
        if skill_context:
            system_message = f"{system_message}\n\n{skill_context}"
        return system_message

    def _first_party_tool_context(self, project_path: Path | None, *, allowed_tools: list[str] | None = None) -> str:
        from .tooling.builtin import build_registry

        workspace_root = project_path or Path.cwd()
        registry = build_registry(workspace_root)
        specs = sorted(registry.list_specs(), key=lambda spec: spec.name)
        if allowed_tools is not None:
            allowlist = {str(name).strip() for name in allowed_tools if str(name).strip()}
            specs = [spec for spec in specs if spec.name in allowlist]
        if not specs:
            return ""
        lines = ["## First-party tools"]
        for spec in specs:
            schema = json.dumps(spec.input_schema or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            lines.append(
                f"- {spec.name}｜risk={spec.risk}｜description={spec.description}｜input_schema={schema}"
            )
        return "\n".join(lines)

    def _prepare_session_path(self, project_path: Path | None, session_id: str) -> Path:
        if not project_path:
            raise ValueError("執行任務需要指定專案")
        sessions_dir = project_path / "sessions"
        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立 sessions 目錄失敗：%s", exc, exc_info=True)
            raise
        return sessions_dir / f"{session_id}.jsonl"

    def _prepare_memory_dir(self, project_path: Path) -> Path:
        memory_dir = project_path / "memory"
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立 memory 目錄失敗：%s", exc, exc_info=True)
            raise
        return memory_dir

    def _entity_aliases_path(self, memory_dir: Path) -> Path:
        return memory_dir / "entity_aliases.json"

    def _normalize_alias_key(self, name: str) -> str:
        normalized = unicodedata.normalize("NFKC", name).strip().lower()
        normalized = re.sub(r"\s+", "", normalized)
        return normalized

    def _slugify_entity_name(self, name: str) -> str:
        normalized = unicodedata.normalize("NFKC", name).strip().lower()
        normalized = re.sub(r"\s+", "_", normalized)
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "_", normalized)
        normalized = normalized.strip("_")
        return normalized or "unknown"

    def _load_entity_aliases(self, memory_dir: Path) -> dict[str, Any]:
        aliases_path = self._entity_aliases_path(memory_dir)
        if not aliases_path.exists():
            return {"entities": {}, "aliases": {}}
        try:
            payload = json.loads(aliases_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 entity aliases 失敗：%s", exc, exc_info=True)
            raise
        if not isinstance(payload, dict):
            return {"entities": {}, "aliases": {}}
        payload.setdefault("entities", {})
        payload.setdefault("aliases", {})
        return payload

    def _save_entity_aliases(self, memory_dir: Path, payload: dict[str, Any]) -> None:
        aliases_path = self._entity_aliases_path(memory_dir)
        try:
            self._atomic_write_text(
                aliases_path,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        except OSError as exc:
            self.logger.error("寫入 entity aliases 失敗：%s", exc, exc_info=True)
            raise

    def _build_canonical_id(self, entity_type: str, name: str, entities: dict[str, Any]) -> str:
        base_slug = self._slugify_entity_name(name)
        canonical_id = f"{entity_type}:{base_slug}"
        if canonical_id in entities and entities[canonical_id].get("name") != name:
            digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:6]
            canonical_id = f"{canonical_id}-{digest}"
        return canonical_id

    def _ensure_entity_alias(
        self,
        entities: dict[str, Any],
        canonical_id: str,
        alias: str,
        entity_type: str | None = None,
    ) -> None:
        entry = entities.setdefault(
            canonical_id,
            {
                "canonical_id": canonical_id,
                "name": alias,
                "type": entity_type or "",
                "aliases": [],
                "merged_ids": [],
            },
        )
        if entity_type and not entry.get("type"):
            entry["type"] = entity_type
        if alias and not entry.get("name"):
            entry["name"] = alias
        alias_list = entry.setdefault("aliases", [])
        if alias not in alias_list:
            alias_list.append(alias)

    def _find_alias_merge_candidate(
        self,
        name: str,
        entity_type: str,
        entities: dict[str, Any],
    ) -> str | None:
        if entity_type != "person":
            return None
        if len(name) > 3:
            return None
        candidates: list[tuple[int, str]] = []
        for canonical_id, entry in entities.items():
            if entry.get("type") != "person":
                continue
            known_name = str(entry.get("name") or "")
            aliases = entry.get("aliases") or []
            if name and (known_name.endswith(name) or name in known_name):
                candidates.append((len(known_name), canonical_id))
                continue
            if any(name and (alias.endswith(name) or name in alias) for alias in aliases):
                candidates.append((len(known_name), canonical_id))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    def _resolve_entity_canonical_id(
        self,
        name: str,
        entity_type: str,
        alias_state: dict[str, Any],
    ) -> str:
        alias_key = self._normalize_alias_key(name)
        aliases = alias_state.setdefault("aliases", {})
        entities = alias_state.setdefault("entities", {})
        if alias_key in aliases:
            canonical_id = aliases[alias_key]
            self._ensure_entity_alias(entities, canonical_id, name, entity_type)
            return canonical_id
        candidate_id = self._find_alias_merge_candidate(name, entity_type, entities)
        if candidate_id:
            aliases[alias_key] = candidate_id
            self._ensure_entity_alias(entities, candidate_id, name, entity_type)
            return candidate_id
        canonical_id = self._build_canonical_id(entity_type, name, entities)
        aliases[alias_key] = canonical_id
        entities.setdefault(
            canonical_id,
            {
                "canonical_id": canonical_id,
                "name": name,
                "type": entity_type,
                "aliases": [name],
                "merged_ids": [],
            },
        )
        if entity_type == "person":
            for derived in self._derive_person_aliases(name):
                derived_key = self._normalize_alias_key(derived)
                if derived_key not in aliases:
                    aliases[derived_key] = canonical_id
                    self._ensure_entity_alias(entities, canonical_id, derived, entity_type)
        return canonical_id

    def _derive_person_aliases(self, name: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", name).strip()
        if len(normalized) < 3:
            return []
        alias = normalized[1:]
        return [alias] if alias and alias != normalized else []

    def _vectorize_text(self, text: str) -> Counter[str]:
        cleaned = re.sub(r"\s+", "", text.lower())
        if len(cleaned) < 2:
            return Counter({cleaned: 1}) if cleaned else Counter()
        grams = [cleaned[index : index + 2] for index in range(len(cleaned) - 1)]
        return Counter(grams)

    def _cosine_similarity(self, left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0
        intersection = set(left) & set(right)
        numerator = sum(left[token] * right[token] for token in intersection)
        left_norm = sum(value * value for value in left.values()) ** 0.5
        right_norm = sum(value * value for value in right.values()) ** 0.5
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def search_memory(
        self,
        project_path: Path,
        query: str,
        time_range: dict[str, str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not project_path:
            raise ValueError("執行 memory search 需要指定專案")
        memory_dir = self._prepare_memory_dir(project_path)
        normalized_path = memory_dir / "normalized.jsonl"
        tags_path = memory_dir / "tags.jsonl"
        if not normalized_path.exists() or not tags_path.exists():
            raise FileNotFoundError("找不到 memory normalized/tags 檔案")
        tag_map: dict[str, dict[str, Any]] = {}
        try:
            with tags_path.open("r", encoding="utf-8") as tags_handle:
                for line in tags_handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    record = json.loads(payload)
                    chunk_id = str(record.get("chunk_id") or "")
                    if not chunk_id:
                        continue
                    tag_map[chunk_id] = record
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 memory tags 失敗：%s", exc, exc_info=True)
            raise
        query_vector = self._vectorize_text(query)
        candidates: list[dict[str, Any]] = []
        try:
            with normalized_path.open("r", encoding="utf-8") as normalized_handle:
                for line in normalized_handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    normalized = json.loads(payload)
                    if time_range and not self._within_time_range(normalized, time_range):
                        continue
                    chunk_id = str(normalized.get("chunk_id") or "")
                    tags = tag_map.get(chunk_id, {})
                    embedding_text = str(tags.get("embedding_text") or normalized.get("text") or "")
                    score = self._cosine_similarity(query_vector, self._vectorize_text(embedding_text))
                    candidates.append(
                        {
                            "chunk_id": chunk_id,
                            "score": score,
                            "text": normalized.get("text"),
                            "created_at": normalized.get("created_at"),
                            "source_path": normalized.get("source_path"),
                            "time": normalized.get("time"),
                        }
                    )
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 memory normalized 失敗：%s", exc, exc_info=True)
            raise
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[: max(top_k, 1)]

    def _within_time_range(self, normalized: dict[str, Any], time_range: dict[str, str]) -> bool:
        start_raw = time_range.get("start") or time_range.get("from")
        end_raw = time_range.get("end") or time_range.get("to")
        if not start_raw and not end_raw:
            return True
        try:
            start_date = date.fromisoformat(start_raw) if start_raw else None
            end_date = date.fromisoformat(end_raw) if end_raw else None
        except ValueError:
            self.logger.warning("time.range 格式錯誤，略過時間過濾。")
            return True
        created_at = str(normalized.get("created_at") or "")
        created = self._parse_chunk_created_at(created_at)
        created_date = created.date() if created else None
        mention_dates: list[date] = []
        for mention in normalized.get("time", {}).get("mentions", []):
            resolved = mention.get("resolved_date")
            if not resolved:
                continue
            try:
                mention_dates.append(date.fromisoformat(resolved))
            except ValueError:
                continue
        def in_range(target: date | None) -> bool:
            if target is None:
                return False
            if start_date and target < start_date:
                return False
            if end_date and target > end_date:
                return False
            return True
        if in_range(created_date):
            return True
        return any(in_range(item) for item in mention_dates)

    def _sanitize_tag_value(self, value: str) -> str:
        sanitized = value.replace("\n", " ").replace("\r", " ")
        sanitized = sanitized.replace("```", "").replace("`", "")
        sanitized = sanitized.replace("<", "").replace(">", "")
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def _build_tags_markdown(
        self,
        normalized: dict[str, Any],
        entity_mentions: list[dict[str, Any]],
    ) -> str:
        lines = ["## AMON_MEMORY_TAGS"]
        time_mentions = normalized.get("time", {}).get("mentions", [])
        geo_mentions = normalized.get("geo", {}).get("mentions", [])

        if time_mentions:
            for mention in time_mentions:
                raw = self._sanitize_tag_value(str(mention.get("raw") or ""))
                resolved = self._sanitize_tag_value(str(mention.get("resolved_date") or ""))
                lines.append(f'- time_mentions: raw="{raw}", resolved_date="{resolved}"')
        else:
            lines.append("- time_mentions: none")

        if geo_mentions:
            for mention in geo_mentions:
                raw = self._sanitize_tag_value(str(mention.get("raw") or ""))
                geocode = self._sanitize_tag_value(str(mention.get("geocode_id") or ""))
                normalized_name = self._sanitize_tag_value(str(mention.get("normalized_name") or ""))
                lines.append(
                    f'- geo_mentions: raw="{raw}", geocode_id="{geocode}", normalized_name="{normalized_name}"'
                )
        else:
            lines.append("- geo_mentions: none")

        if entity_mentions:
            for mention in entity_mentions:
                pronoun = self._sanitize_tag_value(str(mention.get("pronoun") or ""))
                resolved_to = self._sanitize_tag_value(str(mention.get("resolved_to") or ""))
                resolved_to_canonical = self._sanitize_tag_value(str(mention.get("resolved_to_canonical_id") or ""))
                name = self._sanitize_tag_value(str(mention.get("name") or ""))
                canonical_id = self._sanitize_tag_value(str(mention.get("canonical_id") or ""))
                entity_type = self._sanitize_tag_value(str(mention.get("entity_type") or ""))
                confidence = mention.get("confidence")
                needs_review = mention.get("needs_review")
                rule = self._sanitize_tag_value(str(mention.get("rule") or ""))
                lines.append(
                    "- entity_mentions: "
                    f'pronoun="{pronoun}", resolved_to="{resolved_to}", resolved_to_canonical_id="{resolved_to_canonical}", '
                    f'name="{name}", canonical_id="{canonical_id}", entity_type="{entity_type}", '
                    f'confidence="{confidence}", needs_review="{needs_review}", rule="{rule}"'
                )
        else:
            lines.append("- entity_mentions: none")

        return "\n".join(lines)

    def generate_memory_tags(self, project_path: Path) -> int:
        if not project_path:
            raise ValueError("執行 memory tags 需要指定專案")
        memory_dir = self._prepare_memory_dir(project_path)
        normalized_path = memory_dir / "normalized.jsonl"
        entities_path = memory_dir / "entities.jsonl"
        tags_path = memory_dir / "tags.jsonl"
        if not normalized_path.exists():
            self.logger.error("找不到 memory normalized 檔案：%s", normalized_path)
            raise FileNotFoundError(f"找不到 memory normalized 檔案：{normalized_path}")
        entity_map: dict[str, list[dict[str, Any]]] = {}
        if entities_path.exists():
            try:
                with entities_path.open("r", encoding="utf-8") as entity_handle:
                    for line in entity_handle:
                        payload = line.strip()
                        if not payload:
                            continue
                        try:
                            record = json.loads(payload)
                        except json.JSONDecodeError as exc:
                            self.logger.error("解析 memory entities 失敗：%s", exc, exc_info=True)
                            raise
                        chunk_id = str(record.get("chunk_id") or "")
                        if not chunk_id:
                            continue
                        mention = record.get("mention") or {}
                        entity_map.setdefault(chunk_id, []).append(mention)
            except OSError as exc:
                self.logger.error("讀取 memory entities 失敗：%s", exc, exc_info=True)
                raise
        tag_count = 0
        try:
            with (
                normalized_path.open("r", encoding="utf-8") as normalized_handle,
                tags_path.open("w", encoding="utf-8") as tags_handle,
            ):
                for line in normalized_handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    try:
                        normalized = json.loads(payload)
                    except json.JSONDecodeError as exc:
                        self.logger.error("解析 memory normalized 失敗：%s", exc, exc_info=True)
                        raise
                    chunk_id = str(normalized.get("chunk_id") or "")
                    text = str(normalized.get("text") or "")
                    entity_mentions = entity_map.get(chunk_id, [])
                    tags_markdown = self._build_tags_markdown(normalized, entity_mentions)
                    embedding_text = f"{text}\n\n{tags_markdown}"
                    record = {
                        "chunk_id": chunk_id,
                        "tags_markdown": tags_markdown,
                        "embedding_text": embedding_text,
                    }
                    tags_handle.write(json.dumps(record, ensure_ascii=False))
                    tags_handle.write("\n")
                    tag_count += 1
        except OSError as exc:
            self.logger.error("寫入 memory tags 失敗：%s", exc, exc_info=True)
            raise
        return tag_count

    def _parse_chunk_created_at(self, created_at: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(created_at)
        except ValueError as exc:
            self.logger.warning("解析 created_at 失敗：%s", exc, exc_info=True)
            return None
        taipei_tz = ZoneInfo("Asia/Taipei")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=taipei_tz)
        return parsed.astimezone(taipei_tz)

    def _resolve_relative_date(self, raw: str, base_date: date | None) -> str | None:
        if base_date is None:
            return None
        offsets = {
            "昨天": -1,
            "明天": 1,
            "今天": 0,
            "前天": -2,
            "後天": 2,
        }
        if raw in offsets:
            return (base_date + timedelta(days=offsets[raw])).isoformat()
        if raw.startswith("下週"):
            weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
            weekday_char = raw.replace("下週", "", 1)
            target_weekday = weekday_map.get(weekday_char)
            if target_weekday is None:
                return None
            days_until_next_monday = 7 - base_date.weekday()
            resolved = base_date + timedelta(days=days_until_next_monday + target_weekday)
            return resolved.isoformat()
        return None

    def _extract_time_mentions(self, text: str, created_at: str) -> list[dict[str, Any]]:
        base_datetime = self._parse_chunk_created_at(created_at)
        base_date = base_datetime.date() if base_datetime else None
        mentions: list[dict[str, Any]] = []
        patterns = [
            r"昨天|明天|今天|前天|後天",
            r"下週[一二三四五六日天]",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                raw = match.group(0)
                resolved_date = self._resolve_relative_date(raw, base_date)
                if resolved_date:
                    mentions.append(
                        {
                            "raw": raw,
                            "resolved_date": resolved_date,
                            "confidence": 1,
                            "needs_review": False,
                        }
                    )
                else:
                    mentions.append({"raw": raw, "confidence": 0, "needs_review": True})
        return mentions

    def _extract_geo_mentions(self, text: str) -> list[dict[str, Any]]:
        mapping = {
            "台北": {
                "normalized_name": "Taipei City, Taiwan",
                "geocode_id": "tw-tpe",
                "lat": 25.033,
                "lon": 121.5654,
            },
            "臺北": {
                "normalized_name": "Taipei City, Taiwan",
                "geocode_id": "tw-tpe",
                "lat": 25.033,
                "lon": 121.5654,
            },
            "Taipei": {
                "normalized_name": "Taipei City, Taiwan",
                "geocode_id": "tw-tpe",
                "lat": 25.033,
                "lon": 121.5654,
            },
        }
        mentions: list[dict[str, Any]] = []
        for alias, info in mapping.items():
            for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
                mentions.append(
                    {
                        "raw": match.group(0),
                        "normalized_name": info["normalized_name"],
                        "geocode_id": info["geocode_id"],
                        "lat": info["lat"],
                        "lon": info["lon"],
                        "confidence": 1,
                        "needs_review": False,
                    }
                )
        return mentions

    def _extract_explicit_entities(self, text: str) -> list[dict[str, Any]]:
        mentions: list[dict[str, Any]] = []
        surname_list = (
            "王李張劉陳楊黃趙吳周徐孫馬朱胡郭何高林羅鄭梁謝宋唐許韓馮"
            "鄧曹彭曾蕭田董袁潘於蔣蔡余杜葉程蘇魏呂丁任沈姚盧姜崔鐘譚"
            "陸汪范金石廖賴邵熊孟秦白江閻薛尹段雷侯龍史陶黎賀顧毛郝龔"
            "邱萬錢嚴覃武戴莫孔向湯"
        )
        person_pattern = rf"(?P<name>[{surname_list}][\u4e00-\u9fff]{{1,2}})"
        org_pattern = r"(?P<name>[\u4e00-\u9fff]{2,12}(公司|企業|機構|組織|基金會|工作室|學校|大學|協會))"
        for match in re.finditer(person_pattern, text):
            mentions.append(
                {
                    "name": match.group("name"),
                    "type": "person",
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        for match in re.finditer(org_pattern, text):
            mentions.append(
                {
                    "name": match.group("name"),
                    "type": "org",
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return sorted(mentions, key=lambda item: item["start"])

    def _extract_pronoun_mentions(self, text: str) -> list[dict[str, Any]]:
        pronouns = ["他們", "她們", "他", "她", "這家公司", "該公司", "這個公司", "該企業", "該組織"]
        pattern = "|".join(re.escape(pronoun) for pronoun in pronouns)
        mentions: list[dict[str, Any]] = []
        for match in re.finditer(pattern, text):
            mentions.append(
                {
                    "pronoun": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return mentions

    def _resolve_pronouns_in_text(
        self,
        text: str,
        last_entity: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        mentions: list[dict[str, Any]] = []
        explicit_entities = self._extract_explicit_entities(text)
        pronouns = self._extract_pronoun_mentions(text)
        events: list[dict[str, Any]] = []
        for entity in explicit_entities:
            event = dict(entity)
            event["kind"] = "entity"
            events.append(event)
        for pronoun in pronouns:
            event = dict(pronoun)
            event["kind"] = "pronoun"
            events.append(event)
        for event in sorted(events, key=lambda item: item["start"]):
            if event["kind"] == "entity":
                last_entity = {"name": event["name"], "type": event["type"]}
                continue
            resolved_to = last_entity.get("name") if last_entity else None
            entity_type = last_entity.get("type") if last_entity else None
            mentions.append(
                {
                    "pronoun": event["pronoun"],
                    "resolved_to": resolved_to,
                    "entity_type": entity_type,
                    "confidence": 0.6 if resolved_to else 0.0,
                    "needs_review": resolved_to is None,
                    "rule": "session_last_explicit",
                }
            )
        return mentions, last_entity

    def ingest_session_memory(
        self,
        project_path: Path,
        session_id: str,
        project_id: str | None = None,
        lang: str = "zh-TW",
    ) -> int:
        if not project_path:
            raise ValueError("執行 memory ingest 需要指定專案")
        source_path = project_path / "sessions" / f"{session_id}.jsonl"
        if not source_path.exists():
            self.logger.error("找不到 sessions 檔案：%s", source_path)
            raise FileNotFoundError(f"找不到 sessions 檔案：{source_path}")
        memory_dir = self._prepare_memory_dir(project_path)
        chunks_path = memory_dir / "chunks.jsonl"
        source_rel_path = f"sessions/{session_id}.jsonl"
        chunk_count = 0
        try:
            with source_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError as exc:
                        self.logger.error("解析 session JSONL 失敗：%s", exc, exc_info=True)
                        raise
                    event_type = str(event.get("event") or "")
                    if event_type not in {"prompt", "final"}:
                        continue
                    text = str(event.get("content") or "")
                    chunk = {
                        "chunk_id": uuid.uuid4().hex,
                        "project_id": project_id or self.resolve_project_identity(project_path)[0],
                        "session_id": session_id,
                        "source_path": source_rel_path,
                        "text": text,
                        "created_at": self._now(),
                        "lang": lang,
                    }
                    with chunks_path.open("a", encoding="utf-8") as chunk_handle:
                        chunk_handle.write(json.dumps(chunk, ensure_ascii=False))
                        chunk_handle.write("\n")
                    chunk_count += 1
        except OSError as exc:
            self.logger.error("寫入 memory chunk 失敗：%s", exc, exc_info=True)
            raise
        try:
            self.run_memory_ingest_pipeline(project_path, batch_size=50)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Memory ingest pipeline 失敗：%s", exc, exc_info=True)
            raise
        return chunk_count

    def run_memory_ingest_pipeline(
        self,
        project_path: Path,
        *,
        batch_size: int = 50,
        max_queue_size: int = 1000,
    ) -> dict[str, Any]:
        if not project_path:
            raise ValueError("執行 memory pipeline 需要指定專案")
        memory_dir = self._prepare_memory_dir(project_path)
        chunks_path = memory_dir / "chunks.jsonl"
        if not chunks_path.exists():
            self.logger.error("找不到 memory chunks 檔案：%s", chunks_path)
            raise FileNotFoundError(f"找不到 memory chunks 檔案：{chunks_path}")
        state = self._load_memory_ingest_state(memory_dir)
        project_id = self.resolve_project_identity(project_path)[0] or project_path.name
        pending_chunks = self._count_pending_chunks(chunks_path, state.get("stages", {}).get("normalized", {}))
        if pending_chunks > max_queue_size:
            emit_event(
                {
                    "type": "system.backpressure",
                    "scope": "system",
                    "project_id": project_id,
                    "actor": "system",
                    "payload": {
                        "pipeline": "memory_ingest",
                        "pending_chunks": pending_chunks,
                        "max_queue_size": max_queue_size,
                    },
                    "risk": "low",
                }
            )
            return {"status": "backpressure", "pending_chunks": pending_chunks}

        processed: dict[str, int] = {}
        processed["normalized"] = self._process_memory_normalized(project_path, memory_dir, state, batch_size)
        processed["entities"] = self._process_memory_entities(project_path, memory_dir, state, batch_size)
        processed["tags"] = self._process_memory_tags(project_path, memory_dir, state, batch_size)
        processed["embed"] = self._process_memory_embed(project_path, memory_dir, state, batch_size)
        processed["index"] = self._process_memory_index(project_path, memory_dir, state, batch_size)
        self._save_memory_ingest_state(memory_dir, state)
        return {"status": "ok", "processed": processed, "pending_chunks": pending_chunks}

    def _process_memory_normalized(
        self,
        project_path: Path,
        memory_dir: Path,
        state: dict[str, Any],
        batch_size: int,
    ) -> int:
        chunks_path = memory_dir / "chunks.jsonl"
        normalized_path = memory_dir / "normalized.jsonl"
        stages = state.setdefault("stages", {})
        cursor = stages.setdefault("normalized", {"last_chunk_id": None, "processed": 0})
        last_chunk_id = cursor.get("last_chunk_id")
        processed = 0
        try:
            with chunks_path.open("r", encoding="utf-8") as handle, normalized_path.open("a", encoding="utf-8") as out_handle:
                seen_last = last_chunk_id is None
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    chunk = json.loads(payload)
                    chunk_id = str(chunk.get("chunk_id") or "")
                    if not seen_last:
                        if chunk_id == last_chunk_id:
                            seen_last = True
                        continue
                    text = str(chunk.get("text") or "")
                    created_at = str(chunk.get("created_at") or "")
                    mentions = self._extract_time_mentions(text, created_at)
                    geo_mentions = self._extract_geo_mentions(text)
                    normalized = dict(chunk)
                    normalized["time"] = {"mentions": mentions}
                    normalized["geo"] = {"mentions": geo_mentions}
                    out_handle.write(json.dumps(normalized, ensure_ascii=False))
                    out_handle.write("\n")
                    cursor["last_chunk_id"] = chunk_id
                    cursor["processed"] = int(cursor.get("processed", 0)) + 1
                    processed += 1
                    if processed >= batch_size:
                        break
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("寫入 memory normalized 失敗：%s", exc, exc_info=True)
            raise
        return processed

    def _process_memory_entities(
        self,
        project_path: Path,
        memory_dir: Path,
        state: dict[str, Any],
        batch_size: int,
    ) -> int:
        lock_path = memory_dir / ".aliases.lock"
        with file_lock(lock_path):
            return self._process_memory_entities_locked(project_path, memory_dir, state, batch_size)

    def _process_memory_entities_locked(
        self,
        project_path: Path,
        memory_dir: Path,
        state: dict[str, Any],
        batch_size: int,
    ) -> int:
        normalized_path = memory_dir / "normalized.jsonl"
        entities_path = memory_dir / "entities.jsonl"
        stages = state.setdefault("stages", {})
        cursor = stages.setdefault("entities", {"last_chunk_id": None, "processed": 0})
        last_chunk_id = cursor.get("last_chunk_id")
        processed = 0
        session_last_entity = state.setdefault("session_last_entity", {})
        alias_state = self._load_entity_aliases(memory_dir)
        try:
            with normalized_path.open("r", encoding="utf-8") as handle, entities_path.open("a", encoding="utf-8") as out_handle:
                seen_last = last_chunk_id is None
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    normalized = json.loads(payload)
                    chunk_id = str(normalized.get("chunk_id") or "")
                    if not seen_last:
                        if chunk_id == last_chunk_id:
                            seen_last = True
                        continue
                    text = str(normalized.get("text") or "")
                    session_id = str(normalized.get("session_id") or "")
                    last_entity = session_last_entity.get(session_id)
                    pronoun_mentions, last_entity = self._resolve_pronouns_in_text(text, last_entity)
                    session_last_entity[session_id] = last_entity
                    explicit_entities = self._extract_explicit_entities(text)
                    for entity in explicit_entities:
                        name = str(entity.get("name") or "")
                        entity_type = str(entity.get("type") or "")
                        canonical_id = self._resolve_entity_canonical_id(name, entity_type, alias_state)
                        entity_record = {
                            "chunk_id": chunk_id,
                            "project_id": normalized.get("project_id"),
                            "session_id": session_id,
                            "source_path": normalized.get("source_path"),
                            "text": text,
                            "mention": {
                                "name": name,
                                "entity_type": entity_type,
                                "canonical_id": canonical_id,
                                "confidence": 1.0,
                                "needs_review": False,
                                "rule": "explicit_name",
                            },
                        }
                        out_handle.write(json.dumps(entity_record, ensure_ascii=False))
                        out_handle.write("\n")
                    for mention in pronoun_mentions:
                        resolved_to = mention.get("resolved_to")
                        entity_type = mention.get("entity_type") or ""
                        resolved_canonical_id = (
                            self._resolve_entity_canonical_id(str(resolved_to), entity_type, alias_state)
                            if resolved_to
                            else None
                        )
                        mention["resolved_to_canonical_id"] = resolved_canonical_id
                        entity_record = {
                            "chunk_id": chunk_id,
                            "project_id": normalized.get("project_id"),
                            "session_id": session_id,
                            "source_path": normalized.get("source_path"),
                            "text": text,
                            "mention": mention,
                        }
                        out_handle.write(json.dumps(entity_record, ensure_ascii=False))
                        out_handle.write("\n")
                    cursor["last_chunk_id"] = chunk_id
                    cursor["processed"] = int(cursor.get("processed", 0)) + 1
                    processed += 1
                    if processed >= batch_size:
                        break
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("寫入 memory entities 失敗：%s", exc, exc_info=True)
            raise
        self._save_entity_aliases(memory_dir, alias_state)
        return processed

    def _process_memory_tags(
        self,
        project_path: Path,
        memory_dir: Path,
        state: dict[str, Any],
        batch_size: int,
    ) -> int:
        normalized_path = memory_dir / "normalized.jsonl"
        entities_path = memory_dir / "entities.jsonl"
        tags_path = memory_dir / "tags.jsonl"
        stages = state.setdefault("stages", {})
        cursor = stages.setdefault("tags", {"last_chunk_id": None, "processed": 0})
        last_chunk_id = cursor.get("last_chunk_id")
        processed = 0
        entity_map = self._load_entity_mentions(entities_path)
        try:
            with normalized_path.open("r", encoding="utf-8") as handle, tags_path.open("a", encoding="utf-8") as tags_handle:
                seen_last = last_chunk_id is None
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    normalized = json.loads(payload)
                    chunk_id = str(normalized.get("chunk_id") or "")
                    if not seen_last:
                        if chunk_id == last_chunk_id:
                            seen_last = True
                        continue
                    text = str(normalized.get("text") or "")
                    entity_mentions = entity_map.get(chunk_id, [])
                    tags_markdown = self._build_tags_markdown(normalized, entity_mentions)
                    embedding_text = f"{text}\n\n{tags_markdown}"
                    record = {
                        "chunk_id": chunk_id,
                        "tags_markdown": tags_markdown,
                        "embedding_text": embedding_text,
                    }
                    tags_handle.write(json.dumps(record, ensure_ascii=False))
                    tags_handle.write("\n")
                    cursor["last_chunk_id"] = chunk_id
                    cursor["processed"] = int(cursor.get("processed", 0)) + 1
                    processed += 1
                    if processed >= batch_size:
                        break
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("寫入 memory tags 失敗：%s", exc, exc_info=True)
            raise
        return processed

    def _process_memory_embed(
        self,
        project_path: Path,
        memory_dir: Path,
        state: dict[str, Any],
        batch_size: int,
    ) -> int:
        tags_path = memory_dir / "tags.jsonl"
        embed_path = memory_dir / "embed.jsonl"
        stages = state.setdefault("stages", {})
        cursor = stages.setdefault("embed", {"last_chunk_id": None, "processed": 0})
        last_chunk_id = cursor.get("last_chunk_id")
        processed = 0
        try:
            with tags_path.open("r", encoding="utf-8") as handle, embed_path.open("a", encoding="utf-8") as embed_handle:
                seen_last = last_chunk_id is None
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    record = json.loads(payload)
                    chunk_id = str(record.get("chunk_id") or "")
                    if not seen_last:
                        if chunk_id == last_chunk_id:
                            seen_last = True
                        continue
                    embedding_text = str(record.get("embedding_text") or "")
                    vector = self._vectorize_text(embedding_text)
                    embed_handle.write(
                        json.dumps(
                            {
                                "chunk_id": chunk_id,
                                "embedding_text": embedding_text,
                                "vector": dict(vector),
                            },
                            ensure_ascii=False,
                        )
                    )
                    embed_handle.write("\n")
                    cursor["last_chunk_id"] = chunk_id
                    cursor["processed"] = int(cursor.get("processed", 0)) + 1
                    processed += 1
                    if processed >= batch_size:
                        break
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("寫入 memory embed 失敗：%s", exc, exc_info=True)
            raise
        return processed

    def _process_memory_index(
        self,
        project_path: Path,
        memory_dir: Path,
        state: dict[str, Any],
        batch_size: int,
    ) -> int:
        embed_path = memory_dir / "embed.jsonl"
        index_path = memory_dir / "index.jsonl"
        stages = state.setdefault("stages", {})
        cursor = stages.setdefault("index", {"last_chunk_id": None, "processed": 0})
        last_chunk_id = cursor.get("last_chunk_id")
        processed = 0
        try:
            with embed_path.open("r", encoding="utf-8") as handle, index_path.open("a", encoding="utf-8") as index_handle:
                seen_last = last_chunk_id is None
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    record = json.loads(payload)
                    chunk_id = str(record.get("chunk_id") or "")
                    if not seen_last:
                        if chunk_id == last_chunk_id:
                            seen_last = True
                        continue
                    index_handle.write(
                        json.dumps(
                            {
                                "chunk_id": chunk_id,
                                "vector": record.get("vector"),
                            },
                            ensure_ascii=False,
                        )
                    )
                    index_handle.write("\n")
                    cursor["last_chunk_id"] = chunk_id
                    cursor["processed"] = int(cursor.get("processed", 0)) + 1
                    processed += 1
                    if processed >= batch_size:
                        break
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("寫入 memory index 失敗：%s", exc, exc_info=True)
            raise
        return processed

    def _load_entity_mentions(self, entities_path: Path) -> dict[str, list[dict[str, Any]]]:
        if not entities_path.exists():
            return {}
        entity_map: dict[str, list[dict[str, Any]]] = {}
        try:
            with entities_path.open("r", encoding="utf-8") as entity_handle:
                for line in entity_handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    record = json.loads(payload)
                    chunk_id = str(record.get("chunk_id") or "")
                    if not chunk_id:
                        continue
                    mention = record.get("mention") or {}
                    entity_map.setdefault(chunk_id, []).append(mention)
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 memory entities 失敗：%s", exc, exc_info=True)
            raise
        return entity_map

    def _load_memory_ingest_state(self, memory_dir: Path) -> dict[str, Any]:
        state_path = memory_dir / "ingest_state.json"
        if not state_path.exists():
            return {"stages": {}, "session_last_entity": {}}
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 memory ingest state 失敗：%s", exc, exc_info=True)
            raise
        if not isinstance(payload, dict):
            return {"stages": {}, "session_last_entity": {}}
        payload.setdefault("stages", {})
        payload.setdefault("session_last_entity", {})
        return payload

    def _save_memory_ingest_state(self, memory_dir: Path, state: dict[str, Any]) -> None:
        state_path = memory_dir / "ingest_state.json"
        try:
            atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入 memory ingest state 失敗：%s", exc, exc_info=True)
            raise

    def _count_pending_chunks(self, chunks_path: Path, stage_state: dict[str, Any]) -> int:
        processed = int(stage_state.get("processed", 0))
        total = 0
        try:
            with chunks_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        total += 1
        except OSError as exc:
            self.logger.error("讀取 memory chunks 失敗：%s", exc, exc_info=True)
            raise
        return max(total - processed, 0)

    def normalize_memory_dates(self, project_path: Path) -> int:
        if not project_path:
            raise ValueError("執行 memory normalize 需要指定專案")
        memory_dir = self._prepare_memory_dir(project_path)
        chunks_path = memory_dir / "chunks.jsonl"
        normalized_path = memory_dir / "normalized.jsonl"
        entities_path = memory_dir / "entities.jsonl"
        if not chunks_path.exists():
            self.logger.error("找不到 memory chunks 檔案：%s", chunks_path)
            raise FileNotFoundError(f"找不到 memory chunks 檔案：{chunks_path}")
        normalized_count = 0
        session_last_entity: dict[str, dict[str, Any] | None] = {}
        alias_state = self._load_entity_aliases(memory_dir)
        try:
            with (
                chunks_path.open("r", encoding="utf-8") as handle,
                normalized_path.open("w", encoding="utf-8") as out_handle,
                entities_path.open("w", encoding="utf-8") as entity_handle,
            ):
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError as exc:
                        self.logger.error("解析 memory chunk 失敗：%s", exc, exc_info=True)
                        raise
                    text = str(chunk.get("text") or "")
                    created_at = str(chunk.get("created_at") or "")
                    mentions = self._extract_time_mentions(text, created_at)
                    geo_mentions = self._extract_geo_mentions(text)
                    session_id = str(chunk.get("session_id") or "")
                    last_entity = session_last_entity.get(session_id)
                    pronoun_mentions, last_entity = self._resolve_pronouns_in_text(text, last_entity)
                    session_last_entity[session_id] = last_entity
                    explicit_entities = self._extract_explicit_entities(text)
                    normalized = dict(chunk)
                    normalized["time"] = {"mentions": mentions}
                    normalized["geo"] = {"mentions": geo_mentions}
                    out_handle.write(json.dumps(normalized, ensure_ascii=False))
                    out_handle.write("\n")
                    for entity in explicit_entities:
                        name = str(entity.get("name") or "")
                        entity_type = str(entity.get("type") or "")
                        canonical_id = self._resolve_entity_canonical_id(name, entity_type, alias_state)
                        entity_record = {
                            "chunk_id": chunk.get("chunk_id"),
                            "project_id": chunk.get("project_id"),
                            "session_id": session_id,
                            "source_path": chunk.get("source_path"),
                            "text": text,
                            "mention": {
                                "name": name,
                                "entity_type": entity_type,
                                "canonical_id": canonical_id,
                                "confidence": 1.0,
                                "needs_review": False,
                                "rule": "explicit_name",
                            },
                        }
                        entity_handle.write(json.dumps(entity_record, ensure_ascii=False))
                        entity_handle.write("\n")
                    for mention in pronoun_mentions:
                        resolved_to = mention.get("resolved_to")
                        entity_type = mention.get("entity_type") or ""
                        resolved_canonical_id = (
                            self._resolve_entity_canonical_id(str(resolved_to), entity_type, alias_state)
                            if resolved_to
                            else None
                        )
                        mention["resolved_to_canonical_id"] = resolved_canonical_id
                        entity_record = {
                            "chunk_id": chunk.get("chunk_id"),
                            "project_id": chunk.get("project_id"),
                            "session_id": session_id,
                            "source_path": chunk.get("source_path"),
                            "text": text,
                            "mention": mention,
                        }
                        entity_handle.write(json.dumps(entity_record, ensure_ascii=False))
                        entity_handle.write("\n")
                    normalized_count += 1
        except OSError as exc:
            self.logger.error("寫入 memory normalized 失敗：%s", exc, exc_info=True)
            raise
        self._save_entity_aliases(memory_dir, alias_state)
        try:
            self.generate_memory_tags(project_path)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("產生 memory tags 失敗：%s", exc, exc_info=True)
            raise
        return normalized_count

    @contextmanager
    def _project_lock(self, project_path: Path, action: str) -> Any:
        lock_path = self._acquire_project_lock(project_path, action)
        try:
            yield
        finally:
            self._release_project_lock(lock_path)

    def _acquire_project_lock(self, project_path: Path, action: str) -> Path:
        locks_dir = project_path / ".amon" / "locks"
        try:
            locks_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立鎖定目錄失敗：%s", exc, exc_info=True)
            raise
        lock_path = locks_dir / "project.lock"
        payload = {"pid": os.getpid(), "action": action, "created_at": self._now()}
        if lock_path.exists():
            if self._is_stale_project_lock(lock_path):
                try:
                    lock_path.unlink()
                except OSError as exc:
                    self.logger.error("清除過期鎖定失敗：%s", exc, exc_info=True)
                    raise
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
        except FileExistsError:
            detail = ""
            try:
                detail = lock_path.read_text(encoding="utf-8")
            except OSError:
                detail = "（無法讀取鎖定內容）"
            raise RuntimeError(f"專案正在執行其他指令，請稍後再試。鎖定資訊：{detail}")
        except OSError as exc:
            self.logger.error("建立鎖定失敗：%s", exc, exc_info=True)
            raise
        return lock_path

    def _release_project_lock(self, lock_path: Path) -> None:
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError as exc:
            self.logger.error("釋放鎖定失敗：%s", exc, exc_info=True)
            raise

    def _is_stale_project_lock(self, lock_path: Path) -> bool:
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        pid = payload.get("pid")
        created_at = payload.get("created_at")
        if isinstance(pid, int) and self._is_pid_alive(pid):
            if isinstance(created_at, str):
                try:
                    created_time = datetime.fromisoformat(created_at)
                except ValueError:
                    created_time = None
                if created_time:
                    age = datetime.now(created_time.tzinfo).timestamp() - created_time.timestamp()
                    if age < 6 * 60 * 60:
                        return False
            else:
                return False
        return True

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _resolve_doc_paths(self, docs_dir: Path) -> tuple[Path, Path, Path, int]:
        try:
            docs_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立 docs 目錄失敗：%s", exc, exc_info=True)
            raise
        version = self._next_doc_version(docs_dir)
        suffix = f"_v{version}"
        draft_path = docs_dir / f"draft{suffix}.md"
        final_path = docs_dir / f"final{suffix}.md"
        reviews_dir = docs_dir / f"reviews{suffix}"
        try:
            reviews_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立 reviews 目錄失敗：%s", exc, exc_info=True)
            raise
        return draft_path, reviews_dir, final_path, version

    def _next_doc_version(self, docs_dir: Path) -> int:
        max_version = 0
        legacy_paths = [docs_dir / "draft.md", docs_dir / "final.md", docs_dir / "reviews"]
        if any(path.exists() for path in legacy_paths):
            max_version = 1
        for path in docs_dir.glob("draft_v*.md"):
            try:
                version = int(path.stem.split("_v")[-1])
            except ValueError:
                continue
            max_version = max(max_version, version)
        for path in docs_dir.glob("final_v*.md"):
            try:
                version = int(path.stem.split("_v")[-1])
            except ValueError:
                continue
            max_version = max(max_version, version)
        return max_version + 1 if max_version else 1

    def _generate_reviewer_personas(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        prompt: str,
        session_path: Path,
        session_id: str,
        config: dict[str, Any],
        provider_type: str | None,
        project_id: str | None,
    ) -> list[dict[str, str]]:
        role_factory_system = (
            "你是 RoleFactory，負責產生 10 位 reviewer personas。"
            "請以 JSON 陣列輸出，每筆符合 schema："
            '{"persona_id":"reviewer01","name":"","focus":"","tone":"","instructions":""}。'
            "persona_id 必須是 reviewer01 ~ reviewer10，且只輸出 JSON。"
        )
        role_factory_messages = [
            {"role": "system", "content": role_factory_system},
            {"role": "user", "content": f"任務：{prompt}\n\n請輸出 10 位 reviewer personas。"},
        ]
        raw = self._stream_and_collect(
            provider=provider,
            provider_name=provider_name,
            provider_model=provider_model,
            messages=role_factory_messages,
            session_path=session_path,
            session_id=session_id,
            stage="role_factory",
            config=config,
            prompt_text=role_factory_messages[-1]["content"],
            project_id=project_id,
        )
        try:
            personas = json.loads(raw)
        except json.JSONDecodeError:
            self.logger.warning("解析 reviewer personas JSON 失敗，改用預設清單。")
            personas = self._default_personas()
        if not isinstance(personas, list) or len(personas) != 10:
            self.logger.warning("reviewer personas 格式不符，改用預設清單。")
            personas = self._default_personas()
        normalized = []
        for index, persona in enumerate(personas, start=1):
            if not isinstance(persona, dict):
                continue
            persona_id = str(persona.get("persona_id") or f"reviewer{index:02d}")
            normalized.append(
                {
                    "persona_id": persona_id,
                    "name": str(persona.get("name") or f"Reviewer{index:02d}"),
                    "focus": str(persona.get("focus") or "通用審查"),
                    "tone": str(persona.get("tone") or "直接"),
                    "instructions": str(persona.get("instructions") or "提供具體改進建議。"),
                }
            )
        if len(normalized) != 10:
            normalized = self._default_personas()
        return normalized

    def _default_personas(self) -> list[dict[str, str]]:
        return [
            {
                "persona_id": f"reviewer{index:02d}",
                "name": name,
                "focus": focus,
                "tone": tone,
                "instructions": instruction,
            }
            for index, (name, focus, tone, instruction) in enumerate(
                [
                    ("架構審查", "架構一致性與模組化", "嚴謹", "檢查是否符合規格並提出改善點。"),
                    ("資料一致性", "資料結構與流程", "審慎", "指出資料流與持久化問題。"),
                    ("安全守門員", "安全與風險", "直接", "列出可能風險與對應修正。"),
                    ("使用者體驗", "UX 與可讀性", "溫和", "提出可讀性與流程改善建議。"),
                    ("測試工程師", "測試與驗收", "務實", "補強測試缺口與驗收。"),
                    ("效能守護", "效能與擴展性", "直白", "指出效能瓶頸與優化方向。"),
                    ("錯誤處理", "錯誤流程", "嚴格", "檢查錯誤處理與日誌。"),
                    ("文件品質", "文件與可維護性", "平實", "提出文件與維護性建議。"),
                    ("CLI 流程", "CLI 使用流程", "精準", "檢查 CLI 流程與輸出。"),
                    ("向下相容", "向下相容與最小變動", "小心", "確認最小改動與相容性。"),
                ],
                start=1,
            )
        ]

    @staticmethod
    def _review_filename(persona: dict[str, str]) -> str:
        safe_name = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_" for char in persona["name"].strip()
        )
        safe_name = safe_name or "reviewer"
        return f"{persona['persona_id']}_{safe_name}.md"

    @staticmethod
    def _build_final_prompt(
        prompt: str, draft: str, reviews: list[tuple[dict[str, str], str, Path]]
    ) -> str:
        review_sections = []
        for persona, review_text, _path in reviews:
            review_sections.append(
                "review:\n"
                f"- persona_id: {persona['persona_id']}\n"
                f"- name: {persona['name']}\n"
                f"- focus: {persona['focus']}\n"
                f"- tone: {persona['tone']}\n"
                f"- instructions: {persona['instructions']}\n"
                f"{review_text}"
            )
        reviews_block = "\n\n".join(review_sections)
        return f"任務：{prompt}\n\n草稿：\n{draft}\n\nReviews：\n{reviews_block}\n\n請整合後輸出 final。"

    def _stream_to_file(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        messages: list[dict[str, str]],
        output_path: Path,
        session_path: Path,
        session_id: str,
        stage: str,
        config: dict[str, Any],
        provider_type: str | None,
        prompt_text: str,
        project_id: str | None,
    ) -> str:
        response_text = ""
        try:
            self._append_session_event(
                session_path,
                {
                    "event": "prompt",
                    "content": prompt_text,
                    "stage": stage,
                    "provider": provider_name,
                    "model": provider_model,
                },
                session_id=session_id,
            )
            with output_path.open("w", encoding="utf-8") as handle:
                for index, token in enumerate(provider.generate_stream(messages, model=provider_model)):
                    is_reasoning, reasoning_text = decode_reasoning_chunk(token)
                    if is_reasoning:
                        self._append_session_event(
                            session_path,
                            {
                                "event": "reasoning_chunk",
                                "index": index,
                                "content": reasoning_text,
                                "stage": stage,
                                "provider": provider_name,
                                "model": provider_model,
                            },
                            session_id=session_id,
                        )
                        continue
                    print(token, end="", flush=True)
                    handle.write(token)
                    response_text += token
                    self._append_session_event(
                        session_path,
                        {
                            "event": "chunk",
                            "index": index,
                            "content": token,
                            "stage": stage,
                            "provider": provider_name,
                            "model": provider_model,
                        },
                        session_id=session_id,
                    )
            print("")
        except OSError as exc:
            self.logger.error("寫入輸出失敗：%s", exc, exc_info=True)
            raise
        except ProviderError as exc:
            self.logger.error("模型執行失敗：%s", exc, exc_info=True)
            raise
        self._append_session_event(
            session_path,
            {
                "event": "final",
                "content": response_text,
                "stage": stage,
                "provider": provider_name,
                "model": provider_model,
            },
            session_id=session_id,
        )
        self._log_billing(
            config,
            provider_name,
            provider_model or "",
            prompt_text,
            response_text,
            session_id=session_id,
            project_id=project_id,
            project_path=session_path.parents[1] if len(session_path.parents) > 1 else None,
        )
        return response_text

    def _stream_and_collect(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        messages: list[dict[str, str]],
        session_path: Path,
        session_id: str,
        stage: str,
        config: dict[str, Any],
        prompt_text: str,
        project_id: str | None,
    ) -> str:
        response_text = ""
        try:
            self._append_session_event(
                session_path,
                {
                    "event": "prompt",
                    "content": prompt_text,
                    "stage": stage,
                    "provider": provider_name,
                    "model": provider_model,
                },
                session_id=session_id,
            )
            for index, token in enumerate(provider.generate_stream(messages, model=provider_model)):
                is_reasoning, reasoning_text = decode_reasoning_chunk(token)
                if is_reasoning:
                    self._append_session_event(
                        session_path,
                        {
                            "event": "reasoning_chunk",
                            "index": index,
                            "content": reasoning_text,
                            "stage": stage,
                            "provider": provider_name,
                            "model": provider_model,
                        },
                        session_id=session_id,
                    )
                    continue
                print(token, end="", flush=True)
                response_text += token
                self._append_session_event(
                    session_path,
                    {
                        "event": "chunk",
                        "index": index,
                        "content": token,
                        "stage": stage,
                        "provider": provider_name,
                        "model": provider_model,
                    },
                    session_id=session_id,
                )
            print("")
        except ProviderError as exc:
            self.logger.error("模型執行失敗：%s", exc, exc_info=True)
            raise
        self._append_session_event(
            session_path,
            {
                "event": "final",
                "content": response_text,
                "stage": stage,
                "provider": provider_name,
                "model": provider_model,
            },
            session_id=session_id,
        )
        self._log_billing(
            config,
            provider_name,
            provider_model or "",
            prompt_text,
            response_text,
            session_id=session_id,
            project_id=project_id,
            project_path=session_path.parents[1] if len(session_path.parents) > 1 else None,
        )
        return response_text

    def _load_mcp_servers(self, config: dict[str, Any]) -> list[MCPServerConfig]:
        servers_config = config.get("mcp", {}).get("servers", {}) or {}
        servers: list[MCPServerConfig] = []
        for name, server in servers_config.items():
            transport = server.get("transport") or server.get("type") or "stdio"
            command = server.get("command")
            url = server.get("url") or server.get("endpoint")
            allowed = server.get("allowed")
            parsed_command: list[str] | None = None
            if isinstance(command, list):
                parsed_command = [str(item) for item in command]
            elif isinstance(command, str):
                parsed_command = shlex.split(command)
            if parsed_command:
                if any(not str(item).strip() for item in parsed_command):
                    raise ValueError(f"MCP server {name} command 不可為空")
                if any(item in {"&&", "||", ";", "|", "&"} for item in parsed_command):
                    raise ValueError(f"MCP server {name} command 不允許 shell 控制字元")
                executable = parsed_command[0]
                executable_path = Path(executable)
                if executable_path.is_absolute():
                    if not executable_path.exists():
                        raise ValueError(f"MCP server {name} command 不存在：{executable}")
                elif shutil.which(executable) is None:
                    raise ValueError(f"MCP server {name} command 不存在：{executable}")
            servers.append(
                MCPServerConfig(
                    name=name,
                    transport=str(transport),
                    command=parsed_command,
                    url=str(url) if url else None,
                    allowed=allowed,
                )
            )
        return servers

    def _fetch_mcp_tools(self, server: MCPServerConfig) -> dict[str, Any]:
        if server.transport != "stdio":
            return {
                "transport": server.transport,
                "tools": [],
                "error": "尚未支援的 transport",
                "updated_at": self._now(),
            }
        if not server.command:
            return {
                "transport": server.transport,
                "tools": [],
                "error": "缺少 command 設定",
                "updated_at": self._now(),
            }
        try:
            with MCPStdioClient(server.command) as client:
                tools = client.list_tools()
            return {"transport": server.transport, "tools": tools, "updated_at": self._now()}
        except MCPClientError as exc:
            self.logger.error("MCP tools 讀取失敗：%s", exc, exc_info=True)
            return {
                "transport": server.transport,
                "tools": [],
                "error": str(exc),
                "updated_at": self._now(),
            }

    def _write_mcp_registry(self, registry: dict[str, Any]) -> None:
        path = self._mcp_registry_path()
        try:
            self._atomic_write_text(path, json.dumps(registry, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入 MCP registry 失敗：%s", exc, exc_info=True)
            raise

    def _read_mcp_cache(self, server_name: str) -> dict[str, Any] | None:
        path = self._mcp_cache_path(server_name)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取 MCP cache 失敗：%s", exc, exc_info=True)
            return None
        if not isinstance(data, dict):
            return None
        data.setdefault("transport", "unknown")
        data.setdefault("tools", [])
        return data

    def _write_mcp_cache(self, server_name: str, payload: dict[str, Any]) -> None:
        path = self._mcp_cache_path(server_name)
        try:
            self._atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入 MCP cache 失敗：%s", exc, exc_info=True)
            raise

    def _is_tool_allowed(self, full_tool: str, config: dict[str, Any], server: MCPServerConfig) -> bool:
        allowed_tools = config.get("mcp", {}).get("allowed_tools", []) or []
        server_allowed = server.allowed or []
        if allowed_tools:
            return self._match_tool(full_tool, allowed_tools)
        if server_allowed:
            return self._match_tool(
                full_tool,
                [f"{server.name}:{item}" if ":" not in item else item for item in server_allowed],
            )
        return True

    def _is_tool_denied(self, full_tool: str, config: dict[str, Any], server: MCPServerConfig) -> bool:
        denied_tools = config.get("mcp", {}).get("denied_tools", []) or []
        return self._match_tool(full_tool, denied_tools)

    @staticmethod
    def _match_tool(full_tool: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if pattern == full_tool:
                return True
            if pattern.endswith(".*") and full_tool.startswith(pattern[:-2]):
                return True
            if ":" not in pattern and full_tool.endswith(f":{pattern}"):
                return True
        return False

    @staticmethod
    def _is_high_risk_tool(tool_name: str) -> bool:
        lowered = tool_name.lower()
        return any(token in lowered for token in ["write", "delete", "remove", "destroy"])

    @staticmethod
    def _summarize_value(value: Any, limit: int = 200) -> str:
        if isinstance(value, dict):
            keys = ", ".join(sorted(value.keys()))
            text = f"dict(keys=[{keys}])"
        elif isinstance(value, list):
            text = f"list(len={len(value)})"
        else:
            text = str(value)
        if len(text) > limit:
            return f"{text[:limit]}..."
        return text

    def _append_session_event(self, session_path: Path, payload: dict[str, Any], session_id: str) -> None:
        event_payload = {"timestamp": self._now(), "session_id": session_id}
        event_payload.update(payload)
        try:
            with session_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event_payload, ensure_ascii=False))
                handle.write("\n")
        except OSError as exc:
            self.logger.error("寫入 session 事件失敗：%s", exc, exc_info=True)
            raise

    def _log_billing(
        self,
        config: dict[str, Any],
        provider: str,
        model: str,
        prompt: str,
        response: str,
        session_id: str | None = None,
        project_id: str | None = None,
        project_path: Path | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        thread_id: str | None = None,
        mode: str | None = None,
    ) -> None:
        if not config.get("billing", {}).get("enabled", True):
            return
        prompt_tokens, completion_tokens = self._estimate_llm_tokens(prompt, response, config=config)
        total_tokens = prompt_tokens + completion_tokens
        cost_estimate = self._estimate_cost(provider, model, prompt_tokens, completion_tokens)
        payload = {
            "level": "INFO",
            "event": "billing_record",
            "provider": provider,
            "model": model,
            "prompt_chars": len(prompt),
            "response_chars": len(response),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "token": total_tokens,
            "cost": cost_estimate,
            "cost_estimate": cost_estimate,
            "session_id": session_id,
            "project_id": project_id,
            "project_path": str(project_path) if project_path else None,
            "run_id": run_id,
            "node_id": node_id,
            "thread_id": thread_id,
            "mode": mode or "interactive",
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        log_billing(payload)
        if project_path and project_id:
            self._append_project_usage_ledger(project_path=project_path, payload=payload)

    def _append_project_usage_ledger(self, *, project_path: Path, payload: dict[str, Any]) -> None:
        ledger_dir = project_path / ".amon" / "billing"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / "usage.jsonl"
        record = {
            "ts": payload.get("ts") or datetime.now().isoformat(timespec="seconds"),
            "project_id": payload.get("project_id"),
            "run_id": payload.get("run_id"),
            "thread_id": payload.get("thread_id"),
            "node_id": payload.get("node_id"),
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "prompt_tokens": int(payload.get("prompt_tokens") or 0),
            "completion_tokens": int(payload.get("completion_tokens") or 0),
            "total_tokens": int(payload.get("total_tokens") or 0),
            "cost_estimate": float(payload.get("cost_estimate") or payload.get("cost") or 0.0),
            "cost": float(payload.get("cost") or payload.get("cost_estimate") or 0.0),
            "session_id": payload.get("session_id"),
            "mode": payload.get("mode") or "interactive",
        }
        try:
            with ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
        except OSError as exc:
            self.logger.error("寫入專案 billing usage ledger 失敗：%s", exc, exc_info=True)
            raise

    def _estimate_llm_tokens(self, prompt: str, response: str, *, config: dict[str, Any]) -> tuple[int, int]:
        prompt_count = count_non_dialogue_tokens(prompt, effective_config=config)
        completion_count = count_non_dialogue_tokens(response, effective_config=config)
        prompt_tokens = int(prompt_count.tokens) if prompt_count.available and prompt_count.tokens is not None else max(len(prompt) // 4, 0)
        completion_tokens = (
            int(completion_count.tokens)
            if completion_count.available and completion_count.tokens is not None
            else max(len(response) // 4, 0)
        )
        return prompt_tokens, completion_tokens

    @staticmethod
    def _estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = {
            "gpt-4o-mini": (0.00015, 0.0006),
            "gpt-4.1-mini": (0.0004, 0.0016),
            "gpt-4.1": (0.002, 0.008),
        }
        input_rate, output_rate = pricing.get(str(model or "").strip().lower(), (0.0005, 0.0015))
        cost = (prompt_tokens / 1000.0) * input_rate + (completion_tokens / 1000.0) * output_rate
        return round(cost, 8)

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _evaluate_budget(self, config: dict[str, Any], project_id: str | None) -> dict[str, Any]:
        billing_config = config.get("billing", {})
        daily_budget = self._normalize_budget(billing_config.get("daily_budget"))
        project_budget = self._normalize_budget(billing_config.get("per_project_budget"))
        if daily_budget is None and project_budget is None:
            return {
                "exceeded": False,
                "daily_budget": None,
                "per_project_budget": None,
                "daily_usage": 0,
                "project_usage": 0,
            }
        records = self._load_billing_records()
        today = datetime.now().date()
        daily_usage = self._sum_billing_usage(records, target_date=today, project_id=None)
        project_usage = (
            self._sum_billing_usage(records, target_date=None, project_id=project_id) if project_id else 0
        )
        exceeded = False
        if daily_budget is not None and daily_usage >= daily_budget:
            exceeded = True
        if project_budget is not None and project_usage >= project_budget:
            exceeded = True
        return {
            "exceeded": exceeded,
            "daily_budget": daily_budget,
            "per_project_budget": project_budget,
            "daily_usage": daily_usage,
            "project_usage": project_usage,
        }

    def _log_budget_event(self, status: dict[str, Any], mode: str, project_id: str | None, action: str) -> None:
        log_event(
            {
                "level": "WARNING",
                "event": "budget_exceeded",
                "mode": mode,
                "action": action,
                "project_id": project_id,
                "daily_budget": status.get("daily_budget"),
                "per_project_budget": status.get("per_project_budget"),
                "daily_usage": status.get("daily_usage"),
                "project_usage": status.get("project_usage"),
            }
        )

    @staticmethod
    def _normalize_budget(value: Any) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0:
            return None
        return parsed

    def _load_billing_records(self) -> list[dict[str, Any]]:
        if not self.billing_log.exists():
            return []
        try:
            lines = self.billing_log.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            self.logger.error("讀取 billing log 失敗：%s", exc, exc_info=True)
            raise
        records = []
        for line in lines:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def _sum_billing_usage(
        self,
        records: list[dict[str, Any]],
        target_date: datetime.date | None,
        project_id: str | None,
    ) -> int:
        total = 0
        for record in records:
            if project_id and record.get("project_id") != project_id:
                continue
            if target_date:
                record_date = self._parse_record_date(record.get("ts"))
                if record_date != target_date:
                    continue
            prompt_chars = int(record.get("prompt_chars", 0) or 0)
            response_chars = int(record.get("response_chars", 0) or 0)
            total += prompt_chars + response_chars
        return total

    @staticmethod
    def _parse_record_date(timestamp: str | None) -> datetime.date | None:
        if not timestamp:
            return None
        try:
            return datetime.fromisoformat(timestamp).date()
        except ValueError:
            return None

    def _add_export_path(
        self,
        archive: zipfile.ZipFile,
        path: Path,
        base_prefix: str,
        project_path: Path,
    ) -> None:
        if not path.exists():
            return
        relative = path.relative_to(project_path)
        if path.is_dir():
            entries = list(path.rglob("*"))
            if not entries:
                archive.writestr(f"{base_prefix}/{relative}/", "")
                return
            for entry in entries:
                if entry.is_file():
                    archive.write(entry, arcname=f"{base_prefix}/{entry.relative_to(project_path)}")
        else:
            archive.write(path, arcname=f"{base_prefix}/{relative}")

    def _validate_eval_outputs(self, project_path: Path) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        sessions = list((project_path / "sessions").glob("*.jsonl"))
        checks.append(
            {
                "check": "sessions_exists",
                "status": "passed" if sessions else "failed",
                "detail": f"found={len(sessions)}",
            }
        )
        docs_dir = project_path / "docs"
        draft_files = list(docs_dir.glob("draft_v*.md"))
        final_files = list(docs_dir.glob("final_v*.md"))
        checks.append(
            {
                "check": "self_critique_docs",
                "status": "passed"
                if draft_files and final_files
                else "failed",
                "detail": f"draft={len(draft_files)} final={len(final_files)}",
            }
        )
        review_files: list[Path] = []
        for reviews_dir in docs_dir.glob("reviews_v*"):
            if reviews_dir.is_dir():
                review_files.extend(list(reviews_dir.glob("*.md")))
        checks.append(
            {
                "check": "self_critique_reviews",
                "status": "passed" if review_files else "failed",
                "detail": f"count={len(review_files)}",
            }
        )
        tasks_path = project_path / "tasks" / "tasks.json"
        if tasks_path.exists():
            try:
                tasks_payload = json.loads(tasks_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                tasks_payload = None
        else:
            tasks_payload = None
        checks.append(
            {
                "check": "team_tasks_schema",
                "status": "passed" if self._has_valid_tasks_schema(tasks_payload) else "failed",
                "detail": "tasks.json",
            }
        )
        checks.append(
            {
                "check": "team_final_doc",
                "status": "passed" if (docs_dir / "final.md").exists() else "failed",
                "detail": "docs/final.md",
            }
        )
        return checks

    @staticmethod
    def _has_valid_tasks_schema(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        tasks = payload.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            return False
        required_keys = {"task_id", "title", "requiredCapabilities", "status", "attempts", "feedback"}
        for task in tasks:
            if not isinstance(task, dict):
                return False
            if not required_keys.issubset(task.keys()):
                return False
        return True
