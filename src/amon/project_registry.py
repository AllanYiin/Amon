from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import read_yaml, write_yaml


LEGACY_PROJECT_DIR_PATTERN = re.compile(r"^project-(?:\d+|[a-f0-9]+)?$")


@dataclass
class ProjectConfigIdentity:
    project_id: str
    project_name: str
    config: dict[str, Any]


def load_project_config(project_path: Path) -> ProjectConfigIdentity:
    config_path = project_path / "amon.project.yaml"
    config = read_yaml(config_path)
    amon_config = config.setdefault("amon", {})

    project_id = str(amon_config.get("project_id") or "").strip()
    if not project_id:
        project_id = project_path.name
        amon_config["project_id"] = project_id
        write_yaml(config_path, config)

    project_name = str(amon_config.get("project_name") or "").strip() or project_id
    if not amon_config.get("project_name"):
        amon_config["project_name"] = project_name
        write_yaml(config_path, config)

    return ProjectConfigIdentity(project_id=project_id, project_name=project_name, config=config)


class ProjectRegistry:
    def __init__(
        self,
        root_dir: Path,
        *,
        slug_builder: Callable[[str, set[str]], str] | None = None,
        logger=None,
    ) -> None:
        self.root_dir = root_dir
        self._slug_builder = slug_builder
        self._logger = logger
        self._id_to_path: dict[str, Path] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    def scan(self) -> None:
        self._id_to_path = {}
        self._meta = {}
        if not self.root_dir.exists():
            return
        existing_dir_names = {child.name for child in self.root_dir.iterdir() if child.is_dir()}
        for child in sorted(self.root_dir.iterdir()):
            if not child.is_dir() or child.is_symlink():
                continue
            config_path = child / "amon.project.yaml"
            if not config_path.exists():
                continue
            child = self._migrate_legacy_project_dir(child, existing_dir_names)
            identity = load_project_config(child)
            self._id_to_path[identity.project_id] = child
            self._meta[identity.project_id] = {
                "project_id": identity.project_id,
                "project_name": identity.project_name,
                "project_path": str(child),
            }

    def _migrate_legacy_project_dir(self, project_path: Path, existing_dir_names: set[str]) -> Path:
        if not LEGACY_PROJECT_DIR_PATTERN.match(project_path.name):
            return project_path
        config_path = project_path / "amon.project.yaml"
        config = read_yaml(config_path)
        amon_config = config.setdefault("amon", {})
        project_name = str(amon_config.get("project_name") or "").strip() or project_path.name
        has_project_id = bool(str(amon_config.get("project_id") or "").strip())
        project_id = str(amon_config.get("project_id") or "").strip() or project_path.name
        if has_project_id and project_id != project_path.name:
            return project_path

        new_dir_name = self._build_slug(project_name, existing_dir_names)
        if not new_dir_name or new_dir_name == project_path.name:
            amon_config["project_id"] = project_id
            amon_config["project_slug"] = project_path.name
            write_yaml(config_path, config)
            return project_path

        destination = project_path.parent / new_dir_name
        if destination.exists():
            return project_path

        try:
            os.replace(project_path, destination)
        except OSError as exc:
            if self._logger is not None:
                self._logger.error("舊專案資料夾 migration 失敗：%s", exc, exc_info=True)
            return project_path

        migrated_config_path = destination / "amon.project.yaml"
        try:
            migrated_config = read_yaml(migrated_config_path)
            migrated_amon = migrated_config.setdefault("amon", {})
            migrated_amon["project_id"] = project_id
            migrated_amon["project_name"] = project_name
            migrated_amon["project_slug"] = destination.name
            write_yaml(migrated_config_path, migrated_config)
            self._ensure_legacy_alias(project_path, destination)
            existing_dir_names.discard(project_path.name)
            existing_dir_names.add(destination.name)
            return destination
        except OSError as exc:
            if self._logger is not None:
                self._logger.error("回寫 migration 設定失敗：%s", exc, exc_info=True)
            try:
                os.replace(destination, project_path)
            except OSError:
                if self._logger is not None:
                    self._logger.error("migration 回滾失敗：%s -> %s", destination, project_path, exc_info=True)
            return project_path

    def _ensure_legacy_alias(self, legacy_path: Path, target_path: Path) -> None:
        if legacy_path.exists():
            return
        try:
            legacy_path.symlink_to(target_path, target_is_directory=True)
        except OSError:
            return

    def _build_slug(self, project_name: str, existing_dir_names: set[str]) -> str:
        if self._slug_builder is not None:
            return self._slug_builder(project_name, existing_dir_names)
        base = project_name.strip().replace(" ", "-")
        cleaned = "".join(char for char in base if char.isalnum() or char in {"-", "_", "."})
        return cleaned or "project"

    def get_path(self, project_id: str) -> Path:
        project_path = self._id_to_path.get(project_id)
        if project_path is None:
            raise KeyError(f"找不到專案：{project_id}")
        return project_path

    def list_projects(self) -> list[dict[str, Any]]:
        return [self._meta[project_id] for project_id in sorted(self._meta.keys())]
