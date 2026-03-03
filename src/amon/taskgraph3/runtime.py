"""TaskGraph v3 SINGLE runtime with built-in cross-cutting capabilities."""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from amon.fs.atomic import append_jsonl, atomic_write_text

from .schema import GraphDefinition, GraphEdge, TaskNode, validate_graph_definition


class OutputContractError(ValueError):
    """Raised when a node output violates outputContract."""


@dataclass
class TaskGraph3RunResult:
    run_id: str
    run_dir: Path
    state: dict[str, Any]


class TaskGraph3Runtime:
    """Deterministic v3 runtime for SINGLE execution graphs."""

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

    def run(self, node_runner: Callable[[TaskNode, dict[str, Any]], str]) -> TaskGraph3RunResult:
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
                    "status": "READY" if incoming.get(node_id, 0) == 0 else "PENDING",
                    "attempt_logs": [],
                    "output": None,
                    "error": None,
                }
                for node_id in nodes
            },
            "metrics": {
                "counters": {"nodes_total": len(nodes), "nodes_succeeded": 0, "nodes_failed": 0},
                "latency_ms": {},
            },
        }

        self._write_json(resolved_path, {"version": self.graph.version, "nodes": [self._node_to_dict(n) for n in self.graph.nodes], "edges": [self._edge_to_dict(e) for e in self.graph.edges]})
        self._emit_event(events_path, {"event": "run_start", "run_id": run_id}, stream_limit=None)

        while ready:
            node_id = ready.popleft()
            node = nodes[node_id]
            if not isinstance(node, TaskNode):
                continue

            node_state = state["nodes"][node_id]
            node_state["status"] = "RUNNING"
            self._emit_event(events_path, {"event": "node_status", "node_id": node_id, "status": "RUNNING"}, stream_limit=node.policy.stream_limit)

            try:
                self._acquire_rate_limit(node.id, node.policy.rate_limit)
                started = self._time()
                raw_output = node_runner(node, state)
                node_state["attempt_logs"].append(f"attempt=1 output_len={len(raw_output)}")
                extracted = self._extract_ports(node, raw_output)
                self._validate_output_contract(node, extracted)
                self._flush_stream(events_path, node.id)

                latency_ms = int((self._time() - started) * 1000)
                state["metrics"]["latency_ms"][node_id] = latency_ms
                state["metrics"]["counters"]["nodes_succeeded"] += 1
                node_state["status"] = "SUCCEEDED"
                node_state["output"] = {"raw": raw_output, "ports": extracted}
                self._emit_event(events_path, {"event": "node_status", "node_id": node_id, "status": "SUCCEEDED", "latency_ms": latency_ms}, stream_limit=node.policy.stream_limit)
            except Exception as exc:  # noqa: BLE001
                self._flush_stream(events_path, node.id)
                state["metrics"]["counters"]["nodes_failed"] += 1
                node_state["status"] = "FAILED"
                node_state["error"] = str(exc)
                node_state["attempt_logs"].append(f"attempt=1 failed={exc}")
                self._emit_event(events_path, {"event": "node_status", "node_id": node_id, "status": "FAILED", "error": str(exc)}, stream_limit=node.policy.stream_limit)
                state["status"] = "failed"
                break

            for nxt in adjacency.get(node_id, []):
                incoming[nxt] -= 1
                if incoming[nxt] == 0 and state["nodes"][nxt]["status"] == "PENDING":
                    state["nodes"][nxt]["status"] = "READY"
                    ready.append(nxt)

        if state["status"] == "running":
            state["status"] = "completed"

        self._emit_event(events_path, {"event": "run_end", "run_id": run_id, "status": state["status"]}, stream_limit=None)
        self._write_json(state_path, state)
        return TaskGraph3RunResult(run_id=run_id, run_dir=run_dir, state=state)

    def _compile_control_graph(self, edges: list[GraphEdge]) -> tuple[dict[str, list[str]], dict[str, int]]:
        adjacency: dict[str, list[str]] = {node.id: [] for node in self.graph.nodes}
        incoming: dict[str, int] = {node.id: 0 for node in self.graph.nodes}
        for edge in edges:
            if edge.edge_type != "CONTROL":
                continue
            adjacency[edge.from_node].append(edge.to_node)
            incoming[edge.to_node] += 1
        return adjacency, incoming

    def _acquire_rate_limit(self, node_id: str, rate_limit: int | None) -> None:
        if not rate_limit or rate_limit <= 0:
            return
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

    def _node_to_dict(self, node: Any) -> dict[str, Any]:
        payload = {"id": node.id, "node_type": node.node_type, "title": node.title}
        if isinstance(node, TaskNode):
            payload["policy"] = {"rateLimit": node.policy.rate_limit, "streamLimit": node.policy.stream_limit}
            payload["outputContract"] = {
                "ports": [
                    {
                        "name": p.name,
                        "extractor": p.extractor,
                        "parser": p.parser,
                        "jsonSchema": p.json_schema,
                        "typeRef": p.type_ref,
                    }
                    for p in node.output_contract.ports
                ]
            }
        return payload

    def _edge_to_dict(self, edge: GraphEdge) -> dict[str, Any]:
        return {"from": edge.from_node, "to": edge.to_node, "edge_type": edge.edge_type, "kind": edge.kind}
