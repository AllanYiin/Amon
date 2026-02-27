from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import read_yaml, write_yaml


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
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self._id_to_path: dict[str, Path] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    def scan(self) -> None:
        self._id_to_path = {}
        self._meta = {}
        if not self.root_dir.exists():
            return
        for child in self.root_dir.iterdir():
            if not child.is_dir():
                continue
            config_path = child / "amon.project.yaml"
            if not config_path.exists():
                continue
            identity = load_project_config(child)
            self._id_to_path[identity.project_id] = child
            self._meta[identity.project_id] = {
                "project_id": identity.project_id,
                "project_name": identity.project_name,
                "project_path": str(child),
            }

    def get_path(self, project_id: str) -> Path:
        project_path = self._id_to_path.get(project_id)
        if project_path is None:
            raise KeyError(f"找不到專案：{project_id}")
        return project_path

    def list_projects(self) -> list[dict[str, Any]]:
        return [self._meta[project_id] for project_id in sorted(self._meta.keys())]
