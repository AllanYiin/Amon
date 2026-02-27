"""Project-scoped log append helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .fs.atomic import append_jsonl
from .project_registry import ProjectRegistry


class ProjectLogStore:
    """Resolve project id to path, then append logs under <project>/.amon/logs/."""

    def __init__(self, *, data_dir: Path, registry: ProjectRegistry, logger: logging.Logger | None = None) -> None:
        self.data_dir = data_dir
        self.registry = registry
        self.logger = logger or logging.getLogger("amon.project_log_store")

    def append_app(self, payload: dict[str, Any]) -> bool:
        return self._append(project_id=str(payload.get("project_id") or ""), filename="app.jsonl", payload=payload)

    def append_event(self, payload: dict[str, Any]) -> bool:
        return self._append(project_id=str(payload.get("project_id") or ""), filename="events.jsonl", payload=payload)

    def append_billing(self, payload: dict[str, Any]) -> bool:
        return self._append(project_id=str(payload.get("project_id") or ""), filename="billing.jsonl", payload=payload)

    def project_log_path(self, project_id: str, filename: str) -> Path:
        project_path = self.resolve_project_path(project_id)
        return project_path / ".amon" / "logs" / filename

    def resolve_project_path(self, project_id: str) -> Path:
        normalized = project_id.strip()
        if not normalized:
            raise KeyError("project_id is empty")

        try:
            return self.registry.get_path(normalized)
        except KeyError:
            self.registry.scan()
        return self.registry.get_path(normalized)

    def _append(self, *, project_id: str, filename: str, payload: dict[str, Any]) -> bool:
        normalized = project_id.strip()
        if not normalized:
            return False
        try:
            log_path = self.project_log_path(normalized, filename)
        except KeyError:
            self.logger.warning("project log append skipped: unknown project_id=%s", normalized)
            return False
        append_jsonl(log_path, payload)
        return True
