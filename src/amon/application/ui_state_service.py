"""UI state persistence helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from amon.storage import ProjectRepository


class UIStateService:
    def __init__(self, project_root: Path) -> None:
        self.project_repo = ProjectRepository(Path(project_root))

    def load(self) -> dict[str, Any]:
        return self.project_repo.load_ui_state()

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        current.update(payload)
        self.project_repo.save_ui_state(current)
        return current

    def update_recent_run(self, run_id: str | None) -> dict[str, Any]:
        return self.save({"recent_run_id": run_id})

    def update_recent_preview(self, preview_id: str | None) -> dict[str, Any]:
        return self.save({"recent_preview_id": preview_id})

    def update_pending_confirmations(self, confirmation_ids: list[str]) -> dict[str, Any]:
        return self.save({"pending_confirmation_ids": list(confirmation_ids)})
