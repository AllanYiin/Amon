"""Shared observability schema helpers."""

from __future__ import annotations

import uuid
from typing import Any

VIRTUAL_PROJECT_ID = "__virtual__"
CORRELATION_KEYS = ("project_id", "run_id", "node_id", "event_id", "request_id", "tool")


def normalize_project_id(project_id: str | None) -> str:
    """Return a project id compatible with observability schema."""
    value = str(project_id or "").strip()
    return value or VIRTUAL_PROJECT_ID


def ensure_correlation_fields(
    payload: dict[str, Any],
    *,
    project_id: str | None,
    run_id: str | None = None,
    node_id: str | None = None,
    request_id: str | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    """Ensure correlation keys exist on payload."""
    merged = dict(payload)
    merged["project_id"] = normalize_project_id(str(merged.get("project_id") or project_id or ""))
    merged.setdefault("run_id", run_id)
    merged.setdefault("node_id", node_id)
    merged.setdefault("request_id", request_id)
    merged.setdefault("tool", tool)
    merged.setdefault("event_id", uuid.uuid4().hex)
    return merged
