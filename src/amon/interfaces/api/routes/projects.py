"""Project routes for Stage 6 vNext workspace."""

from __future__ import annotations

from typing import Any

from amon.application import WorkspaceService
from amon.core import AmonCore


def list_projects(core: AmonCore, *, include_deleted: bool = False) -> dict[str, Any]:
    records = core.list_projects(include_deleted=include_deleted)
    if not records:
        return {"projects": []}
    return {"projects": WorkspaceService(core, records[0].project_id).list_projects(include_deleted=include_deleted)}


def get_project_summary(core: AmonCore, project_id: str) -> dict[str, Any]:
    return WorkspaceService(core, project_id).get_project_summary()


def create_project(core: AmonCore, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("請提供專案名稱")
    record = core.create_project(name)
    WorkspaceService(core, record.project_id)
    return {"project": record.to_dict()}


def update_project(core: AmonCore, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    description = payload.get("description")
    defaults = payload.get("defaults")
    if not name:
        raise ValueError("請提供新的專案名稱")
    record = core.update_project_name(project_id, name)
    service = WorkspaceService(core, project_id)
    project = service.project_repo.load()
    project.update(
        name=name,
        description=description if isinstance(description, str) else project.description,
        defaults=defaults if isinstance(defaults, dict) else project.defaults,
    )
    service.project_repo.save(project)
    return {"project": record.to_dict(), "manifest_project": project.to_dict()}


def delete_project(core: AmonCore, project_id: str) -> dict[str, Any]:
    service = WorkspaceService(core, project_id)
    record = core.delete_project(project_id)
    project = service.project_repo.soft_delete()
    return {"project": record.to_dict(), "manifest_project": project.to_dict()}


def restore_project(core: AmonCore, project_id: str) -> dict[str, Any]:
    record = core.restore_project(project_id)
    service = WorkspaceService(core, project_id)
    project = service.project_repo.restore()
    return {"project": record.to_dict(), "manifest_project": project.to_dict()}
