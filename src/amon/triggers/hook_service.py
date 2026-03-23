"""Hook trigger service that produces standard run requests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from amon.application.workspace_service import WorkspaceService
from amon.core import AmonCore

from .backpressure import check_backpressure


def submit_hook_run_request(
    *,
    hook_id: str,
    action_args: dict[str, Any],
    event: dict[str, Any],
    data_dir: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    project_id = str(action_args.get("project_id") or event.get("project_id") or "").strip()
    workflow_ref = str(action_args.get("workflow_ref") or "").strip() or None
    template_ref = str(action_args.get("template_ref") or "").strip() or None
    if not project_id:
        raise ValueError("run.request 缺少 project_id")
    if not workflow_ref and not template_ref:
        raise ValueError("run.request 需要 workflow_ref 或 template_ref")

    core = AmonCore(data_dir=data_dir)
    core.ensure_base_structure()
    workspace = WorkspaceService(core, project_id)
    max_active_runs = _read_int(action_args.get("max_active_runs"))
    max_queue_depth = _read_int(action_args.get("max_queue_depth"))
    decision = check_backpressure(
        workspace.project_root,
        trigger_kind="hook",
        trigger_id=hook_id,
        max_active_runs=max_active_runs,
        max_queue_depth=max_queue_depth,
    )
    if not decision.allowed:
        return {
            "status": "blocked",
            "reason": decision.reason,
            "active_runs": decision.active_runs,
        }

    variables = dict(action_args.get("variables") or {})
    variables.setdefault("trigger_event", event)
    variables.setdefault("trigger_payload", dict(event.get("payload") or {}))
    run_payload = workspace.create_run(
        workflow_ref=workflow_ref,
        template_ref=template_ref,
        variables=variables,
        labels=list(action_args.get("labels") or []),
        notes=action_args.get("notes"),
        pin=bool(action_args.get("pin", False)),
        trigger={
            "kind": "hook",
            "id": hook_id,
            "event_id": event.get("event_id"),
            "event_type": event.get("type"),
            "source": "hook",
        },
    )
    queued_run = workspace.enqueue_run(str(run_payload["run"]["id"]))
    return {"status": "queued", "run": queued_run}


def _read_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
