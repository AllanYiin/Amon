"""Upload routes for Stage 6 vNext workspace."""

from __future__ import annotations

from typing import Any

from amon.application import WorkspaceService
from amon.core import AmonCore


def list_uploads(core: AmonCore, project_id: str) -> dict[str, Any]:
    return {"uploads": WorkspaceService(core, project_id).list_uploads()}


def create_upload(core: AmonCore, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    source_path = str(payload.get("source_path") or "").strip()
    if not source_path:
        raise ValueError("請提供 source_path")
    notes = str(payload.get("notes") or "").strip() or None
    return {"upload": WorkspaceService(core, project_id).create_upload(source_path, notes=notes)}


def get_upload(core: AmonCore, project_id: str, asset_id: str) -> dict[str, Any]:
    return {"upload": WorkspaceService(core, project_id).get_upload(asset_id)}


def get_upload_preview(core: AmonCore, project_id: str, asset_id: str) -> dict[str, Any]:
    return WorkspaceService(core, project_id).get_upload_preview(asset_id)


def update_upload(core: AmonCore, project_id: str, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"upload": WorkspaceService(core, project_id).update_upload(asset_id, payload)}


def delete_upload(core: AmonCore, project_id: str, asset_id: str) -> dict[str, Any]:
    return {"upload": WorkspaceService(core, project_id).delete_upload(asset_id)}
