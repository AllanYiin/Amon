from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import EntityTimestamps, copy_list, copy_mapping, utc_now_iso

RUN_STATUSES = {
    "created",
    "planning",
    "binding",
    "compiled",
    "queued",
    "dispatching",
    "running",
    "waiting_confirmation",
    "waiting_external",
    "paused",
    "retrying",
    "retry_wait",
    "repairing",
    "replanning",
    "succeeded",
    "failed",
    "failed_terminal",
    "cancelled",
    "abandoned",
    "rolled_back",
    "archived",
}

RESUMABLE_RUN_STATUSES = {
    "queued",
    "dispatching",
    "running",
    "waiting_confirmation",
    "waiting_external",
    "paused",
    "retrying",
    "retry_wait",
    "repairing",
    "replanning",
}


@dataclass
class RunRecord(EntityTimestamps):
    id: str = ""
    workflow_ref: str | None = None
    template_ref: str | None = None
    status: str = "created"
    trigger: dict[str, Any] = field(default_factory=dict)
    snapshot_refs: dict[str, Any] = field(default_factory=dict)
    checkpoint_state: dict[str, Any] = field(default_factory=dict)
    confirmation_queue: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)
    pin: bool = False
    notes: str | None = None

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        workflow_ref: str | None = None,
        template_ref: str | None = None,
        trigger: dict[str, Any] | None = None,
        snapshot_refs: dict[str, Any] | None = None,
        checkpoint_state: dict[str, Any] | None = None,
        confirmation_queue: list[str] | None = None,
        status: str = "created",
        metadata: dict[str, Any] | None = None,
        labels: list[str] | None = None,
        pin: bool = False,
        notes: str | None = None,
    ) -> "RunRecord":
        return cls(
            id=run_id,
            workflow_ref=workflow_ref,
            template_ref=template_ref,
            status=status,
            trigger=copy_mapping(trigger),
            snapshot_refs=copy_mapping(snapshot_refs),
            checkpoint_state=copy_mapping(checkpoint_state),
            confirmation_queue=copy_list(confirmation_queue),
            metadata=copy_mapping(metadata),
            labels=copy_list(labels),
            pin=pin,
            notes=notes,
        )

    def update_metadata(
        self,
        *,
        metadata: dict[str, Any] | None = None,
        labels: list[str] | None = None,
        pin: bool | None = None,
        notes: str | None = None,
    ) -> "RunRecord":
        if metadata is not None:
            self.metadata = copy_mapping(metadata)
        if labels is not None:
            self.labels = copy_list(labels)
        if pin is not None:
            self.pin = pin
        if notes is not None:
            self.notes = notes
        self.touch()
        return self

    def mark_status(self, status: str) -> "RunRecord":
        if status not in RUN_STATUSES:
            raise ValueError(f"不合法的 run status：{status}")
        self.status = status
        if status in {"dispatching", "running", "repairing", "replanning", "retrying"} and self.started_at is None:
            self.started_at = utc_now_iso()
        if status in {"succeeded", "failed", "failed_terminal", "cancelled", "rolled_back", "archived", "abandoned"}:
            self.finished_at = utc_now_iso()
        self.touch()
        return self

    def archive(self) -> "RunRecord":
        return self.mark_status("archived")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_ref": self.workflow_ref,
            "template_ref": self.template_ref,
            "status": self.status,
            "trigger": copy_mapping(self.trigger),
            "snapshot_refs": copy_mapping(self.snapshot_refs),
            "checkpoint_state": copy_mapping(self.checkpoint_state),
            "confirmation_queue": copy_list(self.confirmation_queue),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "metadata": copy_mapping(self.metadata),
            "labels": copy_list(self.labels),
            "pin": self.pin,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunRecord":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            workflow_ref=payload.get("workflow_ref"),
            template_ref=payload.get("template_ref"),
            status=str(payload.get("status") or "created"),
            trigger=copy_mapping(payload.get("trigger")),
            snapshot_refs=copy_mapping(payload.get("snapshot_refs")),
            checkpoint_state=copy_mapping(payload.get("checkpoint_state")),
            confirmation_queue=copy_list(payload.get("confirmation_queue")),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            metadata=copy_mapping(payload.get("metadata")),
            labels=copy_list(payload.get("labels")),
            pin=bool(payload.get("pin", False)),
            notes=payload.get("notes"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if entity.status not in RUN_STATUSES:
            raise ValueError(f"不合法的 run status：{entity.status}")
        return entity
