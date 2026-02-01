"""Core filesystem operations for Amon."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .logging_utils import setup_logger


DEFAULT_CONFIG = {
    "amon": {
        "data_dir": "~/.amon",
        "default_mode": "auto",
        "ui": {"theme": "light", "streaming": True},
    },
    "skills": {
        "global_dir": "~/.amon/skills",
        "project_dir_rel": ".claude/skills",
    },
    "billing": {"enabled": True, "currency": "USD"},
}


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
        self.data_dir = data_dir or Path("~/.amon").expanduser()
        self.logs_dir = self.data_dir / "logs"
        self.cache_dir = self.data_dir / "cache"
        self.projects_dir = self.data_dir / "projects"
        self.trash_dir = self.data_dir / "trash"
        self.logger = setup_logger("amon", self.logs_dir)

    def ensure_base_structure(self) -> None:
        for path in [self.data_dir, self.logs_dir, self.cache_dir, self.projects_dir, self.trash_dir]:
            path.mkdir(parents=True, exist_ok=True)
        config_path = self.data_dir / "config.yaml"
        if not config_path.exists():
            self._write_yaml(config_path, DEFAULT_CONFIG)

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
        self.logger.info("已建立專案 %s (%s)", name, project_id)
        return record

    def list_projects(self, include_deleted: bool = False) -> list[ProjectRecord]:
        records = self._load_records()
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
                self.logger.info("已還原專案 %s (%s)", record.name, project_id)
                return record
        raise KeyError(f"找不到專案：{project_id}")

    def _generate_project_id(self, name: str) -> str:
        slug = "".join(char.lower() for char in name if char.isalnum())
        short_id = uuid.uuid4().hex[:6]
        return f"{slug or 'project'}-{short_id}"

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
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return [ProjectRecord(**item) for item in data.get("projects", [])]

    def _write_records(self, records: list[ProjectRecord]) -> None:
        index_path = self.cache_dir / "projects_index.json"
        payload = {"projects": [record.to_dict() for record in records]}
        index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

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

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")
