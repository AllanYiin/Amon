from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from amon.taskgraph3.runtime import TaskGraph3Runtime
from amon.taskgraph3.schema import GraphDefinition, GraphEdge, OutputContract, OutputPort, Policy, TaskNode


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
        ports = [
            OutputPort(
                name=port["name"],
                extractor=port.get("extractor"),
                parser=port.get("parser"),
                json_schema=port.get("json_schema"),
                type_ref=port.get("type_ref"),
            )
            for port in item.get("output_contract", {}).get("ports", [])
        ]
        policy_obj = item.get("policy", {})
        nodes.append(
            TaskNode(
                id=item["id"],
                title=item.get("title", ""),
                policy=Policy(rate_limit=policy_obj.get("rate_limit"), stream_limit=policy_obj.get("stream_limit")),
                output_contract=OutputContract(ports=ports),
            )
        )
    edges = [GraphEdge(**edge) for edge in payload["edges"]]
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


if __name__ == "__main__":
    unittest.main()
