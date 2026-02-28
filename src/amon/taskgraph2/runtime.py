"""TaskGraph 2.0 DAG runtime (minimal LLM single-pass execution)."""

from __future__ import annotations

import json
import threading
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from amon.fs.atomic import append_jsonl, atomic_write_text
from amon.sandbox.path_rules import validate_relative_path
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolCall, ToolResult

from .llm import TaskGraphLLMClient, build_default_llm_client
from .schema import TaskEdge, TaskGraph, TaskNode, validate_task_graph
from .serialize import dumps_task_graph

_ALLOWED_OUTPUT_PREFIXES = ("docs/", "audits/")


@dataclass
class TaskGraphRunResult:
    run_id: str
    run_dir: Path
    state: dict[str, Any]


@dataclass
class _NodeExecutionFailed(Exception):
    message: str


class TaskGraphRuntime:
    def __init__(
        self,
        *,
        project_path: Path,
        graph: TaskGraph,
        llm_client: TaskGraphLLMClient | None = None,
        run_id: str | None = None,
        cancel_event: threading.Event | None = None,
        registry: ToolRegistry | None = None,
        tool_dispatcher: Callable[[ToolCall], ToolResult] | None = None,
    ) -> None:
        self.project_path = project_path
        self.graph = graph
        self.llm_client = llm_client
        self.run_id = run_id
        self.cancel_event = cancel_event or threading.Event()
        self.registry = registry
        self.tool_dispatcher = tool_dispatcher

    def run(self) -> TaskGraphRunResult:
        validate_task_graph(self.graph)
        run_id = self.run_id or uuid.uuid4().hex
        run_dir = self.project_path / ".amon" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        events_path = run_dir / "events.jsonl"
        state_path = run_dir / "state.json"
        resolved_path = run_dir / "graph.resolved.json"
        cancel_path = run_dir / "cancel.json"

        state: dict[str, Any] = {
            "run_id": run_id,
            "status": "running",
            "started_at": _now_iso(),
            "ended_at": None,
            "variables": dict(self.graph.session_defaults),
            "session": dict(self.graph.session_defaults),
            "nodes": {},
        }

        self._append_event(events_path, {"event": "run_start", "run_id": run_id})
        atomic_write_text(resolved_path, dumps_task_graph(self.graph), encoding="utf-8")

        nodes_by_id = {node.id: node for node in self.graph.nodes}
        adjacency, incoming = _build_graph(self.graph.nodes, self.graph.edges)

        for node in self.graph.nodes:
            state["nodes"][node.id] = {
                "status": "pending",
                "started_at": None,
                "ended_at": None,
                "error": None,
                "output_path": None,
            }

        llm_client = self.llm_client or build_default_llm_client()
        executor = ThreadPoolExecutor(max_workers=1)
        completed: set[str] = set()

        try:
            ready = deque(node_id for node_id, count in incoming.items() if count == 0)
            while ready:
                if self._is_canceled(cancel_path):
                    state["status"] = "canceled"
                    state["ended_at"] = _now_iso()
                    break

                node_id = ready.popleft()
                node = nodes_by_id[node_id]
                node_state = state["nodes"][node_id]

                node_state["status"] = "running"
                node_state["started_at"] = _now_iso()
                self._append_event(events_path, {"event": "node_start", "node_id": node_id})

                try:
                    output_text, output_path = self._execute_node_with_timeout(
                        llm_client=llm_client,
                        node=node,
                        session=state["session"],
                        project_path=self.project_path,
                        cancel_path=cancel_path,
                        executor=executor,
                        run_id=run_id,
                        events_path=events_path,
                    )
                except _NodeExecutionFailed as exc:
                    node_state["status"] = "failed"
                    node_state["ended_at"] = _now_iso()
                    node_state["error"] = exc.message
                    state["status"] = "failed"
                    state["ended_at"] = _now_iso()
                    state["error"] = exc.message
                    self._append_event(events_path, {"event": "run_failed", "run_id": run_id, "error": exc.message})
                    break
                except RuntimeError as exc:
                    if str(exc) == "run canceled":
                        node_state["status"] = "canceled"
                        node_state["ended_at"] = _now_iso()
                        state["status"] = "canceled"
                        state["ended_at"] = _now_iso()
                        break
                    node_state["status"] = "failed"
                    node_state["ended_at"] = _now_iso()
                    node_state["error"] = str(exc)
                    state["status"] = "failed"
                    state["ended_at"] = _now_iso()
                    state["error"] = str(exc)
                    self._append_event(events_path, {"event": "run_failed", "run_id": run_id, "error": str(exc)})
                    raise
                except Exception as exc:  # noqa: BLE001
                    node_state["status"] = "failed"
                    node_state["ended_at"] = _now_iso()
                    node_state["error"] = str(exc)
                    state["status"] = "failed"
                    state["ended_at"] = _now_iso()
                    state["error"] = str(exc)
                    self._append_event(events_path, {"event": "run_failed", "run_id": run_id, "error": str(exc)})
                    raise

                for key in node.writes:
                    if key not in state["session"]:
                        state["session"][key] = output_text
                state["variables"] = dict(state["session"])

                node_state["status"] = "completed"
                node_state["ended_at"] = _now_iso()
                node_state["output_path"] = str(output_path)
                self._append_event(
                    events_path,
                    {"event": "node_complete", "node_id": node_id, "output_path": str(output_path)},
                )
                completed.add(node_id)

                for edge in adjacency.get(node_id, []):
                    incoming[edge.to_node] -= 1
                    if incoming[edge.to_node] == 0:
                        ready.append(edge.to_node)

            if state["status"] == "running":
                if len(completed) != len(self.graph.nodes):
                    pending = [item.id for item in self.graph.nodes if item.id not in completed]
                    raise RuntimeError(f"TaskGraph 無法完成，仍有節點未執行：{pending}")
                state["status"] = "completed"
                state["ended_at"] = _now_iso()
                self._append_event(events_path, {"event": "run_complete", "run_id": run_id})
        except Exception:
            if state.get("status") == "running":
                state["status"] = "failed"
                state["ended_at"] = _now_iso()
                self._append_event(events_path, {"event": "run_failed", "run_id": run_id, "error": state.get("error")})
            raise
        finally:
            executor.shutdown(wait=True)
            atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        return TaskGraphRunResult(run_id=run_id, run_dir=run_dir, state=state)

    def _execute_node_with_timeout(
        self,
        *,
        llm_client: TaskGraphLLMClient,
        node: TaskNode,
        session: dict[str, Any],
        project_path: Path,
        cancel_path: Path,
        executor: ThreadPoolExecutor,
        run_id: str,
        events_path: Path,
    ) -> tuple[str, Path]:
        if _uses_tool_execution(node):
            output_text = self._execute_tool_node(node=node, session=session, run_id=run_id, events_path=events_path)
            output_path = _default_output_path(node.id)
            resolved = _resolve_output_path(project_path, output_path)
            atomic_write_text(resolved, output_text, encoding="utf-8")
            return output_text, resolved

        messages = _build_messages(node, session)
        future = executor.submit(_generate_text, llm_client, messages, node.llm.model)
        hard_timeout = node.timeout.hard_s

        started = datetime.now().timestamp()
        while True:
            if self.cancel_event.is_set() or cancel_path.exists():
                future.cancel()
                raise RuntimeError("run canceled")
            elapsed = datetime.now().timestamp() - started
            if elapsed > max(hard_timeout, 1):
                future.cancel()
                raise RuntimeError(f"node hard timeout：node_id={node.id}")
            try:
                output_text = future.result(timeout=0.1)
                break
            except FutureTimeoutError:
                continue
            except Exception:
                raise

        output_path = _default_output_path(node.id)
        resolved = _resolve_output_path(project_path, output_path)
        atomic_write_text(resolved, output_text, encoding="utf-8")
        return output_text, resolved

    def _execute_tool_node(
        self,
        *,
        node: TaskNode,
        session: dict[str, Any],
        run_id: str,
        events_path: Path,
    ) -> str:
        dispatcher = self._resolve_tool_dispatcher()
        outputs: list[str] = []
        for step in _iter_tool_steps(node):
            call = ToolCall(
                tool=str(step.get("tool_name") or ""),
                args=dict(step.get("args") or {}),
                caller="taskgraph2",
                project_id=str(self.project_path),
                run_id=run_id,
                node_id=node.id,
            )
            self._append_event(
                events_path,
                {
                    "event": "tool_request",
                    "node_id": node.id,
                    "tool": call.tool,
                    "args": call.args,
                    "meta": {"is_error": False, "status": "requested"},
                },
            )
            result = dispatcher(call)
            status = str(result.meta.get("status") or "ok")
            self._append_event(
                events_path,
                {
                    "event": "tool_result",
                    "node_id": node.id,
                    "tool": call.tool,
                    "result": result.content,
                    "meta": {"is_error": bool(result.is_error), "status": status},
                },
            )
            if result.is_error:
                raise _NodeExecutionFailed(f"tool step failed: {call.tool}: {result.as_text() or status}")

            text = result.as_text()
            outputs.append(text)
            key = _resolve_store_key(node=node, step=step)
            if key:
                session[key] = text

        return "\n".join(part for part in outputs if part).strip()

    def _resolve_tool_dispatcher(self) -> Callable[[ToolCall], ToolResult]:
        if self.tool_dispatcher is not None:
            return self.tool_dispatcher
        if self.registry is not None:
            return lambda call: self.registry.call(call, require_approval=False)
        raise _NodeExecutionFailed("tool dispatcher is not configured")

    def _append_event(self, path: Path, payload: dict[str, Any]) -> None:
        event_payload = dict(payload)
        event_payload["timestamp"] = _now_iso()
        append_jsonl(path, event_payload)

    def _is_canceled(self, cancel_path: Path) -> bool:
        if self.cancel_event.is_set() or cancel_path.exists():
            self.cancel_event.set()
            return True
        return False


