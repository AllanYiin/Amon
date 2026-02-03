"""Core filesystem operations for Amon."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import uuid
import zipfile
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import urllib.error
import urllib.request

import yaml

from .config import DEFAULT_CONFIG, deep_merge, get_config_value, read_yaml, set_config_value, write_yaml
from .fs.atomic import atomic_write_text
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
        lock_context = self._project_lock(project_path, "single") if project_path else nullcontext()
        with lock_context:
            config = self.load_config(project_path)
            project_id = project_path.name if project_path else None
            budget_status = self._evaluate_budget(config, project_id=project_id)
            if budget_status["exceeded"]:
                message = "提醒：已超過用量上限，single 仍可執行，但 self_critique/team 會被拒絕。"
                print(message)
                self._log_budget_event(budget_status, mode="single", project_id=project_id, action="allow")
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
            self._log_billing(
                config,
                provider_name,
                provider_model,
                prompt,
                response_text,
                session_id=session_id,
                project_id=project_id,
            )
            return response_text

    def run_self_critique(self, prompt: str, project_path: Path | None = None, model: str | None = None) -> str:
        if not project_path:
            raise ValueError("執行 self_critique 需要指定專案")
        with self._project_lock(project_path, "self_critique"):
            config = self.load_config(project_path)
            project_id = project_path.name
            budget_status = self._evaluate_budget(config, project_id=project_id)
            if budget_status["exceeded"]:
                self._log_budget_event(budget_status, mode="self_critique", project_id=project_id, action="reject")
                raise RuntimeError("已超過用量上限，拒絕執行 self_critique")
            provider_name = config.get("amon", {}).get("provider", "openai")
            provider_cfg = config.get("providers", {}).get(provider_name, {})
            provider_type = provider_cfg.get("type")
            provider_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
            provider = build_provider(provider_cfg, model=provider_model)
            session_id = uuid.uuid4().hex
            session_path = self._prepare_session_path(project_path, session_id)
            docs_dir = project_path / "docs"
            draft_path, reviews_dir, final_path, version = self._resolve_doc_paths(docs_dir)
            log_event(
                {
                    "level": "INFO",
                    "event": "self_critique_start",
                    "provider": provider_name,
                    "model": provider_model,
                    "session_id": session_id,
                    "doc_version": version,
                    "project_id": project_path.name,
                }
            )
            if provider_type == "mock":
                print("提醒：目前使用 mock provider，輸出為模擬結果。")

            personas = self._generate_reviewer_personas(
                provider=provider,
                provider_name=provider_name,
                provider_model=provider_model,
                prompt=prompt,
                session_path=session_path,
                session_id=session_id,
                config=config,
                provider_type=provider_type,
                project_id=project_path.name,
            )

            writer_system = "你是 Writer，負責撰寫草稿。請用繁體中文輸出 markdown。"
            draft_messages = [
                {"role": "system", "content": writer_system},
                {"role": "user", "content": f"任務：{prompt}\n\n請先產出草稿。"},
            ]
            draft_text = self._stream_to_file(
                provider=provider,
                provider_name=provider_name,
                provider_model=provider_model,
                messages=draft_messages,
                output_path=draft_path,
                session_path=session_path,
                session_id=session_id,
                stage="draft",
                config=config,
                provider_type=provider_type,
                prompt_text=draft_messages[-1]["content"],
                project_id=project_path.name,
            )

            reviews: list[tuple[dict[str, str], str, Path]] = []
            for persona in personas:
                reviewer_messages = [
                    {
                        "role": "system",
                        "content": (
                            "你是 Reviewer，請根據指定 persona 嚴格評論草稿，"
                            "提出具體缺陷與改善建議。請用繁體中文輸出 markdown。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "persona:\n"
                            f"- persona_id: {persona['persona_id']}\n"
                            f"- name: {persona['name']}\n"
                            f"- focus: {persona['focus']}\n"
                            f"- tone: {persona['tone']}\n"
                            f"- instructions: {persona['instructions']}\n\n"
                            "draft:\n"
                            f"{draft_text}\n\n請提供批評與建議。"
                        ),
                    },
                ]
                review_filename = self._review_filename(persona)
                review_path = reviews_dir / review_filename
                review_text = self._stream_to_file(
                    provider=provider,
                    provider_name=provider_name,
                    provider_model=provider_model,
                    messages=reviewer_messages,
                    output_path=review_path,
                    session_path=session_path,
                    session_id=session_id,
                    stage=f"review:{persona['persona_id']}",
                    config=config,
                    provider_type=provider_type,
                    prompt_text=reviewer_messages[-1]["content"],
                    project_id=project_path.name,
                )
                reviews.append((persona, review_text, review_path))

            final_messages = [
                {
                    "role": "system",
                    "content": "你是 Writer，負責整合所有 reviews，產出最終版本。請用繁體中文輸出 markdown。",
                },
                {
                    "role": "user",
                    "content": self._build_final_prompt(prompt, draft_text, reviews),
                },
            ]
            final_text = self._stream_to_file(
                provider=provider,
                provider_name=provider_name,
                provider_model=provider_model,
                messages=final_messages,
                output_path=final_path,
                session_path=session_path,
                session_id=session_id,
                stage="final",
                config=config,
                provider_type=provider_type,
                prompt_text=final_messages[-1]["content"],
                project_id=project_path.name,
            )
            log_event(
                {
                    "level": "INFO",
                    "event": "self_critique_complete",
                    "provider": provider_name,
                    "model": provider_model,
                    "session_id": session_id,
                    "doc_version": version,
                    "project_id": project_path.name,
                }
            )
            return final_text

    def run_team(self, prompt: str, project_path: Path | None = None, model: str | None = None) -> str:
        if not project_path:
            raise ValueError("執行 team 需要指定專案")
        with self._project_lock(project_path, "team"):
            config = self.load_config(project_path)
            project_id = project_path.name
            budget_status = self._evaluate_budget(config, project_id=project_id)
            if budget_status["exceeded"]:
                self._log_budget_event(budget_status, mode="team", project_id=project_id, action="reject")
                raise RuntimeError("已超過用量上限，拒絕執行 team")
            provider_name = config.get("amon", {}).get("provider", "openai")
            provider_cfg = config.get("providers", {}).get(provider_name, {})
            provider_type = provider_cfg.get("type")
            provider_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
            provider = build_provider(provider_cfg, model=provider_model)
            session_id = uuid.uuid4().hex
            session_path = self._prepare_session_path(project_path, session_id)
            docs_dir = project_path / "docs"
            tasks_dir = project_path / "tasks"
            tasks_path = tasks_dir / "tasks.json"
            team_max_retries = int(config.get("amon", {}).get("team_max_retries", 2))
            log_event(
                {
                    "level": "INFO",
                    "event": "team_start",
                    "provider": provider_name,
                    "model": provider_model,
                    "session_id": session_id,
                    "project_id": project_path.name,
                }
            )
            if provider_type == "mock":
                print("提醒：目前使用 mock provider，輸出為模擬結果。")
            try:
                docs_dir.mkdir(parents=True, exist_ok=True)
                tasks_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.logger.error("建立 team 目錄失敗：%s", exc, exc_info=True)
                raise

            tasks_payload = self._load_tasks_payload(tasks_path)
            if not tasks_payload["tasks"]:
                tasks_payload = self._team_plan_tasks(
                    provider=provider,
                    provider_name=provider_name,
                    provider_model=provider_model,
                    provider_type=provider_type,
                    prompt=prompt,
                    docs_dir=docs_dir,
                    session_path=session_path,
                    session_id=session_id,
                    config=config,
                    project_id=project_id,
                )
                self._write_tasks_payload(tasks_path, tasks_payload)
            tasks_payload["tasks"] = self._normalize_team_tasks(tasks_payload.get("tasks", []))
            self._write_tasks_payload(tasks_path, tasks_payload)

            for task in tasks_payload["tasks"]:
                if task["status"] == "done":
                    continue
                attempts = int(task.get("attempts", 0))
                while attempts < team_max_retries:
                    task["status"] = "in_progress"
                    task["attempts"] = attempts
                    self._write_tasks_payload(tasks_path, tasks_payload)
                    log_event(
                        {
                            "level": "INFO",
                            "event": "team_task_start",
                            "task_id": task["task_id"],
                            "title": task["title"],
                            "session_id": session_id,
                            "project_id": project_path.name,
                        }
                    )

                    persona = self._team_role_factory(
                        provider=provider,
                        provider_name=provider_name,
                        provider_model=provider_model,
                        provider_type=provider_type,
                        task=task,
                        docs_dir=docs_dir,
                        session_path=session_path,
                        session_id=session_id,
                        config=config,
                        project_id=project_id,
                    )
                    result_path = self._team_execute_task(
                        provider=provider,
                        provider_name=provider_name,
                        provider_model=provider_model,
                        provider_type=provider_type,
                        prompt=prompt,
                        task=task,
                        persona=persona,
                        docs_dir=docs_dir,
                        session_path=session_path,
                        session_id=session_id,
                        config=config,
                        project_id=project_id,
                    )
                    audit = self._team_audit_task(
                        provider=provider,
                        provider_name=provider_name,
                        provider_model=provider_model,
                        provider_type=provider_type,
                        task=task,
                        result_path=result_path,
                        docs_dir=docs_dir,
                        session_path=session_path,
                        session_id=session_id,
                        config=config,
                        project_id=project_id,
                    )
                    if audit["status"] == "APPROVED":
                        task["status"] = "done"
                        task["feedback"] = audit.get("feedback")
                        self._write_tasks_payload(tasks_path, tasks_payload)
                        log_event(
                            {
                                "level": "INFO",
                                "event": "team_task_approved",
                                "task_id": task["task_id"],
                                "session_id": session_id,
                                "project_id": project_path.name,
                            }
                        )
                        break
                    attempts += 1
                    task["attempts"] = attempts
                    task["status"] = "todo"
                    task["feedback"] = audit.get("feedback")
                    self._write_tasks_payload(tasks_path, tasks_payload)
                    log_event(
                        {
                            "level": "WARNING",
                            "event": "team_task_rejected",
                            "task_id": task["task_id"],
                            "session_id": session_id,
                            "project_id": project_path.name,
                            "attempts": attempts,
                        }
                    )
                    if attempts >= team_max_retries:
                        task["status"] = "failed"
                        self._write_tasks_payload(tasks_path, tasks_payload)
                        log_event(
                            {
                                "level": "ERROR",
                                "event": "team_task_failed",
                                "task_id": task["task_id"],
                                "session_id": session_id,
                                "project_id": project_path.name,
                            }
                        )
                        break

            final_text = self._team_synthesize(
                provider=provider,
                provider_name=provider_name,
                provider_model=provider_model,
                provider_type=provider_type,
                prompt=prompt,
                tasks=tasks_payload["tasks"],
                docs_dir=docs_dir,
                session_path=session_path,
                session_id=session_id,
                config=config,
                project_id=project_id,
            )
            log_event(
                {
                    "level": "INFO",
                    "event": "team_complete",
                    "provider": provider_name,
                    "model": provider_model,
                    "session_id": session_id,
                    "project_id": project_path.name,
                }
            )
            return final_text

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
        base_prefix = project_path.name
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

    def run_eval(self, suite: str = "basic") -> dict[str, Any]:
        if suite != "basic":
            raise ValueError(f"不支援的評測套件：{suite}")
        self.ensure_base_structure()
        project_name = f"eval-basic-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        project = self.create_project(project_name)
        project_path = Path(project.path)
        self.set_config_value(
            "providers.mock",
            {
                "type": "mock",
                "default_model": "mock-model",
                "stream_chunks": ["[mock]"],
            },
            project_path=project_path,
        )
        self.set_config_value("amon.provider", "mock", project_path=project_path)
        log_event(
            {
                "level": "INFO",
                "event": "eval_start",
                "suite": suite,
                "project_id": project_path.name,
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
            "project_id": project_path.name,
            "status": status,
            "tasks": results,
            "checks": checks,
        }
        log_event(
            {
                "level": "INFO" if status == "passed" else "ERROR",
                "event": "eval_complete",
                "suite": suite,
                "project_id": project_path.name,
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
                return {"status": "warning", "message": "目前使用 mock provider，未檢查實際連線"}
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
        index_path = self.cache_dir / "skills_index.json"
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

    def _team_plan_tasks(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        provider_type: str | None,
        prompt: str,
        docs_dir: Path,
        session_path: Path,
        session_id: str,
        config: dict[str, Any],
        project_id: str | None,
    ) -> dict[str, Any]:
        plan_dir = docs_dir / "tasks"
        try:
            plan_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立 team 任務目錄失敗：%s", exc, exc_info=True)
            raise
        plan_path = plan_dir / "plan.json"
        system_message = "你是 PM，負責拆解任務並輸出 JSON。"
        user_message = (
            "請根據 user_task 拆解任務，輸出 JSON 格式："
            '{"tasks":[{"task_id":"t1","title":"...","requiredCapabilities":["capability"]}]}。'
            "請只輸出 JSON。user_task: "
            f"{prompt}"
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
        if provider_type == "mock":
            print("提醒：目前使用 mock provider，輸出為模擬結果。")
        response_text = self._stream_and_collect(
            provider=provider,
            provider_name=provider_name,
            provider_model=provider_model,
            messages=messages,
            session_path=session_path,
            session_id=session_id,
            stage="team:plan",
            config=config,
            prompt_text=user_message,
            project_id=project_id,
        )
        try:
            self._atomic_write_text(plan_path, response_text)
        except OSError as exc:
            self.logger.error("寫入 team 任務規劃失敗：%s", exc, exc_info=True)
            raise
        parsed = self._parse_json_payload(response_text)
        tasks_data = []
        if isinstance(parsed, dict):
            tasks_data = parsed.get("tasks", [])
        elif isinstance(parsed, list):
            tasks_data = parsed
        if not tasks_data:
            tasks_data = [
                {
                    "task_id": "task-1",
                    "title": "預設任務",
                    "requiredCapabilities": ["generalist"],
                }
            ]
        return {"tasks": tasks_data}

    def _team_role_factory(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        provider_type: str | None,
        task: dict[str, Any],
        docs_dir: Path,
        session_path: Path,
        session_id: str,
        config: dict[str, Any],
        project_id: str | None,
    ) -> dict[str, Any]:
        role_dir = docs_dir / "tasks" / task["task_id"]
        try:
            role_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立角色目錄失敗：%s", exc, exc_info=True)
            raise
        persona_path = role_dir / "persona.json"
        system_message = "你是 RoleFactory，請為任務建立 persona，輸出 JSON。"
        user_message = (
            "請輸出 persona JSON："
            '{"persona_id":"p1","name":"...","focus":"...","tone":"...","instructions":"..."}。'
            f" 任務：{task['title']}，能力：{', '.join(task['requiredCapabilities'])}"
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
        if provider_type == "mock":
            print("提醒：目前使用 mock provider，輸出為模擬結果。")
        response_text = self._stream_and_collect(
            provider=provider,
            provider_name=provider_name,
            provider_model=provider_model,
            messages=messages,
            session_path=session_path,
            session_id=session_id,
            stage=f"team:role:{task['task_id']}",
            config=config,
            prompt_text=user_message,
            project_id=project_id,
        )
        parsed = self._parse_json_payload(response_text)
        if not isinstance(parsed, dict) or not {"persona_id", "name", "focus", "tone", "instructions"}.issubset(
            parsed.keys()
        ):
            parsed = {
                "persona_id": f"persona-{task['task_id']}",
                "name": "通用執行者",
                "focus": "任務交付",
                "tone": "務實",
                "instructions": "依照任務需求完成工作，輸出清楚的結果。",
            }
        try:
            self._atomic_write_text(persona_path, json.dumps(parsed, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入 persona 失敗：%s", exc, exc_info=True)
            raise
        return parsed

    def _team_execute_task(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        provider_type: str | None,
        prompt: str,
        task: dict[str, Any],
        persona: dict[str, Any],
        docs_dir: Path,
        session_path: Path,
        session_id: str,
        config: dict[str, Any],
        project_id: str | None,
    ) -> Path:
        task_dir = docs_dir / "tasks" / task["task_id"]
        try:
            task_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立任務目錄失敗：%s", exc, exc_info=True)
            raise
        result_path = task_dir / "result.md"
        system_message = "你是 StemAgent，負責完成指定任務。請用繁體中文輸出 markdown。"
        persona_block = (
            f"persona_id: {persona.get('persona_id')}\n"
            f"name: {persona.get('name')}\n"
            f"focus: {persona.get('focus')}\n"
            f"tone: {persona.get('tone')}\n"
            f"instructions: {persona.get('instructions')}"
        )
        user_message = (
            f"user_task: {prompt}\n\n"
            f"task: {task['title']}\n"
            f"requiredCapabilities: {', '.join(task['requiredCapabilities'])}\n\n"
            f"persona:\n{persona_block}\n\n"
            "請產出對應的結果。"
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
        self._stream_to_file(
            provider=provider,
            provider_name=provider_name,
            provider_model=provider_model,
            messages=messages,
            output_path=result_path,
            session_path=session_path,
            session_id=session_id,
            stage=f"team:execute:{task['task_id']}",
            config=config,
            provider_type=provider_type,
            prompt_text=user_message,
            project_id=project_id,
        )
        return result_path

    def _team_audit_task(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        provider_type: str | None,
        task: dict[str, Any],
        result_path: Path,
        docs_dir: Path,
        session_path: Path,
        session_id: str,
        config: dict[str, Any],
        project_id: str | None,
    ) -> dict[str, Any]:
        audits_dir = docs_dir / "audits"
        try:
            audits_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立 audits 目錄失敗：%s", exc, exc_info=True)
            raise
        audit_path = audits_dir / f"{task['task_id']}.json"
        try:
            result_text = result_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.logger.error("讀取任務結果失敗：%s", exc, exc_info=True)
            raise
        system_message = "你是 Auditor，請審核任務結果並輸出 JSON。"
        user_message = (
            "請輸出 JSON 格式："
            '{"status":"APPROVED|REJECTED","feedback":"..."}。'
            f" 任務：{task['title']}\n結果：\n{result_text}"
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
        if provider_type == "mock":
            print("提醒：目前使用 mock provider，輸出為模擬結果。")
        response_text = self._stream_and_collect(
            provider=provider,
            provider_name=provider_name,
            provider_model=provider_model,
            messages=messages,
            session_path=session_path,
            session_id=session_id,
            stage=f"team:audit:{task['task_id']}",
            config=config,
            prompt_text=user_message,
            project_id=project_id,
        )
        parsed = self._parse_json_payload(response_text)
        status = "APPROVED"
        feedback = "自動通過（未提供有效審核結果）。"
        if isinstance(parsed, dict):
            status = str(parsed.get("status") or status).upper()
            feedback = str(parsed.get("feedback") or feedback)
        if status not in {"APPROVED", "REJECTED"}:
            status = "APPROVED"
        audit_payload = {"status": status, "feedback": feedback}
        try:
            self._atomic_write_text(audit_path, json.dumps(audit_payload, ensure_ascii=False, indent=2))
        except OSError as exc:
            self.logger.error("寫入審核結果失敗：%s", exc, exc_info=True)
            raise
        return audit_payload

    def _team_synthesize(
        self,
        provider: Any,
        provider_name: str,
        provider_model: str | None,
        provider_type: str | None,
        prompt: str,
        tasks: list[dict[str, Any]],
        docs_dir: Path,
        session_path: Path,
        session_id: str,
        config: dict[str, Any],
        project_id: str | None,
    ) -> str:
        final_path = docs_dir / "final.md"
        approved_tasks = [task for task in tasks if task.get("status") == "done"]
        if not approved_tasks:
            fallback_text = "目前沒有通過審核的任務，無法產出最終整合結果。"
            try:
                self._atomic_write_text(final_path, fallback_text)
            except OSError as exc:
                self.logger.error("寫入 final.md 失敗：%s", exc, exc_info=True)
                raise
            return fallback_text
        result_blocks = []
        for task in approved_tasks:
            result_path = docs_dir / "tasks" / task["task_id"] / "result.md"
            try:
                result_text = result_path.read_text(encoding="utf-8")
            except OSError as exc:
                self.logger.error("讀取任務結果失敗：%s", exc, exc_info=True)
                raise
            result_blocks.append(f"task_id: {task['task_id']}\n標題：{task['title']}\n{result_text}")
        synthesis_prompt = (
            f"user_task: {prompt}\n\n"
            "以下是已通過審核的任務結果，請整合為最終輸出：\n\n"
            + "\n\n".join(result_blocks)
        )
        messages = [
            {"role": "system", "content": "你是 PM，負責整合所有任務輸出。請用繁體中文輸出 markdown。"},
            {"role": "user", "content": synthesis_prompt},
        ]
        return self._stream_to_file(
            provider=provider,
            provider_name=provider_name,
            provider_model=provider_model,
            messages=messages,
            output_path=final_path,
            session_path=session_path,
            session_id=session_id,
            stage="team:final",
            config=config,
            provider_type=provider_type,
            prompt_text=synthesis_prompt,
            project_id=project_id,
        )

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
            self._atomic_write_text(index_path, json.dumps({"skills": skills}, ensure_ascii=False, indent=2))
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
        data_prompt = self._format_mcp_result(full_tool, result)
        log_event(
            {
                "level": "INFO",
                "event": "mcp_tool_call",
                "tool_name": full_tool,
                "args_summary": self._summarize_value(args),
                "result_summary": self._summarize_value(result),
            }
        )
        return {"tool": full_tool, "data": result, "data_prompt": data_prompt}

    @staticmethod
    def _format_mcp_result(tool_name: str, result: dict[str, Any]) -> str:
        payload = json.dumps(result, ensure_ascii=False, indent=2)
        return f"[資料]\n工具：{tool_name}\n```json\n{payload}\n```"

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
        (project_path / "memory").mkdir(parents=True, exist_ok=True)
        (project_path / "logs").mkdir(parents=True, exist_ok=True)
        (project_path / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        (project_path / ".amon" / "locks").mkdir(parents=True, exist_ok=True)

        tasks_path = project_path / "tasks" / "tasks.json"
        if not tasks_path.exists():
            self._atomic_write_text(tasks_path, json.dumps({"tasks": []}, ensure_ascii=False, indent=2))

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

    def _prepare_memory_dir(self, project_path: Path) -> Path:
        memory_dir = project_path / "memory"
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.logger.error("建立 memory 目錄失敗：%s", exc, exc_info=True)
            raise
        return memory_dir

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
                        "project_id": project_id or project_path.name,
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
            self.normalize_memory_dates(project_path)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("日期標準化失敗：%s", exc, exc_info=True)
            raise
        return chunk_count

    def normalize_memory_dates(self, project_path: Path) -> int:
        if not project_path:
            raise ValueError("執行 memory normalize 需要指定專案")
        memory_dir = self._prepare_memory_dir(project_path)
        chunks_path = memory_dir / "chunks.jsonl"
        normalized_path = memory_dir / "normalized.jsonl"
        if not chunks_path.exists():
            self.logger.error("找不到 memory chunks 檔案：%s", chunks_path)
            raise FileNotFoundError(f"找不到 memory chunks 檔案：{chunks_path}")
        normalized_count = 0
        try:
            with chunks_path.open("r", encoding="utf-8") as handle, normalized_path.open(
                "w", encoding="utf-8"
            ) as out_handle:
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
                    normalized = dict(chunk)
                    normalized["time"] = {"mentions": mentions}
                    normalized["geo"] = {"mentions": geo_mentions}
                    out_handle.write(json.dumps(normalized, ensure_ascii=False))
                    out_handle.write("\n")
                    normalized_count += 1
        except OSError as exc:
            self.logger.error("寫入 memory normalized 失敗：%s", exc, exc_info=True)
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
        if provider_type == "mock":
            print("提醒：目前使用 mock provider，輸出為模擬結果。")
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
        if provider_type == "mock":
            print("提醒：目前使用 mock provider，輸出為模擬結果。")
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
            self._atomic_write_text(path, json.dumps(registry, ensure_ascii=False, indent=2))
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
        project_id: str | None = None,
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
                "project_id": project_id,
            }
        )

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
