"""Graph runtime execution for Amon."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any

from .artifacts import ingest_artifacts
from .fs.atomic import append_jsonl, atomic_write_text
from .fs.safety import canonicalize_path
from .events import emit_event
from .observability import ensure_correlation_fields, normalize_project_id
from .run.context import get_effective_constraints
from .sandbox.service import run_sandbox_step


@dataclass
class GraphRunResult:
    run_id: str
    state: dict[str, Any]
    run_dir: Path


class GraphRuntime:
    def __init__(
        self,
        core,
        project_path: Path,
        graph_path: Path,
        variables: dict[str, Any] | None = None,
        stream_handler=None,
        run_id: str | None = None,
        cancel_event: threading.Event | None = None,
        node_timeout_s: int | None = None,
        request_id: str | None = None,
    ) -> None:
        self.core = core
        self.project_path = project_path
        self.graph_path = graph_path
        self.variables = variables or {}
        self.stream_handler = stream_handler
        self.run_id = run_id
        self.logger = core.logger
        self.cancel_event = cancel_event or threading.Event()
        self.node_timeout_s = node_timeout_s
        self._cancel_path: Path | None = None
        self.request_id = request_id
        self._active_run_id: str | None = run_id

    def run(self) -> GraphRunResult:
        run_id = self.run_id or uuid.uuid4().hex
        self._active_run_id = run_id
        run_dir = self.project_path / ".amon" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        events_path = run_dir / "events.jsonl"
        state_path = run_dir / "state.json"
        resolved_path = run_dir / "graph.resolved.json"

        state: dict[str, Any] = {
            "run_id": run_id,
            "status": "running",
            "started_at": self._now_iso(),
            "ended_at": None,
            "variables": {},
            "nodes": {},
        }
        self._append_event(events_path, {"event": "run_start", "run_id": run_id})
        emit_event(
            {
                "type": "run.started",
                "scope": "graph",
                "project_id": normalize_project_id(self.project_path.name),
                "actor": "system",
                "payload": {"run_id": run_id, "graph_path": str(self.graph_path)},
                "run_id": run_id,
                "request_id": self.request_id,
                "risk": "low",
            }
        )

        cancel_path = run_dir / "cancel.json"
        self._cancel_path = cancel_path
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            graph = self._load_graph()
            merged_vars = {**graph.get("variables", {}), **self.variables, "run_id": run_id}
            state["variables"] = merged_vars
            resolved = {
                "nodes": graph.get("nodes", []),
                "edges": graph.get("edges", []),
                "variables": merged_vars,
            }
            self._write_json(resolved_path, resolved)

            nodes = self._index_nodes(resolved["nodes"])
            edges = resolved["edges"]
            adjacency, incoming = self._build_graph(nodes, edges)

            for node_id, node in nodes.items():
                state["nodes"][node_id] = {
                    "type": node.get("type"),
                    "status": "pending",
                    "started_at": None,
                    "ended_at": None,
                    "output": None,
                    "error": None,
                }

            ready = deque([node_id for node_id, count in incoming.items() if count == 0])
            completed: set[str] = set()
            skipped: set[str] = set()

            while ready:
                if self._refresh_cancel(cancel_path):
                    self._append_event(events_path, {"event": "run_canceled", "run_id": run_id})
                    state["status"] = "canceled"
                    state["ended_at"] = self._now_iso()
                    self._mark_pending_as_canceled(state, nodes, completed, skipped)
                    break
                node_id = ready.popleft()
                if node_id in skipped:
                    completed.add(node_id)
                    continue
                node = nodes[node_id]
                state["nodes"][node_id]["status"] = "running"
                state["nodes"][node_id]["started_at"] = self._now_iso()
                self._append_event(events_path, {"event": "node_start", "node_id": node_id})

                try:
                    result = self._execute_node_with_timeout(
                        node,
                        merged_vars,
                        run_id,
                        events_path=events_path,
                        executor=executor,
                    )
                except _NodeCanceledError:
                    state["nodes"][node_id]["status"] = "canceled"
                    state["nodes"][node_id]["ended_at"] = self._now_iso()
                    state["nodes"][node_id]["error"] = "node canceled"
                    self._append_event(events_path, {"event": "node_canceled", "node_id": node_id})
                    self._append_event(events_path, {"event": "run_canceled", "run_id": run_id})
                    state["status"] = "canceled"
                    state["ended_at"] = self._now_iso()
                    self._mark_pending_as_canceled(state, nodes, completed, skipped)
                    break
                except _NodeTimeoutError:
                    state["nodes"][node_id]["status"] = "failed"
                    state["nodes"][node_id]["ended_at"] = self._now_iso()
                    state["nodes"][node_id]["error"] = "node timeout"
                    self._append_event(events_path, {"event": "node_timeout", "node_id": node_id})
                    raise RuntimeError("node timeout")
                except Exception as exc:  # noqa: BLE001
                    self.logger.error("Graph node 執行失敗：%s", exc, exc_info=True)
                    state["nodes"][node_id]["status"] = "failed"
                    state["nodes"][node_id]["ended_at"] = self._now_iso()
                    state["nodes"][node_id]["error"] = str(exc)
                    self._append_event(
                        events_path,
                        {"event": "node_failed", "node_id": node_id, "error": str(exc)},
                    )
                    raise

                state["nodes"][node_id]["status"] = "completed"
                state["nodes"][node_id]["ended_at"] = self._now_iso()
                state["nodes"][node_id]["output"] = result
                ingest_summary = result.get("ingest_summary") if isinstance(result, dict) else None
                if isinstance(ingest_summary, dict):
                    self._append_event(
                        events_path,
                        {
                            "event": "artifact_ingest_summary",
                            "node_id": node_id,
                            "summary": ingest_summary,
                        },
                    )
                self._emit_artifact_written_events(events_path, node_id, result)
                node_complete_event = {"event": "node_complete", "node_id": node_id, "output": result}
                node_complete_event.update(self._promote_output_paths(result))
                self._append_event(events_path, node_complete_event)
                completed.add(node_id)

                for edge in adjacency.get(node_id, []):
                    target = edge["to"]
                    if target in skipped or target in completed:
                        continue
                    if edge.get("when") is not None and node.get("type") == "condition":
                        desired = self._parse_bool(edge.get("when"))
                        if result.get("result") is not desired:
                            self._append_event(
                                events_path,
                                {
                                    "event": "edge_skipped",
                                    "from": node_id,
                                    "to": target,
                                    "when": desired,
                                },
                            )
                            self._skip_branch(target, adjacency, state, events_path, skipped)
                            continue
                    incoming[target] -= 1
                    if incoming[target] == 0 and target not in skipped:
                        ready.append(target)

            if len(completed) != len(nodes):
                pending = [node_id for node_id in nodes if node_id not in completed and node_id not in skipped]
                raise RuntimeError(f"Graph 無法完成，仍有節點未執行：{pending}")

            if state["status"] == "running":
                state["status"] = "completed"
                state["ended_at"] = self._now_iso()
                self._append_event(events_path, {"event": "run_complete", "run_id": run_id})
                emit_event(
                    {
                        "type": "run.completed",
                        "scope": "graph",
                        "project_id": normalize_project_id(self.project_path.name),
                        "actor": "system",
                        "payload": {"run_id": run_id, "graph_path": str(self.graph_path)},
                        "run_id": run_id,
                        "request_id": self.request_id,
                        "risk": "low",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            if state["status"] not in {"canceled"}:
                state["status"] = "failed"
                state["ended_at"] = self._now_iso()
                state["error"] = str(exc)
                self._append_event(events_path, {"event": "run_failed", "run_id": run_id, "error": str(exc)})
                self.logger.error("Graph 執行失敗：%s", exc, exc_info=True)
                raise
        finally:
            executor.shutdown(wait=True)
            self._write_json(state_path, state)

        return GraphRunResult(run_id=run_id, state=state, run_dir=run_dir)

    def _load_graph(self) -> dict[str, Any]:
        try:
            content = self.graph_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.logger.error("讀取 graph 檔案失敗：%s", exc, exc_info=True)
            raise
        try:
            graph = json.loads(content)
        except json.JSONDecodeError as exc:
            self.logger.error("解析 graph JSON 失敗：%s", exc, exc_info=True)
            raise ValueError("graph.json 格式錯誤") from exc
        if not isinstance(graph, dict):
            raise ValueError("graph.json 內容需為物件")
        graph.setdefault("nodes", [])
        graph.setdefault("edges", [])
        graph.setdefault("variables", {})
        return graph

    def _index_nodes(self, nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                raise ValueError("node 必須包含 id")
            if node_id in indexed:
                raise ValueError(f"node id 重複：{node_id}")
            indexed[node_id] = node
        return indexed

    def _build_graph(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
        adjacency = {node_id: [] for node_id in nodes}
        incoming = {node_id: 0 for node_id in nodes}
        for edge in edges:
            source = edge.get("from")
            target = edge.get("to")
            if source not in nodes or target not in nodes:
                raise ValueError("edge 需指定有效的 from/to")
            adjacency[source].append(edge)
            incoming[target] += 1
        return adjacency, incoming

    def _execute_node(
        self,
        node: dict[str, Any],
        variables: dict[str, Any],
        run_id: str,
        *,
        cancel_event: threading.Event | None = None,
        timeout_s: int | None = None,
    ) -> dict[str, Any]:
        if cancel_event and cancel_event.is_set():
            raise _NodeCanceledError()
        node_type = node.get("type")
        node_vars = {**variables, **node.get("variables", {})}
        if node_type == "agent_task":
            prompt = self._render_template(node.get("prompt", ""), node_vars)
            prompt = self._inject_run_constraints(prompt, run_id)
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
            if store_key := node.get("store_output"):
                variables[store_key] = response
            return {
                "output_path": str(output_path.relative_to(self.project_path)),
                "content": response,
                "ingest_summary": ingest_summary,
            }
        if node_type == "write_file":
            rel_path = self._render_template(node.get("path", ""), node_vars)
            content = self._render_template(node.get("content", ""), node_vars)
            safe_path = self._resolve_output_path(
                node,
                run_id,
                node_vars,
                explicit_path=rel_path,
                default_prefix="docs",
                default_ext="txt",
            )
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(safe_path, content)
            if store_key := node.get("store_output"):
                variables[store_key] = content
            return {"path": str(safe_path.relative_to(self.project_path))}
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
            atomic_write_text(
                output_path,
                json.dumps({"result": result, "node_id": node.get("id")}, ensure_ascii=False, indent=2),
            )
            return {"result": result, "output_path": str(output_path.relative_to(self.project_path))}
        if node_type == "map":
            return self._execute_map_node(node, variables, run_id, cancel_event=cancel_event)
        if node_type in {"tool.call", "tool_call"}:
            tool_name = str(node.get("tool") or "")
            if not tool_name:
                raise ValueError("tool.call node 缺少 tool")
            args = self._render_payload(node.get("args") or {}, node_vars)
            result = self.core.call_tool_unified(
                tool_name,
                args,
                project_id=self.project_path.name,
                timeout_s=timeout_s,
                cancel_event=cancel_event,
            )
            if store_key := node.get("store_output"):
                variables[store_key] = result
            return {"result": result, "tool": tool_name}
        if node_type == "sandbox_run":
            language = self._render_template(str(node.get("language") or "python"), node_vars)
            code = self._render_template(str(node.get("code") or ""), node_vars)
            code_file = self._render_template(str(node.get("code_file") or ""), node_vars)
            if code.strip() and code_file:
                raise ValueError("sandbox_run node 只能提供 code 或 code_file 其中之一")
            if not code.strip() and code_file:
                code_path = canonicalize_path(self.project_path / code_file, [self.project_path])
                code = code_path.read_text(encoding="utf-8")
            if not code.strip():
                raise ValueError("sandbox_run node 缺少 code 或 code_file")
            raw_input_files = node.get("input_files")
            if raw_input_files is None:
                raw_input_files = node.get("input_paths") or []
            input_paths = [self._render_template(str(path), node_vars) for path in raw_input_files]
            output_prefix = node.get("output_prefix")
            if output_prefix:
                output_prefix = self._render_template(str(output_prefix), node_vars)
            else:
                output_prefix = f"docs/artifacts/{run_id}/{node.get('id')}/"
            overwrite = bool(node.get("overwrite", False))
            service_result = run_sandbox_step(
                project_path=self.project_path,
                config=self.core.load_config(self.project_path),
                run_id=run_id,
                step_id=str(node.get("id") or "sandbox_step"),
                language=language,
                code=code,
                input_paths=input_paths,
                output_prefix=output_prefix,
                timeout_s=timeout_s,
                overwrite=overwrite,
            )
            manifest_path = self._to_relative_project_path(service_result.get("manifest_path"))
            artifact_files = [self._to_relative_project_path(path) for path in service_result.get("written_files", [])]
            result = {
                "exit_code": service_result.get("exit_code"),
                "timed_out": bool(service_result.get("timed_out", False)),
                "duration_ms": service_result.get("duration_ms"),
                "stdout": service_result.get("stdout", ""),
                "stderr": service_result.get("stderr", ""),
                "artifact_path": manifest_path,
                "artifacts": {
                    "manifest_path": manifest_path,
                    "files": artifact_files,
                    "outputs": service_result.get("outputs", []),
                },
            }
            self._append_event(
                self.project_path / ".amon" / "runs" / run_id / "events.jsonl",
                {
                    "event": "sandbox_run_summary",
                    "node_id": node.get("id"),
                    "exit_code": result.get("exit_code"),
                    "manifest_path": manifest_path,
                    "written_files": artifact_files,
                },
            )
            if store_key := node.get("store_output"):
                variables[store_key] = result
            return result
        raise ValueError(f"不支援的 node type：{node_type}")

    def _inject_run_constraints(self, prompt: str, run_id: str) -> str:
        constraints = get_effective_constraints(run_id)
        if not constraints:
            return prompt
        block = "\n".join(constraints)
        return f"{prompt}\n\n```run_constraints\n{block}\n```"

    def _evaluate_condition(self, node: dict[str, Any], variables: dict[str, Any]) -> bool:
        if "expression" in node:
            raise ValueError("condition 暫不支援 expression，請改用 variable/equals")
        var_name = node.get("variable")
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

    def _render_template(self, text: str, variables: dict[str, Any]) -> str:
        if not isinstance(text, str):
            return ""
        safe_vars = {key: "" if value is None else str(value) for key, value in variables.items()}
        return Template(text).safe_substitute(safe_vars)

    def _execute_map_node(
        self,
        node: dict[str, Any],
        variables: dict[str, Any],
        run_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        items = self._resolve_map_items(node, variables)
        subgraph = node.get("subgraph", {})
        sub_nodes = subgraph.get("nodes", [])
        sub_edges = subgraph.get("edges", [])
        item_var = node.get("item_var", "item")
        collected_blocks: list[str] = []

        for index, item in enumerate(items, start=1):
            if cancel_event and cancel_event.is_set():
                raise _NodeCanceledError()
            local_vars = {**variables, **self._flatten_item_vars(item_var, item, index)}
            results = self._run_subgraph(sub_nodes, sub_edges, local_vars, run_id, cancel_event=cancel_event)
            collect_variable = node.get("collect_variable")
            collect_template = node.get("collect_template")
            if collect_variable and collect_template:
                template_vars = {**local_vars, **self._collect_result_vars(results)}
                collected_blocks.append(self._render_template(collect_template, template_vars))

        if collect_variable := node.get("collect_variable"):
            joiner = node.get("collect_join", "\n\n")
            variables[collect_variable] = joiner.join(collected_blocks)

        output_path = self._resolve_output_path(
            node,
            run_id,
            variables,
            default_prefix="audits",
            default_ext="json",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            output_path,
            json.dumps(
                {
                    "node_id": node.get("id"),
                    "items": len(items),
                    "collect_variable": node.get("collect_variable"),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        return {"items": len(items), "output_path": str(output_path.relative_to(self.project_path))}

    def _run_subgraph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        variables: dict[str, Any],
        run_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, dict[str, Any]]:
        indexed = self._index_nodes(nodes)
        adjacency, incoming = self._build_graph(indexed, edges)
        ready = deque([node_id for node_id, count in incoming.items() if count == 0])
        completed: set[str] = set()
        skipped: set[str] = set()
        results: dict[str, dict[str, Any]] = {}

        while ready:
            if cancel_event and cancel_event.is_set():
                raise _NodeCanceledError()
            node_id = ready.popleft()
            if node_id in skipped:
                completed.add(node_id)
                continue
            timeout_s = self._resolve_node_timeout(indexed[node_id])
            result = self._execute_node(indexed[node_id], variables, run_id, cancel_event=cancel_event, timeout_s=timeout_s)
            results[node_id] = result
            completed.add(node_id)
            for edge in adjacency.get(node_id, []):
                target = edge["to"]
                if target in skipped or target in completed:
                    continue
                if edge.get("when") is not None and indexed[node_id].get("type") == "condition":
                    desired = self._parse_bool(edge.get("when"))
                    if result.get("result") is not desired:
                        self._skip_branch_local(target, adjacency, skipped)
                        continue
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)

        if len(completed) + len(skipped) != len(nodes):
            pending = [node_id for node_id in indexed if node_id not in completed and node_id not in skipped]
            raise RuntimeError(f"Map 子圖無法完成，仍有節點未執行：{pending}")
        return results

    def _resolve_map_items(self, node: dict[str, Any], variables: dict[str, Any]) -> list[Any]:
        items_cfg = node.get("items", {})
        if items_cfg.get("type") == "range":
            count = int(items_cfg.get("count", 0))
            return list(range(1, count + 1))
        if items_cfg.get("type") == "json_path":
            rel_path = self._render_template(items_cfg.get("path", ""), variables)
            target_path = Path(rel_path)
            if not target_path.is_absolute():
                target_path = self.project_path / target_path
            safe_path = canonicalize_path(target_path, [self.project_path])
            payload = self._parse_json_payload(safe_path.read_text(encoding="utf-8"))
            query = items_cfg.get("query")
            if query:
                payload = payload.get(query, [])
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
        else:
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
        rel_path = explicit_path
        if not rel_path:
            rel_path = node.get("output_path") or f"{default_prefix}/graph_{run_id}_{node.get('id')}.{default_ext}"
        rel_path = self._render_template(str(rel_path), {**variables, "run_id": run_id})
        target_path = Path(rel_path)
        if not target_path.is_absolute():
            target_path = self.project_path / target_path
        safe_path = canonicalize_path(target_path, [self.project_path])
        docs_dir = self.project_path / "docs"
        audits_dir = self.project_path / "audits"
        if not (docs_dir in safe_path.parents or audits_dir in safe_path.parents):
            raise ValueError("node 輸出必須落在 docs/ 或 audits/")
        return safe_path

    def _execute_node_with_timeout(
        self,
        node: dict[str, Any],
        variables: dict[str, Any],
        run_id: str,
        *,
        events_path: Path,
        executor: ThreadPoolExecutor,
    ) -> dict[str, Any]:
        timeout_s = self._resolve_node_timeout(node)
        node_cancel = threading.Event()
        start = time.monotonic()
        future = executor.submit(
            self._execute_node,
            node,
            variables,
            run_id,
            cancel_event=node_cancel,
            timeout_s=timeout_s,
        )
        while True:
            if self._refresh_cancel(None):
                node_cancel.set()
            try:
                result = future.result(timeout=0.1)
                if self.cancel_event.is_set():
                    raise _NodeCanceledError()
                return result
            except FutureTimeoutError:
                if self.cancel_event.is_set():
                    node_cancel.set()
                if node_cancel.is_set() and future.done():
                    raise _NodeCanceledError()
                if timeout_s and (time.monotonic() - start) > timeout_s:
                    node_cancel.set()
                    self._append_event(events_path, {"event": "node_timeout_pending", "node_id": node.get("id")})
                    raise _NodeTimeoutError()
                continue

    def _resolve_node_timeout(self, node: dict[str, Any]) -> int:
        raw = node.get("timeout_s") or node.get("timeout_seconds") or self.node_timeout_s
        if raw is None:
            raw = os.environ.get("AMON_GRAPH_NODE_TIMEOUT") or 60
        try:
            timeout = int(raw)
        except (TypeError, ValueError):
            timeout = 60
        return max(timeout, 1)

    def _refresh_cancel(self, cancel_path: Path | None = None) -> bool:
        if self.cancel_event.is_set():
            return True
        target_path = cancel_path or self._cancel_path
        if target_path and target_path.exists():
            self.cancel_event.set()
            return True
        return False

    def _mark_pending_as_canceled(
        self,
        state: dict[str, Any],
        nodes: dict[str, dict[str, Any]],
        completed: set[str],
        skipped: set[str],
    ) -> None:
        for node_id in nodes:
            if node_id in completed or node_id in skipped:
                continue
            state["nodes"][node_id]["status"] = "canceled"
            state["nodes"][node_id]["ended_at"] = self._now_iso()

    def _render_payload(self, payload: Any, variables: dict[str, Any]) -> Any:
        if isinstance(payload, dict):
            return {key: self._render_payload(value, variables) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self._render_payload(value, variables) for value in payload]
        if isinstance(payload, str):
            return self._render_template(payload, variables)
        return payload

    def _to_relative_project_path(self, path_value: Any) -> str:
        if not path_value:
            return ""
        target_path = Path(str(path_value))
        if not target_path.is_absolute():
            target_path = self.project_path / target_path
        safe_path = canonicalize_path(target_path, [self.project_path])
        return safe_path.relative_to(self.project_path).as_posix()

    def _emit_artifact_written_events(self, events_path: Path, node_id: str, result: dict[str, Any]) -> None:
        artifacts = result.get("artifacts") if isinstance(result, dict) else None
        if not isinstance(artifacts, dict):
            return
        artifact_paths = artifacts.get("files", [])
        if not isinstance(artifact_paths, list):
            return
        for artifact_path in artifact_paths:
            rel_path = self._to_relative_project_path(artifact_path)
            if not rel_path:
                continue
            self._append_event(
                events_path,
                {"event": "artifact_written", "node_id": node_id, "artifact_path": rel_path},
            )

    def _promote_output_paths(self, result: dict[str, Any]) -> dict[str, str]:
        promoted: dict[str, str] = {}
        for key in ("path", "output_path", "doc_path", "artifact_path"):
            value = result.get(key)
            if isinstance(value, str) and value:
                promoted[key] = value
        return promoted


    def _append_event(self, path: Path, payload: dict[str, Any]) -> None:
        enriched = {**payload, "ts": self._now_iso()}
        enriched = ensure_correlation_fields(
            enriched,
            project_id=self.project_path.name,
            run_id=self._active_run_id,
            node_id=str(payload.get("node_id") or "") or None,
            request_id=self.request_id,
            tool=str(payload.get("tool") or "") or None,
        )
        append_jsonl(path, enriched)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _skip_branch(
        self,
        node_id: str,
        adjacency: dict[str, list[dict[str, Any]]],
        state: dict[str, Any],
        events_path: Path,
        skipped: set[str],
    ) -> None:
        stack = [node_id]
        while stack:
            current = stack.pop()
            if current in skipped:
                continue
            skipped.add(current)
            if current in state["nodes"]:
                state["nodes"][current]["status"] = "skipped"
                state["nodes"][current]["ended_at"] = self._now_iso()
            self._append_event(events_path, {"event": "node_skipped", "node_id": current})
            for edge in adjacency.get(current, []):
                stack.append(edge["to"])

    def _skip_branch_local(
        self,
        node_id: str,
        adjacency: dict[str, list[dict[str, Any]]],
        skipped: set[str],
    ) -> None:
        stack = [node_id]
        while stack:
            current = stack.pop()
            if current in skipped:
                continue
            skipped.add(current)
            for edge in adjacency.get(current, []):
                stack.append(edge["to"])

    def _parse_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return bool(value)

    def _parse_json_payload(self, text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
            return {}
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    payload = json.loads(text[start : end + 1])
                    if isinstance(payload, dict):
                        return payload
                except json.JSONDecodeError:
                    pass
            return {}

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")


class _NodeTimeoutError(RuntimeError):
    """Node execution timeout."""


class _NodeCanceledError(RuntimeError):
    """Node execution canceled."""
