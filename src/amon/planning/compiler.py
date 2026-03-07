"""TaskGraph v3 planning payload helpers."""

from __future__ import annotations

from typing import Any


class LegacyPlanCompilerRemovedError(RuntimeError):
    """Raised when callers attempt to use the removed legacy plan compiler path."""


def normalize_graph_definition_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate that planning payload already uses TaskGraph v3 GraphDefinition."""
    if not isinstance(payload, dict):
        raise TypeError("graph payload 必須是 dict")

    version = str(payload.get("version") or "")
    if version != "taskgraph.v3":
        raise LegacyPlanCompilerRemovedError(
            "僅支援 TaskGraph v3（version=taskgraph.v3）；legacy plan compiler 已移除。"
        )
    return payload
