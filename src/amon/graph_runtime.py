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
            merged_vars = {**graph.get("variables", {}), **self.variables}
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
        if node_type == "agent_task":
            prompt = self._render_template(node.get("prompt", ""), variables)
            response = self.core.run_single(prompt, project_path=self.project_path)
            docs_dir = self.project_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            output_path = docs_dir / f"graph_{run_id}_{node.get('id')}.md"
            atomic_write_text(output_path, response)
            return {"output_path": str(output_path.relative_to(self.project_path))}
        if node_type == "write_file":
            rel_path = self._render_template(node.get("path", ""), variables)
            content = self._render_template(node.get("content", ""), variables)
            target_path = Path(rel_path)
            if not target_path.is_absolute():
                target_path = self.project_path / target_path
            safe_path = canonicalize_path(target_path, [self.project_path])
            atomic_write_text(safe_path, content)
            return {"path": str(safe_path.relative_to(self.project_path))}
        if node_type == "condition":
            result = self._evaluate_condition(node, variables)
            variables[f"condition.{node.get('id')}"] = result
            return {"result": result}
        raise ValueError(f"不支援的 node type：{node_type}")

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
        return bool(value)

    def _render_template(self, text: str, variables: dict[str, Any]) -> str:
        if not isinstance(text, str):
            return ""
        safe_vars = {key: "" if value is None else str(value) for key, value in variables.items()}
        return Template(text).safe_substitute(safe_vars)

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

    def _parse_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return bool(value)

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")
