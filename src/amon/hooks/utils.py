"""Hook utilities."""

from __future__ import annotations

import re
from typing import Any


_TEMPLATE_RE = re.compile(r"\{\{\s*event\.([a-zA-Z0-9_\.]+)\s*\}\}")


def resolve_event_path(event: dict[str, Any], path: str) -> Any:
    cursor: Any = event
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return ""
        cursor = cursor[part]
    return cursor


def render_template(value: Any, event: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: render_template(val, event) for key, val in value.items()}
    if isinstance(value, list):
        return [render_template(item, event) for item in value]
    if not isinstance(value, str):
        return value

    matches = list(_TEMPLATE_RE.finditer(value))
    if not matches:
        return value
    if len(matches) == 1 and matches[0].span() == (0, len(value)):
        return resolve_event_path(event, matches[0].group(1))

    rendered = value
    for match in matches:
        replacement = resolve_event_path(event, match.group(1))
        rendered = rendered.replace(match.group(0), str(replacement))
    return rendered
