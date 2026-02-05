"""Hook execution runner."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from amon.core import AmonCore

from .matcher import match
from .state import HookStateStore
from .types import Hook
from .utils import render_template


logger = logging.getLogger(__name__)

ToolExecutor = Callable[[str, dict[str, Any], str | None], dict[str, Any]]


def _resolve_hooks_dir(data_dir: Path | None = None) -> Path:
    if data_dir:
        return data_dir / "hooks"
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser() / "hooks"
    return Path("~/.amon").expanduser() / "hooks"


def _append_pending_action(hook: Hook, event: dict[str, Any], action_args: dict[str, Any], data_dir: Path | None = None) -> None:
    hooks_dir = _resolve_hooks_dir(data_dir)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hook_id": hook.hook_id,
        "event_id": event.get("event_id"),
        "event_type": event.get("type"),
        "action": {
            "type": hook.action.type,
            "tool": hook.action.tool,
            "args": action_args,
        },
        "status": "pending",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    pending_path = hooks_dir / "pending_actions.jsonl"
    with pending_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _default_tool_executor(tool_name: str, args: dict[str, Any], project_id: str | None) -> dict[str, Any]:
    core = AmonCore()
    core.ensure_base_structure()
    return core.run_tool(tool_name, args, project_id=project_id)


def _dedupe_key_for(hook: Hook, event: dict[str, Any]) -> str | None:
    if not hook.dedupe_key:
        return None
    rendered = render_template(hook.dedupe_key, event)
    return str(rendered) if rendered is not None else None


def process_event(
    event: dict[str, Any],
    *,
    tool_executor: ToolExecutor | None = None,
    now: datetime | None = None,
    state_store: HookStateStore | None = None,
    data_dir: Path | None = None,
) -> list[dict[str, Any]]:
    current_time = now or datetime.now().astimezone()
    store = state_store or HookStateStore(data_dir=data_dir)
    executor = tool_executor or _default_tool_executor
    results: list[dict[str, Any]] = []

    for hook in match(event, now=current_time, state_store=store):
        args = render_template(hook.action.args or {}, event)
        dedupe_key = _dedupe_key_for(hook, event)
        if hook.policy.require_confirm:
            _append_pending_action(hook, event, args, data_dir=data_dir)
            store.record_trigger(hook.hook_id, current_time, dedupe_key)
            results.append({"hook_id": hook.hook_id, "status": "pending"})
            continue

        if hook.action.type == "tool.call" and hook.action.tool:
            store.increment_inflight(hook.hook_id)
            try:
                result = executor(hook.action.tool, args, event.get("project_id"))
                results.append({"hook_id": hook.hook_id, "status": "executed", "result": result})
            except Exception as exc:  # noqa: BLE001
                logger.error("Hook %s 執行工具失敗：%s", hook.hook_id, exc, exc_info=True)
                results.append({"hook_id": hook.hook_id, "status": "failed", "error": str(exc)})
            finally:
                store.decrement_inflight(hook.hook_id)
                store.record_trigger(hook.hook_id, current_time, dedupe_key)
        else:
            results.append({"hook_id": hook.hook_id, "status": "skipped", "reason": "unsupported_action"})

    return results
