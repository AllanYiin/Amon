from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...config import write_yaml
from ...domain.entities import Project
from ..common import read_json, write_json
from ..migrations import bootstrap_manifest_storage


@dataclass
class ProjectResumeSnapshot:
    project: Project
    ui_state: dict[str, Any]
    resumable_runs: list[dict[str, Any]]


class ProjectRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.amon_dir = self.project_root / ".amon"
        self.project_file = self.amon_dir / "project.json"
        self.ui_state_file = self.amon_dir / "ui_state.json"

    def create(self, project: Project) -> Project:
        bootstrap_manifest_storage(self.project_root, project=project)
        self.save(project)
        self.save_ui_state(
            {
                "recent_project_id": project.id,
                "recent_run_id": None,
                "recent_preview_id": None,
                "pending_confirmation_ids": [],
            }
        )
        write_yaml(
            self.project_root / "amon.project.yaml",
            {
                "amon": {
                    "project_id": project.id,
                    "project_name": project.name,
                    "project_root": str(self.project_root),
                }
            },
        )
        return project

    def save(self, project: Project) -> Project:
        write_json(self.project_file, project.to_dict())
        return project

    def load(self) -> Project:
        return Project.from_dict(read_json(self.project_file, default={}))

    def update(self, **changes: Any) -> Project:
        project = self.load()
        project.update(**changes)
        return self.save(project)

    def soft_delete(self) -> Project:
        project = self.load().soft_delete()
        return self.save(project)

    def restore(self) -> Project:
        project = self.load().restore()
        return self.save(project)

    def save_ui_state(self, payload: dict[str, Any]) -> None:
        write_json(self.ui_state_file, payload)

    def load_ui_state(self) -> dict[str, Any]:
        return read_json(
            self.ui_state_file,
            default={
                "recent_project_id": None,
                "recent_run_id": None,
                "recent_preview_id": None,
                "pending_confirmation_ids": [],
            },
        )

    def load_resume_snapshot(self) -> ProjectResumeSnapshot:
        runs_dir = self.amon_dir / "runs"
        resumable_runs: list[dict[str, Any]] = []
        for run_dir in sorted(runs_dir.iterdir()) if runs_dir.exists() else []:
            run_file = run_dir / "run.json"
            if not run_file.exists():
                continue
            payload = read_json(run_file, default={})
            status = str(payload.get("status") or "")
            if status in {"queued", "running", "waiting_confirmation", "paused", "retrying"}:
                resumable_runs.append(payload)
        return ProjectResumeSnapshot(project=self.load(), ui_state=self.load_ui_state(), resumable_runs=resumable_runs)
