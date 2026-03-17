"""TaskGraph v3 runtime with deterministic cross-cutting capabilities."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from amon.fs.atomic import append_jsonl, atomic_write_text

from amon.artifacts.store import ingest_artifacts

from .schema import ArtifactNode, GateNode, GraphDefinition, GraphEdge, GroupNode, TaskNode, validate_graph_definition
from .serialize import dumps_graph_definition


class OutputContractError(ValueError):
    """Raised when a node output violates outputContract."""


@dataclass
class TaskGraph3RunResult:
    run_id: str
    run_dir: Path
    state: dict[str, Any]


class TaskGraph3Runtime:
    """Deterministic v3 runtime for SINGLE/PARALLEL_MAP/RECURSIVE task execution."""

    def __init__(
        self,
        *,
        project_path: Path,
        graph: GraphDefinition,
        run_id: str | None = None,
        time_func: Callable[[], float] | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        validate_graph_definition(graph)
        self.project_path = Path(project_path)
        self.graph = graph
        self.run_id = run_id
        self._time = time_func or time.monotonic
        self._sleep = sleep_func or time.sleep
        self._bucket_state: dict[str, dict[str, float]] = {}
        self._stream_state: dict[str, dict[str, float]] = {}
        self._rate_lock = threading.Lock()

    def run(self, node_runner: Callable[[TaskNode, dict[str, Any]], Any]) -> TaskGraph3RunResult:
        run_id = self.run_id or uuid.uuid4().hex
        run_dir = self.project_path / ".amon" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        state_path = run_dir / "state.json"
        events_path = run_dir / "events.jsonl"
        resolved_path = run_dir / "graph.resolved.json"

        nodes = {node.id: node for node in self.graph.nodes}
        adjacency, incoming = self._compile_control_graph(self.graph.edges)
        ready = deque(node_id for node_id, count in incoming.items() if count == 0)

        state: dict[str, Any] = {
            "version": self.graph.version,
            "run_id": run_id,
            "status": "running",
            "nodes": {
                node_id: {
                    "status": "ready" if incoming.get(node_id, 0) == 0 else "queued",
                    "attempt_logs": [],
                    "output": None,
                    "error": None,
                }
                for node_id in nodes
            },
            "variables": {"run_id": run_id},
            "metrics": {
                "counters": {"nodes_total": len(nodes), "nodes_succeeded": 0, "nodes_failed": 0},
                "latency_ms": {},
            },
        }

        self._write_json(resolved_path, json.loads(dumps_graph_definition(self.graph)))
        self._emit_event(events_path, {"event": "run_start", "run_id": run_id}, stream_limit=None)

        while ready:
            node_id = ready.popleft()
            node_state = state["nodes"][node_id]
            node_state["status"] = "running"
            node = nodes[node_id]
            stream_limit = node.policy.stream_limit if isinstance(node, TaskNode) else None
            self._emit_event(
                events_path,
                {"event": "node_status", "node_id": node_id, "status": "running"},
                stream_limit=stream_limit,
            )

            try:
                started = self._time()
                output_payload: dict[str, Any] = {}
                extracted: dict[str, Any] = {}
                if isinstance(node, TaskNode):
                    output_payload = self._execute_node_by_mode(node, state, node_runner)
                    raw_output = str(output_payload.get("raw_output") or "")
                    node_state["attempt_logs"].append(f"attempt=1 output_len={len(raw_output)}")
                    extracted = self._extract_ports(node, raw_output)
                    self._validate_output_contract(node, extracted)
                    self._flush_stream(events_path, node.id)
                elif isinstance(node, GateNode):
                    output_payload = self._execute_gate_node(node, state, adjacency)
                    self._emit_event(
                        events_path,
                        {
                            "event": "gate_route_evaluated",
                            "node_id": node.id,
                            "outcome": output_payload.get("outcome"),
                            "selected_targets": output_payload.get("selected_targets", []),
                        },
                        stream_limit=None,
                    )
                    self._flush_stream(events_path, node.id)
                elif isinstance(node, ArtifactNode):
                    output_payload = self._execute_artifact_node(node, state, adjacency)
                    self._emit_event(
                        events_path,
                        {
                            "event": "artifact_materialized",
                            "node_id": node.id,
                            "action": output_payload.get("action"),
                            "metadata": output_payload.get("metadata", {}),
                        },
                        stream_limit=None,
                    )
                    self._flush_stream(events_path, node.id)
                elif isinstance(node, GroupNode):
                    raise NotImplementedError(
                        f"node={node.id} GROUP execution is not supported yet; fail-fast by design"
                    )
                else:
                    raise TypeError(f"Unsupported node class for node={node.id}")

                latency_ms = int((self._time() - started) * 1000)
                state["metrics"]["latency_ms"][node_id] = latency_ms
                state["metrics"]["counters"]["nodes_succeeded"] += 1
                node_state["status"] = "succeeded"
                if isinstance(node, TaskNode):
                    merged_output = {"raw": str(output_payload.get("raw_output") or ""), "ports": extracted}
                    for key, value in output_payload.items():
                        if key == "raw_output":
                            continue
                        merged_output[key] = value
                    node_state["output"] = merged_output
                else:
                    node_state["output"] = output_payload
                self._emit_event(
                    events_path,
                    {"event": "node_status", "node_id": node_id, "status": "succeeded", "latency_ms": latency_ms},
                    stream_limit=stream_limit,
                )
            except Exception as exc:  # noqa: BLE001
                self._flush_stream(events_path, node.id)
                state["metrics"]["counters"]["nodes_failed"] += 1
                node_state["status"] = "failed"
                node_state["error"] = str(exc)
                node_state["attempt_logs"].append(f"attempt=1 failed={exc}")
                self._emit_event(
                    events_path,
                    {"event": "node_status", "node_id": node_id, "status": "failed", "error": str(exc)},
                    stream_limit=stream_limit,
                )
                state["status"] = "failed"
                break

            for nxt in adjacency.get(node_id, []):
                incoming[nxt] -= 1
                if incoming[nxt] == 0 and state["nodes"][nxt]["status"] == "queued":
                    state["nodes"][nxt]["status"] = "ready"
                    ready.append(nxt)

        if state["status"] == "running":
            state["status"] = "succeeded"

        self._emit_event(
            events_path,
            {"event": "run_end", "run_id": run_id, "status": state["status"]},
            stream_limit=None,
        )
        self._write_json(state_path, state)
        return TaskGraph3RunResult(run_id=run_id, run_dir=run_dir, state=state)

    def _execute_node_by_mode(
        self,
        node: TaskNode,
        state: dict[str, Any],
        node_runner: Callable[[TaskNode, dict[str, Any]], Any],
    ) -> dict[str, Any]:
        mode = node.execution
        if mode == "PARALLEL_MAP":
            return self._run_parallel_map(node, state, node_runner)
        if mode == "RECURSIVE":
            return self._run_recursive(node, state, node_runner)
        self._acquire_rate_limit(node.id, node.policy.rate_limit)
        return self._normalize_runner_output(node_runner(node, state))

    def _run_parallel_map(
        self,
        node: TaskNode,
        state: dict[str, Any],
        node_runner: Callable[[TaskNode, dict[str, Any]], Any],
    ) -> dict[str, Any]:
        config = node.execution_config or {}
        items = self._resolve_parallel_items(node, state, config)
        max_concurrency = int(config.get("maxConcurrency") or 1)
        if max_concurrency <= 0:
            raise ValueError(f"node={node.id} maxConcurrency must be > 0")
        result_parser = str(config.get("resultParser") or "").strip().lower()

        results: dict[int, str] = {}

        def _worker(index: int, item: Any) -> tuple[int, str]:
            ctx = dict(state)
            ctx["map_item"] = item
            ctx["map_index"] = index
            ctx.update(self._expand_map_item_context(item))
            self._acquire_rate_limit(node.id, node.policy.rate_limit)
            normalized = self._normalize_runner_output(node_runner(node, ctx))
            return index, str(normalized.get("raw_output") or "")

        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            futures = [executor.submit(_worker, idx, item) for idx, item in enumerate(items)]
            for future in as_completed(futures):
                idx, output = future.result()
                results[idx] = output

        ordered = [results[idx] for idx in range(len(items))]
        if result_parser == "json":
            parsed = [self._extract_json(item) if isinstance(item, str) else item for item in ordered]
            return {"raw_output": json.dumps(parsed, ensure_ascii=False), "items": parsed}
        return {"raw_output": json.dumps(ordered, ensure_ascii=False), "items": ordered}

    def _run_recursive(
        self,
        node: TaskNode,
        state: dict[str, Any],
        node_runner: Callable[[TaskNode, dict[str, Any]], Any],
    ) -> dict[str, Any]:
        config = node.execution_config or {}
        max_iters = int(config.get("maxIters") or 1)
        if max_iters <= 0:
            raise ValueError(f"node={node.id} maxIters must be > 0")
        stop_condition = config.get("stopCondition") if isinstance(config.get("stopCondition"), dict) else {}

        latest = ""
        for iteration in range(max_iters):
            ctx = dict(state)
            ctx["recursive_iter"] = iteration
            self._acquire_rate_limit(node.id, node.policy.rate_limit)
            normalized = self._normalize_runner_output(node_runner(node, ctx))
            latest = str(normalized.get("raw_output") or "")
            if self._is_recursive_stop(latest, stop_condition):
                break
        return {"raw_output": latest}

    def _execute_gate_node(
        self,
        node: GateNode,
        state: dict[str, Any],
        adjacency: dict[str, list[str]],
    ) -> dict[str, Any]:
        outcome = "success"
        routes = {route.on_outcome: route.to_node for route in node.routes}
        selected = routes.get(outcome) or routes.get("default")
        selected_targets = {selected} if selected else set(adjacency.get(node.id, []))
        for target in adjacency.get(node.id, []):
            if target in selected_targets:
                continue
            target_state = state["nodes"].get(target)
            if isinstance(target_state, dict) and target_state.get("status") == "queued":
                target_state["status"] = "skipped"
                target_state["error"] = f"gate {node.id} route outcome={outcome} not selected"
        return {"outcome": outcome, "selected_targets": sorted(selected_targets)}

    def _execute_artifact_node(
        self,
        node: ArtifactNode,
        state: dict[str, Any],
        adjacency: dict[str, list[str]],
    ) -> dict[str, Any]:
        _ = adjacency
        raw_output = ""
        for node_id, node_state in state["nodes"].items():
            if node_state.get("status") != "succeeded":
                continue
            output = node_state.get("output")
            if isinstance(output, dict) and isinstance(output.get("raw"), str):
                raw_output = output["raw"]
        ingest_summary = ingest_artifacts(
            response_text=raw_output,
            project_path=self.project_path,
            source={"run_id": state["run_id"], "node_id": node.id},
        )
        return {"action": "ingest", "metadata": {"node": node.id}, "ingest_summary": ingest_summary}

    def _is_recursive_stop(self, raw_output: str, stop_condition: dict[str, Any]) -> bool:
        if not stop_condition:
            return False
        if "contains" in stop_condition:
            token = str(stop_condition.get("contains") or "")
            return token != "" and token in raw_output
        if "equals" in stop_condition:
            return raw_output == str(stop_condition.get("equals"))
        return False

    def _resolve_parallel_items(self, node: TaskNode, state: dict[str, Any], config: dict[str, Any]) -> list[Any]:
        if isinstance(config.get("items"), list):
            return list(config.get("items") or [])
        items_from = config.get("itemsFrom")
        if not isinstance(items_from, dict):
            return []
        source = str(items_from.get("source") or "upstream").strip().lower()
        value: Any = None
        if source == "upstream":
            value = self._resolve_upstream_items(
                state,
                from_node=str(items_from.get("fromNode") or ""),
                port=str(items_from.get("port") or "raw"),
            )
        elif source == "variable":
            variables = state.get("variables") if isinstance(state.get("variables"), dict) else {}
            value = variables.get(str(items_from.get("key") or ""))
        if isinstance(items_from.get("jsonPath"), str) and items_from.get("jsonPath"):
            value = self._resolve_json_path(value, str(items_from.get("jsonPath") or ""))
        if value is None:
            return []
        if isinstance(value, list):
            return value
        raise ValueError(f"node={node.id} itemsFrom 必須解析為 list")

    @staticmethod
    def _resolve_upstream_items(state: dict[str, Any], *, from_node: str, port: str) -> Any:
        nodes = state.get("nodes")
        if not isinstance(nodes, dict):
            return None
        upstream_state = nodes.get(from_node)
        if not isinstance(upstream_state, dict):
            return None
        output = upstream_state.get("output")
        if port == "raw":
            if isinstance(output, dict):
                raw_text = output.get("raw") if "raw" in output else output.get("raw_output")
                if isinstance(raw_text, str):
                    parsed = TaskGraph3Runtime._parse_json_like(raw_text)
                    return parsed if parsed is not None else raw_text
            return output
        if not isinstance(output, dict):
            return None
        ports = output.get("ports")
        if isinstance(ports, dict):
            return ports.get(port)
        return output.get(port)

    @staticmethod
    def _parse_json_like(raw_text: str) -> Any:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            start_positions = [pos for pos in [raw_text.find("{"), raw_text.find("[")] if pos != -1]
            if not start_positions:
                return None
            start = min(start_positions)
            end = max(raw_text.rfind("}"), raw_text.rfind("]"))
            if end <= start:
                return None
            try:
                return json.loads(raw_text[start : end + 1])
            except json.JSONDecodeError:
                return None

    @staticmethod
    def _resolve_json_path(value: Any, path: str) -> Any:
        current = value
        for segment in [item for item in path.split(".") if item]:
            if isinstance(current, dict):
                current = current.get(segment)
                continue
            if isinstance(current, list) and segment.isdigit():
                index = int(segment)
                if 0 <= index < len(current):
                    current = current[index]
                    continue
            return None
        return current

    @staticmethod
    def _expand_map_item_context(item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        ctx = {"map_item_json": json.dumps(item, ensure_ascii=False)}
        for key, value in item.items():
            safe_key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(key)).strip("_")
            if not safe_key:
                continue
            if isinstance(value, (dict, list)):
                ctx[f"map_item_{safe_key}"] = json.dumps(value, ensure_ascii=False, indent=2)
            else:
                ctx[f"map_item_{safe_key}"] = value
        return ctx

    def _compile_control_graph(self, edges: list[GraphEdge]) -> tuple[dict[str, list[str]], dict[str, int]]:
        adjacency: dict[str, list[str]] = {node.id: [] for node in self.graph.nodes}
        incoming: dict[str, int] = {node.id: 0 for node in self.graph.nodes}
        seen_pairs: set[tuple[str, str]] = set()
        for edge in edges:
            if edge.status != "active":
                continue
            if edge.edge_type not in {"CONTROL", "DATA"}:
                continue
            pair = (edge.from_node, edge.to_node)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            adjacency[edge.from_node].append(edge.to_node)
            incoming[edge.to_node] += 1
        return adjacency, incoming

    def _acquire_rate_limit(self, node_id: str, rate_limit: int | None) -> None:
        if not rate_limit or rate_limit <= 0:
            return
        with self._rate_lock:
            rate = float(rate_limit)
            bucket = self._bucket_state.setdefault(node_id, {"tokens": rate, "last_refill": self._time()})
            now = self._time()
            elapsed = max(0.0, now - bucket["last_refill"])
            bucket["tokens"] = min(rate, bucket["tokens"] + elapsed * rate)
            bucket["last_refill"] = now
            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return
            wait_s = (1.0 - bucket["tokens"]) / rate
            self._sleep(wait_s)
            bucket["tokens"] = 0.0
            bucket["last_refill"] = self._time()

    def _emit_event(self, events_path: Path, payload: dict[str, Any], *, stream_limit: int | None) -> None:
        node_id = str(payload.get("node_id") or "")
        event_name = str(payload.get("event") or "")
        if not node_id or not stream_limit or stream_limit <= 0:
            append_jsonl(events_path, payload)
            return
        interval = 1.0 / float(stream_limit)
        status_key = str(payload.get("status") or "")
        key = f"{node_id}:{event_name}:{status_key}"
        state = self._stream_state.setdefault(key, {"last_emit": -1.0, "suppressed": 0})
        now = self._time()
        if state["last_emit"] < 0 or (now - state["last_emit"]) >= interval:
            if state["suppressed"] > 0:
                payload = dict(payload)
                payload["coalesced"] = int(state["suppressed"])
                state["suppressed"] = 0
            append_jsonl(events_path, payload)
            state["last_emit"] = now
            return
        state["suppressed"] += 1

    def _flush_stream(self, events_path: Path, node_id: str) -> None:
        prefix = f"{node_id}:"
        for key, stream in self._stream_state.items():
            if not key.startswith(prefix) or stream["suppressed"] <= 0:
                continue
            parts = key.split(":", 2)
            event_name = parts[1]
            status_name = parts[2] if len(parts) > 2 else ""
            payload = {"event": event_name, "node_id": node_id, "coalesced": int(stream["suppressed"])}
            if status_name:
                payload["status"] = status_name
            append_jsonl(events_path, payload)
            stream["suppressed"] = 0
            stream["last_emit"] = self._time()

    def _extract_ports(self, node: TaskNode, raw_output: str) -> dict[str, Any]:
        ports: dict[str, Any] = {}
        for port in node.output_contract.ports:
            value: Any = raw_output
            if port.extractor == "json":
                value = self._extract_json(raw_output)
            elif port.extractor == "line":
                value = raw_output.splitlines()[0] if raw_output else ""
            if port.parser == "json" and isinstance(value, str):
                value = json.loads(value)
            ports[port.name] = value
        return ports

    def _validate_output_contract(self, node: TaskNode, ports: dict[str, Any]) -> None:
        for port in node.output_contract.ports:
            value = ports.get(port.name)
            if port.type_ref is not None:
                self._validate_type_ref(node.id, port.name, value, port.type_ref)
            if port.json_schema is not None:
                self._validate_json_schema(node.id, port.name, value, port.json_schema)

    def _validate_type_ref(self, node_id: str, port_name: str, value: Any, type_ref: str) -> None:
        if type_ref == "string" and not isinstance(value, str):
            raise OutputContractError(f"node={node_id} port={port_name} typeRef=string mismatch")
        if type_ref == "object" and not isinstance(value, dict):
            raise OutputContractError(f"node={node_id} port={port_name} typeRef=object mismatch")
        if type_ref == "array" and not isinstance(value, list):
            raise OutputContractError(f"node={node_id} port={port_name} typeRef=array mismatch")
        if type_ref == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise OutputContractError(f"node={node_id} port={port_name} typeRef=number mismatch")

    def _validate_json_schema(self, node_id: str, port_name: str, value: Any, schema: dict[str, Any]) -> None:
        expected = schema.get("type")
        if expected:
            self._validate_type_ref(node_id, port_name, value, expected)
        required = schema.get("required") or []
        if required:
            if not isinstance(value, dict):
                raise OutputContractError(f"node={node_id} port={port_name} must be object for required fields")
            for key in required:
                if key not in value:
                    raise OutputContractError(f"node={node_id} port={port_name} missing required key={key}")

    def _extract_json(self, raw_output: str) -> Any:
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            start = raw_output.find("{")
            end = raw_output.rfind("}")
            if start < 0 or end <= start:
                raise OutputContractError("extractor=json failed")
            return json.loads(raw_output[start : end + 1])

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _normalize_runner_output(self, output: Any) -> dict[str, Any]:
        if isinstance(output, dict):
            if "raw_output" not in output:
                output = {"raw_output": json.dumps(output, ensure_ascii=False), **output}
            return output
        return {"raw_output": str(output)}

