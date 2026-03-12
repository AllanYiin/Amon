"""Compatibility runtime for legacy graph templates still emitted by core modes."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any

from amon.artifacts.store import ingest_artifacts
from amon.fs.atomic import append_jsonl, atomic_write_text
from amon.fs.safety import canonicalize_path
from amon.run.context import get_effective_constraints
from amon.taskgraph3.runtime import TaskGraph3RunResult


class _NodeCanceledError(RuntimeError):
    pass


class _NodeTimeoutError(RuntimeError):
    pass


class LegacyGraphRuntime:
    def __init__(
        self,
        *,
        core,
        project_path: Path,
        graph_payload: dict[str, Any],
        variables: dict[str, Any] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        request_id: str | None = None,
        thread_id: str | None = None,
        node_timeout_s: int | None = None,
    ) -> None:
        self.core = core
        self.project_path = Path(project_path)
        self.graph_payload = graph_payload
        self.variables = variables or {}
        self.stream_handler = stream_handler
        self.run_id = run_id
        self.request_id = request_id
        self.thread_id = thread_id
        self.node_timeout_s = node_timeout_s
        self.logger = core.logger

    def run(self) -> TaskGraph3RunResult:
        run_id = self.run_id or uuid.uuid4().hex
        run_dir = self.project_path / ".amon" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        events_path = run_dir / "events.jsonl"
        state_path = run_dir / "state.json"
        resolved_path = run_dir / "graph.resolved.json"

        merged_vars = {
            **(self.graph_payload.get("variables", {}) if isinstance(self.graph_payload.get("variables"), dict) else {}),
            **self.variables,
            "run_id": run_id,
        }
        resolved = {
            "version": str(self.graph_payload.get("version") or "taskgraph.v3"),
            "nodes": self.graph_payload.get("nodes", []),
            "edges": self.graph_payload.get("edges", []),
            "variables": merged_vars,
        }
        atomic_write_text(resolved_path, json.dumps(resolved, ensure_ascii=False, indent=2))

        nodes = self._index_nodes(resolved["nodes"])
        adjacency, incoming = self._build_graph(nodes, resolved["edges"])
        ready = deque(node_id for node_id, count in incoming.items() if count == 0)
        skipped: set[str] = set()
        completed: set[str] = set()

        state: dict[str, Any] = {
            "version": resolved["version"],
            "run_id": run_id,
            "status": "running",
            "variables": merged_vars,
            "nodes": {
                node_id: {
                    "status": "READY" if incoming.get(node_id, 0) == 0 else "PENDING",
                    "attempt_logs": [],
                    "output": None,
                    "error": None,
                }
                for node_id in nodes
            },
        }
        append_jsonl(events_path, {"event": "run_start", "run_id": run_id})

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            while ready:
                node_id = ready.popleft()
                if node_id in skipped:
                    completed.add(node_id)
                    continue

                node = nodes[node_id]
                node_state = state["nodes"][node_id]
                node_state["status"] = "RUNNING"
                append_jsonl(events_path, {"event": "node_status", "node_id": node_id, "status": "RUNNING"})

                try:
                    result = self._execute_node_with_timeout(
                        node,
                        merged_vars,
                        run_id,
                        executor=executor,
                    )
                except _NodeCanceledError:
                    node_state["status"] = "FAILED"
                    node_state["error"] = "node canceled"
                    node_state["attempt_logs"].append("attempt=1 failed=node canceled")
                    append_jsonl(events_path, {"event": "node_status", "node_id": node_id, "status": "FAILED", "error": "node canceled"})
                    state["status"] = "failed"
                    break
                except _NodeTimeoutError:
                    node_state["status"] = "FAILED"
                    node_state["error"] = "node timeout"
                    node_state["attempt_logs"].append("attempt=1 failed=node timeout")
                    append_jsonl(events_path, {"event": "node_status", "node_id": node_id, "status": "FAILED", "error": "node timeout"})
                    state["status"] = "failed"
                    break
                except Exception as exc:  # noqa: BLE001
                    node_state["status"] = "FAILED"
                    node_state["error"] = str(exc)
                    node_state["attempt_logs"].append(f"attempt=1 failed={exc}")
                    append_jsonl(events_path, {"event": "node_status", "node_id": node_id, "status": "FAILED", "error": str(exc)})
                    state["status"] = "failed"
                    raise

                node_state["status"] = "SUCCEEDED"
                node_state["output"] = result
                raw_output = str(result.get("raw_output") or result.get("content") or "")
                node_state["attempt_logs"].append(f"attempt=1 output_len={len(raw_output)}")
                append_jsonl(events_path, {"event": "node_status", "node_id": node_id, "status": "SUCCEEDED"})
                completed.add(node_id)

                for edge in adjacency.get(node_id, []):
                    target = edge["to"]
                    if target in skipped or target in completed:
                        continue
                    if edge.get("when") is not None and node.get("type") == "condition":
                        desired = self._parse_bool(edge.get("when"))
                        if bool(result.get("result")) is not desired:
                            self._skip_branch(target, adjacency, state, skipped)
                            continue
                    incoming[target] -= 1
                    if incoming[target] == 0 and state["nodes"][target]["status"] == "PENDING":
                        state["nodes"][target]["status"] = "READY"
                        ready.append(target)

            pending = [node_id for node_id in nodes if node_id not in completed and node_id not in skipped]
            if state["status"] == "running" and pending:
                raise RuntimeError(f"Graph 無法完成，仍有節點未執行：{pending}")
            if state["status"] == "running":
                state["status"] = "completed"
        finally:
            append_jsonl(events_path, {"event": "run_end", "run_id": run_id, "status": state["status"]})
            atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2))
            executor.shutdown(wait=True)

        return TaskGraph3RunResult(run_id=run_id, run_dir=run_dir, state=state)

    def _execute_node_with_timeout(
        self,
        node: dict[str, Any],
        variables: dict[str, Any],
        run_id: str,
        *,
        executor: ThreadPoolExecutor,
    ) -> dict[str, Any]:
        timeout_s = self._resolve_node_timeout(node)
        future = executor.submit(self._execute_node, node, variables, run_id)
        started = time.monotonic()
        while True:
            try:
                return future.result(timeout=0.1)
            except FutureTimeoutError:
                if timeout_s and (time.monotonic() - started) > timeout_s:
                    raise _NodeTimeoutError() from None
                continue

    def _execute_node(self, node: dict[str, Any], variables: dict[str, Any], run_id: str) -> dict[str, Any]:
        node_type = str(node.get("type") or "").strip()
        node_vars = {**variables, **(node.get("variables") if isinstance(node.get("variables"), dict) else {})}

        if node_type == "agent_task":
            prompt = self._render_template(str(node.get("prompt") or ""), node_vars)
            prompt = self._inject_run_constraints(prompt, run_id)
            try:
                response = self.core.run_agent_task(
                    prompt,
                    project_path=self.project_path,
                    model=node_vars.get("model") or node.get("model"),
                    mode=node_vars.get("mode", "single"),
                    stream_handler=self.stream_handler,
                    skill_names=node_vars.get("skill_names"),
                    conversation_history=node_vars.get("conversation_history"),
                    run_id=run_id,
                    node_id=str(node.get("id") or "") or None,
                    thread_id=self.thread_id,
                    request_id=self.request_id,
                )
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise
                response = self.core.run_agent_task(
                    prompt,
                    project_path=self.project_path,
                    model=node_vars.get("model") or node.get("model"),
                    mode=node_vars.get("mode", "single"),
                    stream_handler=self.stream_handler,
                    skill_names=node_vars.get("skill_names"),
                    conversation_history=node_vars.get("conversation_history"),
                )

            output_path = self._resolve_output_path(
                node,
                run_id,
                node_vars,
                default_prefix="docs",
                default_ext="md",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(output_path, response)
            ingest_summary = ingest_artifacts(
                response_text=response,
                project_path=self.project_path,
                source={
                    "run_id": run_id,
                    "node_id": str(node.get("id") or ""),
                    "output_path": str(output_path.relative_to(self.project_path)),
                },
            )
            if store_key := str(node.get("store_output") or "").strip():
                variables[store_key] = response
            return {
                "raw_output": response,
                "content": response,
                "output_path": str(output_path.relative_to(self.project_path)),
                "ingest_summary": ingest_summary,
            }

        if node_type == "write_file":
            rel_path = self._render_template(str(node.get("path") or ""), node_vars)
            content = self._render_template(str(node.get("content") or ""), node_vars)
            output_path = self._resolve_output_path(
                node,
                run_id,
                node_vars,
                explicit_path=rel_path,
                default_prefix="docs",
                default_ext="txt",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(output_path, content)
            if store_key := str(node.get("store_output") or "").strip():
                variables[store_key] = content
            return {
                "raw_output": content,
                "content": content,
                "path": str(output_path.relative_to(self.project_path)),
            }

        if node_type == "condition":
            result = self._evaluate_condition(node, variables)
            variables[f"condition.{node.get('id')}"] = result
            output_path = self._resolve_output_path(
                node,
                run_id,
                variables,
                default_prefix="audits",
                default_ext="json",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"result": result, "node_id": node.get("id")}
            atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2))
            return {
                "raw_output": json.dumps(payload, ensure_ascii=False),
                "result": result,
                "output_path": str(output_path.relative_to(self.project_path)),
            }

        if node_type == "map":
            return self._execute_map_node(node, variables, run_id)

        raise ValueError(f"不支援的 legacy node type：{node_type}")

    def _execute_map_node(self, node: dict[str, Any], variables: dict[str, Any], run_id: str) -> dict[str, Any]:
        items = self._resolve_map_items(node, variables)
        subgraph = node.get("subgraph") if isinstance(node.get("subgraph"), dict) else {}
        sub_nodes = subgraph.get("nodes") if isinstance(subgraph.get("nodes"), list) else []
        sub_edges = subgraph.get("edges") if isinstance(subgraph.get("edges"), list) else []
        item_var = str(node.get("item_var") or "item")
        collected_blocks: list[str] = []

        for index, item in enumerate(items, start=1):
            local_vars = {**variables, **self._flatten_item_vars(item_var, item, index)}
            results = self._run_subgraph(sub_nodes, sub_edges, local_vars, run_id)
            collect_variable = str(node.get("collect_variable") or "").strip()
            collect_template = str(node.get("collect_template") or "")
            if collect_variable and collect_template:
                template_vars = {**local_vars, **self._collect_result_vars(results)}
                collected_blocks.append(self._render_template(collect_template, template_vars))

        collect_variable = str(node.get("collect_variable") or "").strip()
        if collect_variable:
            joiner = str(node.get("collect_join") or "\n\n")
            variables[collect_variable] = joiner.join(collected_blocks)

        output_path = self._resolve_output_path(
            node,
            run_id,
            variables,
            default_prefix="audits",
            default_ext="json",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "node_id": node.get("id"),
            "items": len(items),
            "collect_variable": node.get("collect_variable"),
        }
        atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2))
        return {
            "raw_output": json.dumps(payload, ensure_ascii=False),
            "items": len(items),
            "output_path": str(output_path.relative_to(self.project_path)),
        }

    def _run_subgraph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        variables: dict[str, Any],
        run_id: str,
    ) -> dict[str, dict[str, Any]]:
        indexed = self._index_nodes(nodes)
        adjacency, incoming = self._build_graph(indexed, edges)
        ready = deque(node_id for node_id, count in incoming.items() if count == 0)
        completed: set[str] = set()
        skipped: set[str] = set()
        results: dict[str, dict[str, Any]] = {}

        while ready:
            node_id = ready.popleft()
            if node_id in skipped:
                completed.add(node_id)
                continue
            result = self._execute_node(indexed[node_id], variables, run_id)
            results[node_id] = result
            completed.add(node_id)
            for edge in adjacency.get(node_id, []):
                target = edge["to"]
                if target in skipped or target in completed:
                    continue
                if edge.get("when") is not None and indexed[node_id].get("type") == "condition":
                    desired = self._parse_bool(edge.get("when"))
                    if bool(result.get("result")) is not desired:
                        self._skip_branch_local(target, adjacency, skipped)
                        continue
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)

        pending = [node_id for node_id in indexed if node_id not in completed and node_id not in skipped]
        if pending:
            raise RuntimeError(f"Map 子圖無法完成，仍有節點未執行：{pending}")
        return results

    def _resolve_map_items(self, node: dict[str, Any], variables: dict[str, Any]) -> list[Any]:
        items_cfg = node.get("items")
        if isinstance(items_cfg, dict) and str(items_cfg.get("type") or "") == "range":
            count = int(items_cfg.get("count") or 0)
            return list(range(1, count + 1))
        if isinstance(items_cfg, dict) and str(items_cfg.get("type") or "") == "json_path":
            rel_path = self._render_template(str(items_cfg.get("path") or ""), variables)
            target_path = Path(rel_path)
            if not target_path.is_absolute():
                target_path = self.project_path / target_path
            safe_path = canonicalize_path(target_path, [self.project_path])
            payload = self._parse_json_payload(safe_path.read_text(encoding="utf-8"))
            query = str(items_cfg.get("query") or "").strip()
            if query:
                payload = payload.get(query, []) if isinstance(payload, dict) else []
            if not isinstance(payload, list):
                raise ValueError("map items 必須為陣列")
            return payload
        if isinstance(items_cfg, list):
            return items_cfg
        raise ValueError("map node 需要 items 設定")

    def _flatten_item_vars(self, item_var: str, item: Any, index: int) -> dict[str, Any]:
        flattened: dict[str, Any] = {"item_index": index}
        if isinstance(item, dict):
            for key, value in item.items():
                flattened[f"{item_var}_{key}"] = value
            flattened[item_var] = json.dumps(item, ensure_ascii=False)
            return flattened
        flattened[item_var] = item
        return flattened

    def _collect_result_vars(self, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        collected: dict[str, Any] = {}
        for node_id, result in results.items():
            if "content" in result:
                collected[f"{node_id}_content"] = result["content"]
            if "result" in result:
                collected[f"{node_id}_result"] = result["result"]
            if "output_path" in result:
                collected[f"{node_id}_output_path"] = result["output_path"]
        return collected

    def _render_template(self, text: str, variables: dict[str, Any]) -> str:
        safe_vars = {key: "" if value is None else str(value) for key, value in variables.items()}
        return Template(text).safe_substitute(safe_vars)

    def _evaluate_condition(self, node: dict[str, Any], variables: dict[str, Any]) -> bool:
        if "expression" in node:
            raise ValueError("condition 暫不支援 expression，請改用 variable/equals")
        var_name = str(node.get("variable") or "").strip()
        if not var_name:
            raise ValueError("condition 需要 variable")
        value = variables.get(var_name)
        if "equals" in node:
            return value == node.get("equals")
        if "not_equals" in node:
            return value != node.get("not_equals")
        if "contains" in node:
            return str(node.get("contains")) in str(value)
        return bool(value)

    def _resolve_output_path(
        self,
        node: dict[str, Any],
        run_id: str,
        variables: dict[str, Any],
        *,
        default_prefix: str,
        default_ext: str,
        explicit_path: str | None = None,
    ) -> Path:
        rel_path = explicit_path or str(node.get("output_path") or f"{default_prefix}/graph_{run_id}_{node.get('id')}.{default_ext}")
        rel_path = self._render_template(rel_path, {**variables, "run_id": run_id})
        target_path = Path(rel_path)
        if not target_path.is_absolute():
            target_path = self.project_path / target_path
        safe_path = canonicalize_path(target_path, [self.project_path])
        docs_dir = self.project_path / "docs"
        audits_dir = self.project_path / "audits"
        if docs_dir not in safe_path.parents and audits_dir not in safe_path.parents:
            raise ValueError("node 輸出必須落在 docs/ 或 audits/")
        return safe_path

    def _resolve_node_timeout(self, node: dict[str, Any]) -> int:
        raw_timeout = node.get("timeout_s") or node.get("timeout_seconds") or self.node_timeout_s or 300
        try:
            return max(1, int(raw_timeout))
        except (TypeError, ValueError):
            return 300

    def _inject_run_constraints(self, prompt: str, run_id: str) -> str:
        try:
            constraints = get_effective_constraints(run_id)
        except FileNotFoundError:
            return prompt
        if not constraints:
            return prompt
        block = "\n".join(constraints)
        return f"{prompt}\n\n```run_constraints\n{block}\n```"

    @staticmethod
    def _index_nodes(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "")
            if not node_id:
                raise ValueError("node 必須包含 id")
            if node_id in indexed:
                raise ValueError(f"node id 重複：{node_id}")
            indexed[node_id] = node
        return indexed

    @staticmethod
    def _build_graph(
        nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
        adjacency = {node_id: [] for node_id in nodes}
        incoming = {node_id: 0 for node_id in nodes}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("from") or "")
            target = str(edge.get("to") or "")
            if source not in nodes or target not in nodes:
                raise ValueError("edge 需指定有效的 from/to")
            adjacency[source].append(edge)
            incoming[target] += 1
        return adjacency, incoming

    def _skip_branch(
        self,
        start: str,
        adjacency: dict[str, list[dict[str, Any]]],
        state: dict[str, Any],
        skipped: set[str],
    ) -> None:
        stack = [start]
        while stack:
            node_id = stack.pop()
            if node_id in skipped:
                continue
            skipped.add(node_id)
            node_state = state["nodes"].get(node_id)
            if isinstance(node_state, dict) and node_state.get("status") in {"PENDING", "READY"}:
                node_state["status"] = "SKIPPED"
                node_state["error"] = "branch skipped"
            for edge in adjacency.get(node_id, []):
                stack.append(str(edge.get("to") or ""))

    @staticmethod
    def _skip_branch_local(start: str, adjacency: dict[str, list[dict[str, Any]]], skipped: set[str]) -> None:
        stack = [start]
        while stack:
            node_id = stack.pop()
            if node_id in skipped:
                continue
            skipped.add(node_id)
            for edge in adjacency.get(node_id, []):
                stack.append(str(edge.get("to") or ""))

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "y", "yes", "true"}
        return bool(value)

    @staticmethod
    def _parse_json_payload(text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().astimezone().isoformat()
