"""Job trigger service that converts job events into standard run requests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from amon.application.workspace_service import WorkspaceService
from amon.config import read_yaml
from amon.core import AmonCore
from amon.hooks.utils import render_template

from .backpressure import check_backpressure
from .dedupe import TriggerDedupeStore


def submit_job_run_request(
    event: dict[str, Any],
    *,
    data_dir: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    payload = dict(event.get("payload") or {})
    job_id = str(payload.get("job_id") or "").strip()
    if not job_id:
        return None

    core = AmonCore(data_dir=data_dir)
    core.ensure_base_structure()
    config = _load_job_config(core.data_dir, job_id)
    run_request = dict(config.get("run_request") or {})
    if not run_request:
        return None

    rendered = render_template(run_request, event)
    project_id = str(rendered.get("project_id") or "").strip()
    workflow_ref = str(rendered.get("workflow_ref") or "").strip() or None
    template_ref = str(rendered.get("template_ref") or rendered.get("template_id") or "").strip() or None
    if not project_id or (not workflow_ref and not template_ref):
        return None

    workspace = WorkspaceService(core, project_id)
    dedupe_key = str(
        rendered.get("dedupe_key")
        or event.get("event_id")
        or payload.get("path")
        or job_id
    )
    store = TriggerDedupeStore(core.data_dir)
    cooldown_seconds = _read_int(rendered.get("cooldown_seconds"))
    if store.is_duplicate("job", job_id, dedupe_key, cooldown_seconds=cooldown_seconds, now=now):
        return {"status": "deduplicated", "job_id": job_id}

    decision = check_backpressure(
        workspace.project_root,
        trigger_kind="job",
        trigger_id=job_id,
        max_active_runs=_read_int(rendered.get("max_active_runs")),
        max_queue_depth=_read_int(rendered.get("max_queue_depth")),
    )
    if not decision.allowed:
        return {
            "status": "blocked",
            "reason": decision.reason,
            "job_id": job_id,
            "active_runs": decision.active_runs,
        }

    variables = dict(rendered.get("variables") or {})
    variables.setdefault("trigger_event", event)
    variables.setdefault("trigger_payload", payload)
    run_payload = workspace.create_run(
        workflow_ref=workflow_ref,
        template_ref=template_ref,
        variables=variables,
        labels=list(rendered.get("labels") or []),
        notes=rendered.get("notes"),
        pin=bool(rendered.get("pin", False)),
        trigger={
            "kind": "job",
            "id": job_id,
            "event_id": event.get("event_id"),
            "event_type": event.get("type"),
            "source": "job",
        },
    )
    store.record("job", job_id, dedupe_key, now=now)
    queued_run = workspace.enqueue_run(str(run_payload["run"]["id"]))
    return {"status": "queued", "run": queued_run}


def _load_job_config(data_dir: Path, job_id: str) -> dict[str, Any]:
    path = data_dir / "jobs" / f"{job_id}.yaml"
    payload = read_yaml(path)
    if not isinstance(payload, dict):
        raise ValueError("job 設定必須為物件")
    return payload


def _read_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
