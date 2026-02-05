"""Hook matcher."""

from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from typing import Any

from .loader import load_hooks
from .state import HookStateStore
from .types import Hook
from .utils import render_template


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _ensure_now(now: datetime | None) -> datetime:
    if now:
        return now
    return datetime.now().astimezone()


def _event_value(event: dict[str, Any], key: str) -> Any:
    if key in event:
        return event[key]
    payload = event.get("payload")
    if isinstance(payload, dict):
        return payload.get(key)
    return None


def _match_filters(hook: Hook, event: dict[str, Any]) -> bool:
    if hook.filters.ignore_actors and event.get("actor") in hook.filters.ignore_actors:
        return False

    if hook.filters.path_glob:
        path = _event_value(event, "path")
        if not path or not fnmatch.fnmatch(str(path), hook.filters.path_glob):
            return False

    if hook.filters.min_size is not None:
        size = _event_value(event, "size")
        try:
            size_val = int(size)
        except (TypeError, ValueError):
            return False
        if size_val < hook.filters.min_size:
            return False

    if hook.filters.mime:
        mime = _event_value(event, "mime")
        if not mime:
            return False
        if hook.filters.mime.endswith("/*"):
            if not str(mime).startswith(hook.filters.mime[:-1]):
                return False
        elif str(mime) != hook.filters.mime:
            return False

    return True


def _dedupe_key_for(hook: Hook, event: dict[str, Any]) -> str | None:
    if not hook.dedupe_key:
        return None
    rendered = render_template(hook.dedupe_key, event)
    return str(rendered) if rendered is not None else None


def match(event: dict[str, Any], now: datetime | None = None, state_store: HookStateStore | None = None) -> list[Hook]:
    hooks = load_hooks()
    if not hooks:
        return []
    current_time = _ensure_now(now)
    store = state_store or HookStateStore()
    matches: list[Hook] = []

    event_type = event.get("type")
    for hook in hooks:
        if not hook.enabled:
            continue
        if event_type not in hook.event_types:
            continue
        if not _match_filters(hook, event):
            continue

        state = store.get_hook_state(hook.hook_id)
        if hook.max_concurrency is not None and int(state.get("inflight", 0)) >= hook.max_concurrency:
            continue

        if hook.cooldown_seconds:
            last_triggered = _parse_iso(state.get("last_triggered_at"))
            if last_triggered and (current_time - last_triggered).total_seconds() < hook.cooldown_seconds:
                continue

        dedupe_key = _dedupe_key_for(hook, event)
        if dedupe_key:
            dedupe_state = state.get("dedupe", {})
            last_seen = _parse_iso(dedupe_state.get(dedupe_key))
            if last_seen:
                if hook.cooldown_seconds:
                    if (current_time - last_seen).total_seconds() < hook.cooldown_seconds:
                        continue
                else:
                    continue

        matches.append(hook)

    return matches
