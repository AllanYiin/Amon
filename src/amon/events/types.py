"""Known event type names for observability and integration contracts."""

from __future__ import annotations

EXECUTION_MODE_DECISION = "execution_mode_decision"
PLAN_GENERATED = "plan_generated"
PLAN_COMPILED = "plan_compiled"
TOOL_DISPATCH = "tool_dispatch"

KNOWN_EVENT_TYPES = {
    EXECUTION_MODE_DECISION,
    PLAN_GENERATED,
    PLAN_COMPILED,
    TOOL_DISPATCH,
}


__all__ = [
    "EXECUTION_MODE_DECISION",
    "PLAN_GENERATED",
    "PLAN_COMPILED",
    "TOOL_DISPATCH",
    "KNOWN_EVENT_TYPES",
]
