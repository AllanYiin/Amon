from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from amon.taskgraph3.runtime import TaskGraph3Runtime
from amon.taskgraph3.schema import ArtifactNode, GateNode, GateRoute, GraphDefinition, GraphEdge, GroupNode, OutputContract, OutputPort, Policy, TaskNode


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _build_graph_from_fixture(path: Path) -> GraphDefinition:
    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes: list[TaskNode] = []
    for item in payload["nodes"]:
        output_contract = item.get("outputContract") or item.get("output_contract") or {}
        ports = [
            OutputPort(
                name=port["name"],
                extractor=port.get("extractor"),
                parser=port.get("parser"),
                json_schema=port.get("jsonSchema") or port.get("json_schema"),
                type_ref=port.get("typeRef") or port.get("type_ref"),
            )
            for port in output_contract.get("ports", [])
        ]
        policy_obj = item.get("policy", {})
        nodes.append(
            TaskNode(
                id=item["id"],
                title=item.get("title", ""),
                execution=item.get("execution", "SINGLE"),
                execution_config=item.get("executionConfig") if isinstance(item.get("executionConfig"), dict) else None,
                policy=Policy(
                    rate_limit=policy_obj.get("rateLimit", policy_obj.get("rate_limit")),
                    stream_limit=policy_obj.get("streamLimit", policy_obj.get("stream_limit")),
                ),
                output_contract=OutputContract(ports=ports),
            )
        )
    edges = [
        GraphEdge(
            from_node=edge.get("from_node", edge.get("from")),
            to_node=edge.get("to_node", edge.get("to")),
            edge_type=edge["edge_type"],
            kind=edge["kind"],
        )
        for edge in payload["edges"]
    ]
    return GraphDefinition(version=payload["version"], nodes=nodes, edges=edges)


