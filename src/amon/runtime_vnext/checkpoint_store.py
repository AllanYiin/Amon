"""Checkpoint persistence helpers for runtime vNext."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amon.storage import RunRepository


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CheckpointStore:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.run_repo = RunRepository(self.project_root)

    def write(
        self,
        run_id: str,
        *,
        phase: str,
        node_id: str | None = None,
        status: str | None = None,
        payload: dict[str, Any] | None = None,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        selected_id = checkpoint_id or f"cp-{uuid.uuid4().hex}"
        body = {
            "checkpoint_id": selected_id,
            "phase": phase,
            "node_id": node_id,
            "status": status,
            "payload": dict(payload or {}),
            "ts": _utc_now_iso(),
        }
        path = self.run_repo.save_checkpoint_metadata(run_id, selected_id, body)
        return {**body, "path": str(path)}

    def load(self, run_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
        return self.run_repo.load_checkpoint_metadata(run_id, checkpoint_id=checkpoint_id)

