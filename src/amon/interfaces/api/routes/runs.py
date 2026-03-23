"""Run routes for Stage 6 vNext workspace."""

from __future__ import annotations

from typing import Any

from amon.application import WorkspaceService
from amon.core import AmonCore


def create_run(core: AmonCore, task_manager, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    service = WorkspaceService(core, project_id)
    result = service.create_run(
        workflow_ref=str(payload.get("workflow_ref") or "").strip() or None,
        template_ref=str(payload.get("template_ref") or "").strip() or None,
        variables=payload.get("variables") if isinstance(payload.get("variables"), dict) else {},
        labels=payload.get("labels") if isinstance(payload.get("labels"), list) else [],
        notes=str(payload.get("notes") or "").strip() or None,
        pin=bool(payload.get("pin", False)),
    )
    execute = bool(payload.get("execute", False))
    request_id = None
    if execute:
        result["run"] = service.enqueue_run(result["run"]["id"])
        request_id = task_manager.submit_run(
            request_id=None,
            core=core,
            project_path=service.project_root,
            graph_path=result["graph_path"],
            variables=result["variables"],
            run_id=result["run"]["id"],
        )
    return {"run": result["run"], "request_id": request_id, "graph_path": result["graph_path"]}


def get_run(core: AmonCore, project_id: str, run_id: str) -> dict[str, Any]:
    return WorkspaceService(core, project_id).get_run(run_id)


def get_run_events(core: AmonCore, project_id: str, run_id: str) -> dict[str, Any]:
    return {"events": WorkspaceService(core, project_id).list_run_events(run_id)}


def resume_run(core: AmonCore, task_manager, project_id: str, run_id: str, *, execute: bool = True) -> dict[str, Any]:
    service = WorkspaceService(core, project_id)
    result = service.resume_run(run_id)
    request_id = None
    if execute:
        request_id = task_manager.submit_run(
            request_id=None,
            core=core,
            project_path=service.project_root,
            graph_path=result["graph_path"],
            variables=result["variables"],
            run_id=run_id,
        )
    return {"run": result["run"], "request_id": request_id, "checkpoint": result["checkpoint"]}


def cancel_run(core: AmonCore, project_id: str, run_id: str) -> dict[str, Any]:
    return {"run": WorkspaceService(core, project_id).cancel_run(run_id)}


def archive_run(core: AmonCore, project_id: str, run_id: str) -> dict[str, Any]:
    return {"run": WorkspaceService(core, project_id).archive_run(run_id)}
