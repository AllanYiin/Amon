"""Confirmation queue persistence for runtime vNext."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from pathlib import Path
from typing import Any

from amon.storage.common import read_json, write_json


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ConfirmationRequest:
    id: str
    run_id: str
    node_id: str
    tool_name: str
    reason: str
    status: str = "pending"
    preview: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "node_id": self.node_id,
            "tool_name": self.tool_name,
            "reason": self.reason,
            "status": self.status,
            "preview": dict(self.preview),
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


class ConfirmationService:
    def __init__(self, project_path: Path) -> None:
        self.project_path = Path(project_path)

    def request(
        self,
        *,
        run_id: str,
        node_id: str,
        tool_name: str,
        reason: str,
        preview: dict[str, Any] | None = None,
    ) -> ConfirmationRequest:
        request = ConfirmationRequest(
            id=f"confirm-{uuid.uuid4().hex}",
            run_id=run_id,
            node_id=node_id,
            tool_name=tool_name,
            reason=reason,
            preview=dict(preview or {}),
        )
        write_json(self._confirmation_path(run_id, request.id), request.to_dict())
        return request

    def resolve(self, run_id: str, confirmation_id: str, *, approved: bool) -> ConfirmationRequest:
        payload = read_json(self._confirmation_path(run_id, confirmation_id), default={})
        request = ConfirmationRequest(
            id=str(payload.get("id") or confirmation_id),
            run_id=str(payload.get("run_id") or run_id),
            node_id=str(payload.get("node_id") or ""),
            tool_name=str(payload.get("tool_name") or ""),
            reason=str(payload.get("reason") or ""),
            status="approved" if approved else "rejected",
            preview=payload.get("preview") if isinstance(payload.get("preview"), dict) else {},
            created_at=str(payload.get("created_at") or _utc_now_iso()),
            resolved_at=_utc_now_iso(),
        )
        write_json(self._confirmation_path(run_id, confirmation_id), request.to_dict())
        return request

    def load_pending(self, run_id: str) -> list[ConfirmationRequest]:
        confirm_dir = self._run_dir(run_id) / "confirmations"
        if not confirm_dir.exists():
            return []
        results: list[ConfirmationRequest] = []
        for path in sorted(confirm_dir.glob("*.json")):
            payload = read_json(path, default={})
            if str(payload.get("status") or "pending") != "pending":
                continue
            results.append(
                ConfirmationRequest(
                    id=str(payload.get("id") or path.stem),
                    run_id=str(payload.get("run_id") or run_id),
                    node_id=str(payload.get("node_id") or ""),
                    tool_name=str(payload.get("tool_name") or ""),
                    reason=str(payload.get("reason") or ""),
                    status="pending",
                    preview=payload.get("preview") if isinstance(payload.get("preview"), dict) else {},
                    created_at=str(payload.get("created_at") or _utc_now_iso()),
                    resolved_at=payload.get("resolved_at"),
                )
            )
        return results

    def _confirmation_path(self, run_id: str, confirmation_id: str) -> Path:
        path = self._run_dir(run_id) / "confirmations" / f"{confirmation_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _run_dir(self, run_id: str) -> Path:
        return self.project_path / ".amon" / "runs" / run_id
