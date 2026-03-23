"""Schedule trigger service that creates standard run requests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from amon.application.workspace_service import WorkspaceService
from amon.core import AmonCore

from .backpressure import check_backpressure
from .dedupe import TriggerDedupeStore


def submit_schedule_run_request(
    event: dict[str, Any],
    *,
    data_dir: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    payload = dict(event.get("payload") or {})
    project_id = str(payload.get("project_id") or "").strip()
    workflow_ref = str(payload.get("workflow_ref") or "").strip() or None
    template_ref = str(payload.get("template_id") or payload.get("template_ref") or "").strip() or None
    schedule_id = str(payload.get("schedule_id") or "").strip()
    if not schedule_id or not project_id or (not workflow_ref and not template_ref):
        return None

    cooldown_seconds = _read_int(payload.get("cooldown_seconds"))
    dedupe_key = str(payload.get("event_id") or payload.get("scheduled_for") or schedule_id)
    core = AmonCore(data_dir=data_dir)
    core.ensure_base_structure()
    workspace = WorkspaceService(core, project_id)
    store = TriggerDedupeStore(core.data_dir)
    if store.is_duplicate("schedule", schedule_id, dedupe_key, cooldown_seconds=cooldown_seconds, now=now):
        return {"status": "deduplicated", "schedule_id": schedule_id}

    decision = check_backpressure(
        workspace.project_root,
        trigger_kind="schedule",
        trigger_id=schedule_id,
        max_active_runs=_read_int(payload.get("max_active_runs")),
        max_queue_depth=_read_int(payload.get("max_queue_depth")),
    )
    if not decision.allowed:
        return {
            "status": "blocked",
            "reason": decision.reason,
            "schedule_id": schedule_id,
            "active_runs": decision.active_runs,
        }

    variables = dict(payload.get("vars") or {})
    variables.setdefault("trigger_event", event)
    variables.setdefault("scheduled_for", payload.get("scheduled_for"))
    run_payload = workspace.create_run(
        workflow_ref=workflow_ref,
        template_ref=template_ref,
        variables=variables,
        trigger={
            "kind": "schedule",
            "id": schedule_id,
            "event_id": event.get("event_id"),
            "event_type": event.get("type"),
            "source": "schedule",
        },
    )
    store.record("schedule", schedule_id, dedupe_key, now=now)
    queued_run = workspace.enqueue_run(str(run_payload["run"]["id"]))
    return {"status": "queued", "run": queued_run}


def _read_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
