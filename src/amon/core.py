"""Core filesystem operations for Amon."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .config import DEFAULT_CONFIG, deep_merge, get_config_value, read_yaml, set_config_value, write_yaml
from .fs.safety import canonicalize_path, make_change_plan, require_confirm
from .fs.trash import trash_move, trash_restore
from .logging import log_billing, log_event
from .logging_utils import setup_logger
from .mcp_client import MCPClientError, MCPServerConfig, MCPStdioClient
from .models import ProviderError, build_provider


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
        self.python_env_dir = self.data_dir / "python_env"
        self.node_env_dir = self.data_dir / "node_env"
        self.billing_log = self.logs_dir / "billing.log"
        self.logger = setup_logger("amon", self.logs_dir)

    def ensure_base_structure(self) -> None:
        for path in [
            self.data_dir,
            self.logs_dir,
            self.cache_dir,
            self.projects_dir,
            self.trash_dir,
            self.skills_dir,
            self.python_env_dir,
            self.node_env_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        self._touch_log(self.logs_dir / "amon.log")
        if not self.billing_log.exists():
            try:
                self.billing_log.write_text("", encoding="utf-8")
            except OSError as exc:
                self.logger.error("建立 billing.log 失敗：%s", exc, exc_info=True)
                raise
        config_path = self._global_config_path()
        if not config_path.exists():
            write_yaml(config_path, self._initial_config())
        trash_manifest = self.trash_dir / "manifest.json"
        if not trash_manifest.exists():
            try:
                trash_manifest.write_text(
                    json.dumps({"entries": []}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError as exc:
                self.logger.error("建立回收桶清單失敗：%s", exc, exc_info=True)
                raise

    def initialize(self) -> None:
        try:
            self.ensure_base_structure()
        except OSError as exc:
            self.logger.error("初始化 Amon 失敗：%s", exc, exc_info=True)
            raise

    def create_project(self, name: str) -> ProjectRecord:
        self.ensure_base_structure()
        project_id = self._generate_project_id(name)
        project_path = self.projects_dir / project_id

        if project_path.exists():
            raise FileExistsError(f"專案已存在：{project_id}")

        try:
            self._create_project_structure(project_path)
            self._write_project_config(project_path, name)
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
        self.logger.info("已建立專案 %s (%s)", name, project_id)
        return record

    def list_projects(self, include_deleted: bool = False) -> list[ProjectRecord]:
        records = self._load_records()
        log_event(
            {
                "level": "INFO",
                "event": "project_list",
                "include_deleted": include_deleted,
                "count": len(records),
            }
        )
        if include_deleted:
            return records
        return [record for record in records if record.status == "active"]

    def get_project(self, project_id: str) -> ProjectRecord:
        for record in self._load_records():
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
                self.logger.info("已刪除專案 %s (%s)", record.name, project_id)
                return record
        raise KeyError(f"找不到專案：{project_id}")

    def restore_project(self, project_id: str) -> ProjectRecord:
        records = self._load_records()
        for record in records:
            if record.project_id == project_id:
                if record.status != "deleted" or not record.trash_path:
                    raise ValueError("專案不在回收桶")
                original_path = self.projects_dir / project_id
                if original_path.exists():
                    raise FileExistsError("專案路徑已存在，無法還原")
                self._safe_move(Path(record.trash_path), original_path, "還原專案")
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
        current = read_yaml(config_path)
        updated = set_config_value(current, key_path, value)
        write_yaml(config_path, updated)

    def run_single(self, prompt: str, project_path: Path | None = None, model: str | None = None) -> str:
        config = self.load_config(project_path)
        provider_name = config.get("amon", {}).get("provider", "openai")
        provider_cfg = config.get("providers", {}).get(provider_name, {})
        provider_type = provider_cfg.get("type")
        provider_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
        provider = build_provider(provider_cfg, model=provider_model)
        system_message = "你是 Amon 的專案助理，請用繁體中文回覆。"
        skill_context = self._resolve_skill_context(prompt, project_path)
        if skill_context:
            system_message = f"{system_message}\n\n[Skill]\n{skill_context}"
        user_prompt = prompt
        if prompt.startswith("/"):
            user_prompt = " ".join(prompt.split()[1:]).strip()
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt or prompt},
        ]
        response_text = ""
        session_id = uuid.uuid4().hex
        session_path = self._prepare_session_path(project_path, session_id)
        log_event(
            {
                "level": "INFO",
                "event": "run_single_start",
                "provider": provider_name,
                "model": provider_model,
                "session_id": session_id,
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
        if provider_type == "mock":
            print("提醒：目前使用 mock provider，輸出為模擬結果。")
        try:
            for index, token in enumerate(provider.generate_stream(messages, model=provider_model)):
                print(token, end="", flush=True)
                response_text += token
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
            }
        )
        self._log_billing(config, provider_name, provider_model, prompt, response_text, session_id=session_id)
        return response_text

    def scan_skills(self, project_path: Path | None = None) -> list[dict[str, Any]]:
        config = self.load_config(project_path)
        skills = []
        global_dir = Path(config["skills"]["global_dir"]).expanduser()
        if global_dir.exists():
            skills.extend(self._scan_skill_dir(global_dir, scope="global"))
        if project_path:
            project_dir = project_path / config["skills"]["project_dir_rel"]
            if project_dir.exists():
                skills.extend(self._scan_skill_dir(project_dir, scope="project"))
        index_path = self.cache_dir / "skills_index.json"
        try:
            index_path.write_text(json.dumps({"skills": skills}, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.logger.error("寫入技能索引失敗：%s", exc, exc_info=True)
            raise
        return skills

    def list_skills(self) -> list[dict[str, Any]]:
        index_path = self.cache_dir / "skills_index.json"
        if not index_path.exists():
            return []
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("讀取技能索引失敗：%s", exc, exc_info=True)
            raise
        return data.get("skills", [])

    def get_skill(self, name: str, project_path: Path | None = None) -> dict[str, Any]:
        if project_path:
            skills = self.scan_skills(project_path)
        else:
            skills = self.list_skills()
            if not skills:
                skills = self.scan_skills()
        for skill in skills:
            if skill.get("name") == name:
                try:
                    content = Path(skill["path"]).read_text(encoding="utf-8")
                except OSError as exc:
                    self.logger.error("讀取技能檔案失敗：%s", exc, exc_info=True)
                    raise
                return {**skill, "content": content}
        raise KeyError(f"找不到技能：{name}")

    def get_project_path(self, project_id: str) -> Path:
        record = self.get_project(project_id)
        return Path(record.path)

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
        self.ensure_base_structure()
        config = self.load_config()
        servers = self._load_mcp_servers(config)
        registry = {"updated_at": self._now(), "servers": {}}
        for server in servers:
            if server.transport != "stdio":
                registry["servers"][server.name] = {
                    "transport": server.transport,
                    "tools": [],
                    "error": "尚未支援的 transport",
                }
                continue
            if not server.command:
                registry["servers"][server.name] = {
                    "transport": server.transport,
                    "tools": [],
                    "error": "缺少 command 設定",
                }
                continue
            try:
                with MCPStdioClient(server.command) as client:
                    tools = client.list_tools()
                registry["servers"][server.name] = {
                    "transport": server.transport,
                    "tools": tools,
                }
            except MCPClientError as exc:
                self.logger.error("MCP tools 讀取失敗：%s", exc, exc_info=True)
                registry["servers"][server.name] = {
                    "transport": server.transport,
                    "tools": [],
                    "error": str(exc),
                }
        self._write_mcp_registry(registry)
        return registry

    def call_mcp_tool(self, server_name: str, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.ensure_base_structure()
        config = self.load_config()
        servers = {server.name: server for server in self._load_mcp_servers(config)}
        if server_name not in servers:
            raise KeyError(f"找不到 MCP server：{server_name}")
        server = servers[server_name]
        full_tool = f"{server_name}:{tool_name}"
        if self._is_tool_denied(full_tool, config, server):
            raise PermissionError("工具已被拒絕")
        if not self._is_tool_allowed(full_tool, config, server):
            raise PermissionError("工具尚未被允許")
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
                raise RuntimeError("使用者取消操作")
        if server.transport != "stdio" or not server.command:
            raise RuntimeError("目前僅支援 stdio transport")
        try:
            with MCPStdioClient(server.command) as client:
                result = client.call_tool(tool_name, args)
        except MCPClientError as exc:
            self.logger.error("MCP tool 呼叫失敗：%s", exc, exc_info=True)
            raise
        log_event(
            {
                "level": "INFO",
                "event": "mcp_tool_call",
                "tool_name": full_tool,
                "args_summary": self._summarize_value(args),
                "result_summary": self._summarize_value(result),
            }
        )
        return result

    def _generate_project_id(self, name: str) -> str:
        slug = "".join(char.lower() for char in name if char.isalnum())
        short_id = uuid.uuid4().hex[:6]
        return f"{slug or 'project'}-{short_id}"

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

    def _create_project_structure(self, project_path: Path) -> None:
        (project_path / "workspace").mkdir(parents=True, exist_ok=True)
        (project_path / "docs").mkdir(parents=True, exist_ok=True)
        (project_path / "tasks").mkdir(parents=True, exist_ok=True)
        (project_path / "sessions").mkdir(parents=True, exist_ok=True)
        (project_path / "logs").mkdir(parents=True, exist_ok=True)
        (project_path / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        (project_path / ".amon" / "locks").mkdir(parents=True, exist_ok=True)

        tasks_path = project_path / "tasks" / "tasks.json"
        if not tasks_path.exists():
            tasks_path.write_text(json.dumps({"tasks": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_project_config(self, project_path: Path, name: str) -> None:
        config_path = project_path / "amon.project.yaml"
        config_data = {
            "amon": {
                "project_name": name,
                "mode": "auto",
            }
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
            index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.logger.error("寫入專案索引失敗：%s", exc, exc_info=True)
            raise

    def _write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        try:
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except OSError as exc:
            self.logger.error("寫入設定檔失敗：%s", exc, exc_info=True)
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
            path.write_text("", encoding="utf-8")
        except OSError as exc:
            self.logger.error("建立 %s 失敗：%s", path.name, exc, exc_info=True)
            raise

    def _mcp_registry_path(self) -> Path:
        return self.cache_dir / "mcp_registry.json"

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
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
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
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.logger.error("寫入回收桶清單失敗：%s", exc, exc_info=True)
            raise

    def _scan_skill_dir(self, base_dir: Path, scope: str) -> list[dict[str, Any]]:
        skills = []
        for child in base_dir.iterdir():
            if not child.is_dir():
                continue
            skill_file = child / "SKILL.md"
            if not skill_file.exists():
                continue
            skills.append(self._read_skill(skill_file, child.name, scope))
        return skills

    def _read_skill(self, skill_file: Path, fallback_name: str, scope: str) -> dict[str, Any]:
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            self.logger.error("讀取技能檔案失敗：%s", exc, exc_info=True)
            raise
        name = fallback_name
        description = ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError as exc:
                    self.logger.warning("解析技能 YAML frontmatter 失敗：%s", exc, exc_info=True)
                    frontmatter = {}
                name = frontmatter.get("name", name)
                description = frontmatter.get("description", "")
        return {
            "name": name,
            "description": description,
            "path": str(skill_file),
            "scope": scope,
        }

    def _resolve_skill_context(self, prompt: str, project_path: Path | None) -> str:
        if not prompt.startswith("/"):
            return ""
        skill_name = prompt.split()[0].lstrip("/")
        try:
            skill = self.get_skill(skill_name, project_path=project_path)
        except KeyError:
            return ""
        return skill.get("content", "")

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

    def _write_mcp_registry(self, registry: dict[str, Any]) -> None:
        path = self._mcp_registry_path()
        try:
            path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.logger.error("寫入 MCP registry 失敗：%s", exc, exc_info=True)
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
    ) -> None:
        if not config.get("billing", {}).get("enabled", True):
            return
        log_billing(
            {
                "level": "INFO",
                "event": "billing_record",
                "provider": provider,
                "model": model,
                "prompt_chars": len(prompt),
                "response_chars": len(response),
                "token": 0,
                "session_id": session_id,
            }
        )

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")
