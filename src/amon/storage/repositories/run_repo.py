from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.entities import RESUMABLE_RUN_STATUSES, RunRecord
from ..common import read_json, write_json
from ..migrations import bootstrap_manifest_storage


class RunRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.runs_dir = self.project_root / ".amon" / "runs"
        bootstrap_manifest_storage(project_root)

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def create(
        self,
        run: RunRecord,
        *,
        snapshot_manifest: dict[str, Any] | None = None,
        compiled_graph: dict[str, Any] | None = None,
    ) -> RunRecord:
        run_dir = self._run_dir(run.id)
        (run_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        (run_dir / "confirmations").mkdir(parents=True, exist_ok=True)
        write_json(run_dir / "run.json", run.to_dict())
        write_json(run_dir / "snapshot.manifest.json", snapshot_manifest or {})
        write_json(run_dir / "compiled.taskgraph.v3.json", compiled_graph or {})
        return run

    def save(self, run: RunRecord) -> RunRecord:
        write_json(self._run_dir(run.id) / "run.json", run.to_dict())
        return run

    def get(self, run_id: str) -> RunRecord:
        return RunRecord.from_dict(read_json(self._run_dir(run_id) / "run.json", default={}))

    def save_checkpoint_metadata(self, run_id: str, checkpoint_id: str, payload: dict[str, Any]) -> Path:
        path = self._run_dir(run_id) / "checkpoints" / f"{checkpoint_id}.json"
        write_json(path, payload)
        run = self.get(run_id)
        run.checkpoint_state = {"last_checkpoint_id": checkpoint_id, "path": str(path)}
        self.save(run)
        return path

    def load_checkpoint_metadata(self, run_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
        run = self.get(run_id)
        selected = checkpoint_id or str(run.checkpoint_state.get("last_checkpoint_id") or "")
        if not selected:
            return {}
        return read_json(self._run_dir(run_id) / "checkpoints" / f"{selected}.json", default={})

    def enqueue_confirmation(self, run_id: str, confirmation_id: str, payload: dict[str, Any]) -> Path:
        path = self._run_dir(run_id) / "confirmations" / f"{confirmation_id}.json"
        write_json(path, payload)
        run = self.get(run_id)
        if confirmation_id not in run.confirmation_queue:
            run.confirmation_queue.append(confirmation_id)
        self.save(run)
        return path

    def load_pending_confirmations(self, run_id: str) -> list[dict[str, Any]]:
        run = self.get(run_id)
        results: list[dict[str, Any]] = []
        for confirmation_id in run.confirmation_queue:
            results.append(read_json(self._run_dir(run_id) / "confirmations" / f"{confirmation_id}.json", default={}))
        return results

    def load_snapshot_manifest(self, run_id: str) -> dict[str, Any]:
        return read_json(self._run_dir(run_id) / "snapshot.manifest.json", default={})

    def list_resumable_runs(self) -> list[RunRecord]:
        results: list[RunRecord] = []
        for run_dir in sorted(self.runs_dir.iterdir()) if self.runs_dir.exists() else []:
            run_file = run_dir / "run.json"
            if not run_file.exists():
                continue
            run = RunRecord.from_dict(read_json(run_file, default={}))
            if run.status in RESUMABLE_RUN_STATUSES:
                results.append(run)
        return results