def _build_graph(nodes: list[TaskNode], edges: list[TaskEdge]) -> tuple[dict[str, list[TaskEdge]], dict[str, int]]:
    incoming = {node.id: 0 for node in nodes}
    adjacency = {node.id: [] for node in nodes}
    for edge in edges:
        incoming[edge.to_node] += 1
        adjacency[edge.from_node].append(edge)
    return adjacency, incoming


def _build_messages(node: TaskNode, session: dict[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if node.role.strip():
        messages.append({"role": "system", "content": node.role.strip()})

    parts = [node.description.strip()]
    for key in node.reads:
        value = session.get(key)
        if value is None:
            continue
        parts.append(f"[session:{key}]\n{value}")
    messages.append({"role": "user", "content": "\n\n".join(parts).strip()})
    return messages


def _generate_text(llm_client: TaskGraphLLMClient, messages: list[dict[str, str]], model: str | None) -> str:
    return "".join(str(token) for token in llm_client.generate_stream(messages, model=model))


def _uses_tool_execution(node: TaskNode) -> bool:
    return bool(node.steps) or (node.kind == "tooling" and bool(node.tools))


def _iter_tool_steps(node: TaskNode) -> list[dict[str, Any]]:
    if node.steps:
        return [item for item in node.steps if str(item.get("type") or "") == "tool"]
    if node.kind != "tooling":
        return []
    steps: list[dict[str, Any]] = []
    for tool in node.tools:
        steps.append(
            {
                "type": "tool",
                "tool_name": tool.name,
                "args": dict(tool.args_schema_hint or {}),
            }
        )
    return steps


def _resolve_store_key(*, node: TaskNode, step: dict[str, Any]) -> str | None:
    store_as = step.get("store_as")
    if isinstance(store_as, str) and store_as.strip():
        return store_as.strip()
    tool_name = str(step.get("tool_name") or "")
    if tool_name in node.writes:
        return tool_name
    if len(node.writes) == 1:
        return next(iter(node.writes))
    return None


def _default_output_path(node_id: str) -> str:
    safe_id = validate_relative_path(node_id)
    return f"docs/steps/{safe_id}.md"


def _resolve_output_path(project_path: Path, relative_path: str) -> Path:
    normalized = validate_relative_path(relative_path)
    if not normalized.startswith(_ALLOWED_OUTPUT_PREFIXES):
        raise ValueError(f"輸出路徑不在允許前綴內：{normalized}")
    resolved = (project_path / normalized).resolve()
    project_root = project_path.resolve()
    if project_root not in resolved.parents and resolved != project_root:
        raise ValueError("輸出路徑超出專案目錄")
    return resolved


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
