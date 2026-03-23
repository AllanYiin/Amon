"""Definition routes for Stage 6 vNext workspace."""

from __future__ import annotations

from typing import Any

from amon.application import WorkspaceService
from amon.core import AmonCore


def list_definitions(core: AmonCore, project_id: str, definition_kind: str) -> dict[str, Any]:
    return {definition_kind: WorkspaceService(core, project_id).list_definitions(definition_kind)}


def create_definition(core: AmonCore, project_id: str, definition_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"definition": WorkspaceService(core, project_id).create_definition(definition_kind, payload)}


def get_definition(core: AmonCore, project_id: str, definition_kind: str, entity_id: str) -> dict[str, Any]:
    return {"definition": WorkspaceService(core, project_id).get_definition(definition_kind, entity_id)}


def update_definition(
    core: AmonCore,
    project_id: str,
    definition_kind: str,
    entity_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {"definition": WorkspaceService(core, project_id).update_definition(definition_kind, entity_id, payload)}


def delete_definition(core: AmonCore, project_id: str, definition_kind: str, entity_id: str) -> dict[str, Any]:
    return {"definition": WorkspaceService(core, project_id).delete_definition(definition_kind, entity_id)}
