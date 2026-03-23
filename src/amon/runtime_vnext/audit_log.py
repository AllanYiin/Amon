"""Runtime vNext audit trail for tool invocation records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amon.fs.atomic import append_jsonl


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ToolAuditRecord:
    run_id: str
    node_id: str
    tool_name: str
    invocation_mode: str
    selected_by: str
    approval_state: str
    side_effect_class: str
    replayable: bool = True
    request_id: str | None = None
    thread_id: str | None = None
    payload_preview: dict[str, Any] | None = None
    ts: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "run_id": self.run_id,
            "node_id": self.node_id,
            "tool_name": self.tool_name,
            "invocation_mode": self.invocation_mode,
            "selected_by": self.selected_by,
            "approval_state": self.approval_state,
            "side_effect_class": self.side_effect_class,
            "replayable": self.replayable,
            "request_id": self.request_id,
            "thread_id": self.thread_id,
            "payload_preview": self.payload_preview,
        }


class RuntimeAuditLog:
    def __init__(self, project_path: Path) -> None:
        self.project_path = Path(project_path)

    def record_tool_call(self, record: ToolAuditRecord) -> Path:
        path = self._audit_path(record.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        append_jsonl(path, record.to_dict())
        return path

    def _audit_path(self, run_id: str) -> Path:
        return self.project_path / ".amon" / "runs" / run_id / "tool_audit.jsonl"
