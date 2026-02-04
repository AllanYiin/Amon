"""Graph runtime execution for Amon."""

from __future__ import annotations

import json
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any

from .fs.atomic import atomic_write_text
from .fs.safety import canonicalize_path
from .run.context import get_effective_constraints


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
    ) -> None:
        self.core = core
        self.project_path = project_path
        self.graph_path = graph_path
        self.variables = variables or {}
        self.logger = core.logger

    def run(self) -> GraphRunResult:
        run_id = uuid.uuid4().hex
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
                node_id = ready.popleft()
                if node_id in skipped:
                    completed.add(node_id)
                    continue
                node = nodes[node_id]
                state["nodes"][node_id]["status"] = "running"
                state["nodes"][node_id]["started_at"] = self._now_iso()
                self._append_event(events_path, {"event": "node_start", "node_id": node_id})

                try:
                    result = self._execute_node(node, merged_vars, run_id)
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
                self._append_event(
                    events_path,
                    {"event": "node_complete", "node_id": node_id, "output": result},
                )
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

            state["status"] = "completed"
            state["ended_at"] = self._now_iso()
            self._append_event(events_path, {"event": "run_complete", "run_id": run_id})
        except Exception as exc:  # noqa: BLE001
            state["status"] = "failed"
            state["ended_at"] = self._now_iso()
            state["error"] = str(exc)
            self._append_event(events_path, {"event": "run_failed", "run_id": run_id, "error": str(exc)})
            self.logger.error("Graph 執行失敗：%s", exc, exc_info=True)
            raise
        finally:
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
    ) -> dict[str, Any]:
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
            if store_key := node.get("store_output"):
                variables[store_key] = response
            return {
                "output_path": str(output_path.relative_to(self.project_path)),
                "content": response,
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
            return self._execute_map_node(node, variables, run_id)
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
    ) -> dict[str, Any]:
        items = self._resolve_map_items(node, variables)
        subgraph = node.get("subgraph", {})
        sub_nodes = subgraph.get("nodes", [])
        sub_edges = subgraph.get("edges", [])
        item_var = node.get("item_var", "item")
        collected_blocks: list[str] = []

        for index, item in enumerate(items, start=1):
            local_vars = {**variables, **self._flatten_item_vars(item_var, item, index)}
            results = self._run_subgraph(sub_nodes, sub_edges, local_vars, run_id)
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
    ) -> dict[str, dict[str, Any]]:
        indexed = self._index_nodes(nodes)
        adjacency, incoming = self._build_graph(indexed, edges)
        ready = deque([node_id for node_id, count in incoming.items() if count == 0])
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

    def _append_event(self, path: Path, payload: dict[str, Any]) -> None:
        payload = {**payload, "ts": self._now_iso()}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

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
