"""Persistent confirmation queue adapter for Stage 5."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amon.storage import RunRepository
from amon.storage.common import read_json


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ConfirmationQueue:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.run_repo = RunRepository(self.project_root)

    def enqueue(
        self,
        run_id: str,
        *,
        tool_name: str,
        reason: str,
        preview: dict[str, Any] | None = None,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        selected_id = confirmation_id or f"confirm-{uuid.uuid4().hex}"
        payload = {
            "id": selected_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "reason": reason,
            "preview": dict(preview or {}),
            "status": "pending",
            "created_at": _utc_now_iso(),
        }
        self.run_repo.enqueue_confirmation(run_id, selected_id, payload)
        return payload

    def list_pending(self, run_id: str) -> list[dict[str, Any]]:
        return self.run_repo.load_pending_confirmations(run_id)

    def resolve(self, run_id: str, confirmation_id: str, *, approved: bool) -> dict[str, Any]:
        path = self.project_root / ".amon" / "runs" / run_id / "confirmations" / f"{confirmation_id}.json"
        payload = read_json(path, default={})
        payload["status"] = "approved" if approved else "rejected"
        payload["resolved_at"] = _utc_now_iso()
        self.run_repo.enqueue_confirmation(run_id, confirmation_id, payload)
        return payload
