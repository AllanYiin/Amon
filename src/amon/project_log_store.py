from __future__ import annotations

from pathlib import Path
from typing import Any

from .fs.atomic import append_jsonl
from .fs.safety import canonicalize_path
from .project_registry import ProjectRegistry


class ProjectLogStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.projects_dir = data_dir / "projects"
        self.registry = ProjectRegistry(self.projects_dir)

    def project_logs_dir(self, project_id: str) -> Path:
        self.registry.scan()
        project_path = self.registry.get_path(project_id)
        logs_dir = project_path / ".amon" / "logs"
        canonicalize_path(logs_dir, [project_path])
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def append_event(self, project_id: str, payload: dict[str, Any]) -> None:
        logs_dir = self.project_logs_dir(project_id)
        append_jsonl(logs_dir / "events.jsonl", payload)

    def append_app(self, project_id: str, payload: dict[str, Any]) -> None:
        logs_dir = self.project_logs_dir(project_id)
        append_jsonl(logs_dir / "app.jsonl", payload)

    def read_events(self, project_id: str) -> list[dict[str, Any]]:
        logs_dir = self.project_logs_dir(project_id)
        path = logs_dir / "events.jsonl"
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                import json

                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def read_app(self, project_id: str) -> list[dict[str, Any]]:
        logs_dir = self.project_logs_dir(project_id)
        path = logs_dir / "app.jsonl"
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                import json

                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records
