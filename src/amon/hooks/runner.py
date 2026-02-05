"""Hook execution runner."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from threading import Event
from uuid import uuid4

from amon.core import AmonCore
from amon.fs.atomic import atomic_write_text
from amon.events import emit_event
from amon.logging import log_event
from amon.tooling import load_tool_spec, validate_inputs_schema

from .matcher import match
from .state import HookStateStore
from .types import Hook
from .utils import render_template


logger = logging.getLogger(__name__)

ToolExecutor = Callable[..., dict[str, Any]]
GraphRunner = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


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


def _default_tool_executor(
    tool_name: str,
    args: dict[str, Any],
    project_id: str | None,
    *,
    timeout_s: int | None = None,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    core = AmonCore()
    core.ensure_base_structure()
    return core.run_tool(tool_name, args, project_id=project_id, timeout_s=timeout_s, cancel_event=cancel_event)


def _default_graph_runner(action_args: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    core = AmonCore()
    core.ensure_base_structure()
    project_id = action_args.get("project_id") or event.get("project_id")
    if not project_id:
        raise ValueError("graph.run 需要 project_id")
    graph_path_value = action_args.get("graph_path") or action_args.get("path")
    if not graph_path_value:
        raise ValueError("graph.run 需要 graph_path")
    variables = action_args.get("variables") or action_args.get("vars") or {}
    return _run_graph(core, project_id, graph_path_value, variables, event, action_args)


def _dedupe_key_for(hook: Hook, event: dict[str, Any]) -> str | None:
    if not hook.dedupe_key:
        return None
    rendered = render_template(hook.dedupe_key, event)
    return str(rendered) if rendered is not None else None


def process_event(
    event: dict[str, Any],
    *,
    tool_executor: ToolExecutor | None = None,
    graph_runner: GraphRunner | None = None,
    now: datetime | None = None,
    state_store: HookStateStore | None = None,
    data_dir: Path | None = None,
    allow_llm: bool = False,
    enqueue_action: Callable[[dict[str, Any]], str] | None = None,
) -> list[dict[str, Any]]:
    current_time = now or datetime.now().astimezone()
    store = state_store or HookStateStore(data_dir=data_dir)
    results: list[dict[str, Any]] = []
    enqueue = enqueue_action
    if enqueue is None:
        from amon.daemon.queue import enqueue_action as default_enqueue_action

        enqueue = default_enqueue_action

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
                _validate_tool_args(hook.action.tool, args, event, hook.hook_id)
                store.record_trigger(hook.hook_id, current_time, dedupe_key)
                action_id = enqueue(
                    {
                        "hook_id": hook.hook_id,
                        "action_type": hook.action.type,
                        "tool": hook.action.tool,
                        "action_args": args,
                        "event": event,
                        "allow_llm": allow_llm,
                    }
                )
                results.append({"hook_id": hook.hook_id, "status": "queued", "action_id": action_id})
            except Exception as exc:  # noqa: BLE001
                logger.error("Hook %s 佇列工具失敗：%s", hook.hook_id, exc, exc_info=True)
                results.append({"hook_id": hook.hook_id, "status": "failed", "error": str(exc)})
                store.decrement_inflight(hook.hook_id)
            continue

        if hook.action.type == "graph.run":
            store.increment_inflight(hook.hook_id)
            try:
                if not allow_llm:
                    _guard_llm_policy(args, event)
                store.record_trigger(hook.hook_id, current_time, dedupe_key)
                action_id = enqueue(
                    {
                        "hook_id": hook.hook_id,
                        "action_type": hook.action.type,
                        "action_args": args,
                        "event": event,
                        "allow_llm": allow_llm,
                    }
                )
                results.append({"hook_id": hook.hook_id, "status": "queued", "action_id": action_id})
            except Exception as exc:  # noqa: BLE001
                logger.error("Hook %s 佇列 graph 失敗：%s", hook.hook_id, exc, exc_info=True)
                results.append({"hook_id": hook.hook_id, "status": "failed", "error": str(exc)})
                store.decrement_inflight(hook.hook_id)
            continue

        results.append({"hook_id": hook.hook_id, "status": "skipped", "reason": "unsupported_action"})

    return results


def execute_hook_action(
    action: dict[str, Any],
    *,
    tool_executor: ToolExecutor | None = None,
    graph_runner: GraphRunner | None = None,
    state_store: HookStateStore | None = None,
    data_dir: Path | None = None,
    allow_llm: bool | None = None,
    cancel_event: Event | None = None,
) -> dict[str, Any]:
    store = state_store or HookStateStore(data_dir=data_dir)
    executor = tool_executor or _default_tool_executor
    runner = graph_runner or _default_graph_runner
    hook_id = str(action.get("hook_id") or "")
    action_type = str(action.get("action_type") or "")
    args = action.get("action_args") or {}
    event = action.get("event") or {}
    llm_allowed = allow_llm if allow_llm is not None else bool(action.get("allow_llm", False))

    timeout_s = _resolve_timeout(action)
    if cancel_event and cancel_event.is_set():
        return {"hook_id": hook_id, "status": "canceled"}

    try:
        if action_type == "tool.call":
            tool_name = str(action.get("tool") or "")
            if not tool_name:
                raise ValueError("tool.call 缺少 tool")
            _validate_tool_args(tool_name, args, event, hook_id)
            result = _call_tool_executor(
                executor,
                tool_name,
                args,
                event.get("project_id"),
                timeout_s=timeout_s,
                cancel_event=cancel_event,
            )
            log_event(
                {
                    "event": "hook_action_executed",
                    "hook_id": hook_id,
                    "action_type": action_type,
                    "event_id": event.get("event_id"),
                }
            )
            return {"hook_id": hook_id, "status": "executed", "result": result}
        if action_type == "graph.run":
            if not llm_allowed:
                _guard_llm_policy(args, event)
            result = runner(args, event)
            log_event(
                {
                    "event": "hook_action_executed",
                    "hook_id": hook_id,
                    "action_type": action_type,
                    "event_id": event.get("event_id"),
                    "run_id": result.get("run_id"),
                }
            )
            return {"hook_id": hook_id, "status": "executed", "result": result}
        return {"hook_id": hook_id, "status": "skipped", "reason": "unsupported_action"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Hook %s 執行 action 失敗：%s", hook_id, exc, exc_info=True)
        return {"hook_id": hook_id, "status": "failed", "error": str(exc)}
    finally:
        if hook_id:
            store.decrement_inflight(hook_id)


def _call_tool_executor(
    executor: ToolExecutor,
    tool_name: str,
    args: dict[str, Any],
    project_id: str | None,
    *,
    timeout_s: int,
    cancel_event: Event | None,
) -> dict[str, Any]:
    try:
        return executor(
            tool_name,
            args,
            project_id,
            timeout_s=timeout_s,
            cancel_event=cancel_event,
        )
    except TypeError:
        return executor(tool_name, args, project_id)


def _resolve_timeout(action: dict[str, Any]) -> int:
    raw = action.get("timeout_s") or action.get("tool_timeout_s")
    if raw is None:
        env_value = os.environ.get("AMON_TOOL_TIMEOUT") or os.environ.get("AMON_TOOL_TIMEOUT_S")
        raw = env_value
    try:
        timeout = int(raw) if raw is not None else 60
    except (TypeError, ValueError):
        timeout = 60
    return max(timeout, 1)


def _guard_llm_policy(action_args: dict[str, Any], event: dict[str, Any]) -> None:
    project_id = action_args.get("project_id") or event.get("project_id")
    graph_path_value = action_args.get("graph_path") or action_args.get("path")
    if not project_id or not graph_path_value:
        return
    core = AmonCore()
    core.ensure_base_structure()
    project_path = core.get_project_path(project_id)
    graph_path = (project_path / graph_path_value).expanduser() if not Path(graph_path_value).is_absolute() else Path(graph_path_value)
    try:
        graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("讀取 graph 失敗：%s", exc, exc_info=True)
        return
    nodes = graph_payload.get("nodes", [])
    for node in nodes:
        if node.get("type") == "agent_task" and not bool(node.get("allow_llm", False)):
            log_event(
                {
                    "level": "WARNING",
                    "event": "policy.llm_blocked",
                    "project_id": project_id,
                    "hook_action": "graph.run",
                    "graph_path": str(graph_path),
                    "node_id": node.get("id"),
                }
            )
            emit_event(
                {
                    "type": "policy.llm_blocked",
                    "scope": "policy",
                    "project_id": project_id,
                    "actor": "system",
                    "payload": {
                        "hook_action": "graph.run",
                        "graph_path": str(graph_path),
                        "node_id": node.get("id"),
                    },
                    "risk": "medium",
                }
            )
            raise PermissionError("graph node 使用 LLM 需 allow_llm=true")


def _validate_tool_args(tool_name: str, args: dict[str, Any], event: dict[str, Any], hook_id: str) -> None:
    project_id = event.get("project_id")
    core = AmonCore()
    core.ensure_base_structure()
    try:
        tool_dir, _, _ = core._resolve_tool_dir(tool_name, project_id)
    except Exception:
        fallback_dir = core.data_dir / "tools" / tool_name
        if (fallback_dir / "tool.py").exists():
            tool_dir = fallback_dir
        else:
            return
    try:
        spec = load_tool_spec(tool_dir)
    except Exception:
        return
    errors = validate_inputs_schema(spec.inputs_schema, args)
    if errors:
        emit_event(
            {
                "type": "tool.validation_failed",
                "scope": "tool",
                "project_id": project_id,
                "actor": "system",
                "payload": {
                    "tool_name": tool_name,
                    "hook_id": hook_id,
                    "event_id": event.get("event_id"),
                    "errors": errors,
                },
                "risk": "medium",
            }
        )
        raise ValueError("工具參數驗證失敗")


def _run_graph(
    core: AmonCore,
    project_id: str,
    graph_path_value: str,
    variables: dict[str, Any],
    event: dict[str, Any],
    action_args: dict[str, Any],
) -> dict[str, Any]:
    project_path = core.get_project_path(project_id)
    graph_path = (project_path / graph_path_value).expanduser() if not Path(graph_path_value).is_absolute() else Path(graph_path_value)
    run_id = uuid4().hex
    run_dir = project_path / ".amon" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trigger_payload = {
        "run_id": run_id,
        "hook_action": "graph.run",
        "hook_args": action_args,
        "event_id": event.get("event_id"),
        "event_type": event.get("type"),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    try:
        atomic_write_text(run_dir / "trigger.json", json.dumps(trigger_payload, ensure_ascii=False, indent=2))
    except OSError as exc:
        logger.error("寫入 trigger metadata 失敗：%s", exc, exc_info=True)
        raise
    log_event(
        {
            "event": "graph_triggered",
            "project_id": project_id,
            "run_id": run_id,
            "graph_path": str(graph_path),
            "event_id": event.get("event_id"),
        }
    )
    from amon.graph_runtime import GraphRuntime

    runtime = GraphRuntime(
        core=core,
        project_path=project_path,
        graph_path=graph_path,
        variables=variables,
        run_id=run_id,
    )
    result = runtime.run()
    return {"run_id": result.run_id, "run_dir": str(result.run_dir)}
