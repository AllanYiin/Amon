"""Run/project resume loading for Stage 5."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amon.domain import RunRecord
from amon.storage import ProjectRepository, RunRepository


@dataclass(frozen=True)
class RunResumeBundle:
    run: RunRecord
    checkpoint: dict[str, Any]
    confirmations: list[dict[str, Any]]
    snapshot_manifest: dict[str, Any]
    compiled_graph: dict[str, Any]


class ResumeService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.project_repo = ProjectRepository(self.project_root)
        self.run_repo = RunRepository(self.project_root)

    def load_project_resume(self):
        return self.project_repo.load_resume_snapshot()

    def restore_run(self, run_id: str) -> RunResumeBundle:
        run = self.run_repo.get(run_id)
        return RunResumeBundle(
            run=run,
            checkpoint=self.run_repo.load_checkpoint_metadata(run_id),
            confirmations=self.run_repo.load_pending_confirmations(run_id),
            snapshot_manifest=self.run_repo.load_snapshot_manifest(run_id),
            compiled_graph=self.run_repo.load_compiled_graph(run_id),
        )

    def mark_restore_failed(self, run_id: str, *, reason: str) -> RunRecord:
        run = self.run_repo.get(run_id)
        run.mark_status("paused")
        metadata = dict(run.metadata)
        metadata["restore_error"] = reason
        run.update_metadata(metadata=metadata)
        return self.run_repo.save(run)