class TaskGraph3RuntimeSmokeTests(unittest.TestCase):
    def test_smoke_run_linear_graph(self) -> None:
        fixture = Path("fixtures/graphs/v3_smoke.json")
        graph = _build_graph_from_fixture(fixture)
        clock = FakeClock()

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            runtime = TaskGraph3Runtime(project_path=project, graph=graph, run_id="run-smoke", time_func=clock.time, sleep_func=clock.sleep)

            def node_runner(node: TaskNode, _: dict[str, object]) -> str:
                clock.now += 0.02
                return json.dumps({"value": node.id, "artifact": f"{node.id}.txt"})

            result = runtime.run(node_runner)

            self.assertEqual(result.state["status"], "completed")
            self.assertEqual(result.state["nodes"]["n1"]["status"], "SUCCEEDED")
            self.assertEqual(result.state["nodes"]["n2"]["status"], "SUCCEEDED")
            self.assertEqual(result.state["nodes"]["n3"]["status"], "SUCCEEDED")
            self.assertIn("artifact", result.state["nodes"]["n3"]["output"]["ports"]["payload"])

            events_path = result.run_dir / "events.jsonl"
            lines = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(any(event.get("status") == "RUNNING" and event.get("node_id") == "n1" for event in lines))
            self.assertTrue(any(event.get("status") == "SUCCEEDED" and event.get("node_id") == "n3" for event in lines))

    def test_output_contract_failure_stops_downstream(self) -> None:
        graph = GraphDefinition(
            nodes=[
                TaskNode(
                    id="a",
                    output_contract=OutputContract(
                        ports=[OutputPort(name="payload", extractor="json", json_schema={"type": "object", "required": ["value"]}, type_ref="object")]
                    ),
                ),
                TaskNode(id="b"),
            ],
            edges=[GraphEdge(from_node="a", to_node="b", edge_type="CONTROL", kind="next")],
        )

        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-fail")
            result = runtime.run(lambda *_: json.dumps({"not_value": 1}))
            self.assertEqual(result.state["status"], "failed")
            self.assertEqual(result.state["nodes"]["a"]["status"], "FAILED")
            self.assertIn("missing required key=value", str(result.state["nodes"]["a"]["error"]))
            self.assertEqual(result.state["nodes"]["b"]["status"], "PENDING")

    def test_parallel_map_respects_max_concurrency_and_rate_limit(self) -> None:
        lock = threading.Lock()
        active = 0
        max_seen = 0
        invoked: list[float] = []
        graph = GraphDefinition(
            nodes=[
                TaskNode(
                    id="map",
                    execution="PARALLEL_MAP",
                    execution_config={"items": ["a", "b", "c"], "maxConcurrency": 2},
                    policy=Policy(rate_limit=2),
                    output_contract=OutputContract(ports=[OutputPort(name="items", extractor="json", type_ref="array")]),
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-map")

            def node_runner(_: TaskNode, ctx: dict[str, object]) -> str:
                nonlocal active, max_seen
                with lock:
                    active += 1
                    max_seen = max(max_seen, active)
                invoked.append(time.monotonic())
                time.sleep(0.02)
                with lock:
                    active -= 1
                return str(ctx.get("map_item", ""))

            result = runtime.run(node_runner)
            payload = result.state["nodes"]["map"]["output"]["ports"]["items"]
            self.assertEqual(payload, ["a", "b", "c"])
            self.assertLessEqual(max_seen, 2)
            self.assertEqual(result.state["nodes"]["map"]["status"], "SUCCEEDED")
            self.assertGreaterEqual(len(invoked), 3)

    def test_recursive_respects_stop_condition_and_max_iters(self) -> None:
        graph = GraphDefinition(
            nodes=[
                TaskNode(
                    id="recur",
                    execution="RECURSIVE",
                    execution_config={"maxIters": 5, "stopCondition": {"contains": "done"}},
                    output_contract=OutputContract(ports=[OutputPort(name="line", extractor="line", type_ref="string")]),
                )
            ]
        )

        calls: list[int] = []

        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-rec")

            def node_runner(_: TaskNode, ctx: dict[str, object]) -> str:
                idx = int(ctx.get("recursive_iter", 0))
                calls.append(idx)
                if idx >= 2:
                    return "done"
                return f"continue-{idx}"

            result = runtime.run(node_runner)
            self.assertEqual(result.state["status"], "completed")
            self.assertEqual(calls, [0, 1, 2])
            self.assertEqual(result.state["nodes"]["recur"]["output"]["ports"]["line"], "done")

    def test_rate_limit_and_stream_limit_are_applied(self) -> None:
        clock = FakeClock()
        graph = GraphDefinition(
            nodes=[
                TaskNode(
                    id="rate-node",
                    policy=Policy(rate_limit=1, stream_limit=1),
                )
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-rate", time_func=clock.time, sleep_func=clock.sleep)
            runtime._acquire_rate_limit("rate-node", 1)
            runtime._acquire_rate_limit("rate-node", 1)
            self.assertTrue(clock.sleeps and clock.sleeps[-1] >= 1.0)

            result = runtime.run(lambda *_: "ok")
            events_path = result.run_dir / "events.jsonl"
            runtime._emit_event(events_path, {"event": "node_log", "node_id": "rate-node", "line": "a"}, stream_limit=1)
            runtime._emit_event(events_path, {"event": "node_log", "node_id": "rate-node", "line": "b"}, stream_limit=1)
            runtime._flush_stream(events_path, "rate-node")
            events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(event.get("coalesced", 0) > 0 for event in events))

    def test_gate_node_routes_and_marks_unselected_as_skipped(self) -> None:
        graph = GraphDefinition(
            nodes=[
                GateNode(id="gate", routes=[GateRoute(on_outcome="success", to_node="next")]),
                TaskNode(id="next"),
                TaskNode(id="fallback"),
            ],
            edges=[
                GraphEdge(from_node="gate", to_node="next", edge_type="CONTROL", kind="success"),
                GraphEdge(from_node="gate", to_node="fallback", edge_type="CONTROL", kind="default"),
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-gate")
            result = runtime.run(lambda *_: "ok")
            self.assertEqual(result.state["status"], "completed")
            self.assertEqual(result.state["nodes"]["gate"]["output"]["outcome"], "success")
            self.assertEqual(result.state["nodes"]["fallback"]["status"], "SKIPPED")

    def test_group_node_fail_fast(self) -> None:
        graph = GraphDefinition(nodes=[GroupNode(id="grp", children=[])], edges=[])
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-group")
            result = runtime.run(lambda *_: "ok")
            self.assertEqual(result.state["status"], "failed")
            self.assertEqual(result.state["nodes"]["grp"]["status"], "FAILED")
            self.assertIn("fail-fast", result.state["nodes"]["grp"]["error"])

    def test_artifact_node_ingests_upstream_output(self) -> None:
        graph = GraphDefinition(
            nodes=[TaskNode(id="agent"), ArtifactNode(id="artifact")],
            edges=[GraphEdge(from_node="agent", to_node="artifact", edge_type="CONTROL", kind="next")],
        )
        response = "```python file=workspace/demo.py\nprint('v3')\n```"
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-artifact")
            result = runtime.run(lambda *_: response)
            self.assertEqual(result.state["nodes"]["artifact"]["status"], "SUCCEEDED")
            self.assertEqual(result.state["nodes"]["artifact"]["output"]["ingest_summary"]["created"], 1)


if __name__ == "__main__":
    unittest.main()
