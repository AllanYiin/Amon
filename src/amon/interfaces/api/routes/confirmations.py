"""Confirmation routes for Stage 6 vNext workspace."""

from __future__ import annotations

from amon.application import WorkspaceService
from amon.core import AmonCore


def list_confirmations(core: AmonCore, project_id: str, *, run_id: str | None = None) -> dict[str, object]:
    return {"confirmations": WorkspaceService(core, project_id).list_confirmations(run_id=run_id)}


def approve_confirmation(core: AmonCore, project_id: str, confirmation_id: str) -> dict[str, object]:
    return {"confirmation": WorkspaceService(core, project_id).resolve_confirmation(confirmation_id, approved=True)}


def reject_confirmation(core: AmonCore, project_id: str, confirmation_id: str) -> dict[str, object]:
    return {"confirmation": WorkspaceService(core, project_id).resolve_confirmation(confirmation_id, approved=False)}
