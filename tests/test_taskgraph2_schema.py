import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.schema import (
    TaskEdge,
    TaskGraph,
    TaskNode,
    TaskNodeOutput,
    validate_task_graph,
)
from amon.taskgraph2.serialize import dumps_task_graph, loads_task_graph


class TaskGraph2SchemaTests(unittest.TestCase):
    def _valid_graph(self) -> TaskGraph:
        return TaskGraph(
            schema_version="2.0",
            objective="完成任務圖",
            session_defaults={"lang": "zh-TW"},
            nodes=[
                TaskNode(
                    id="N1",
                    title="Planner",
                    kind="planner",
                    description="規劃工作",
                    reads=["lang"],
                    writes={"plan": "json"},
                ),
                TaskNode(
                    id="N2",
                    title="執行",
                    kind="task",
                    description="執行計畫",
                    reads=["plan"],
                    writes={"report": "md"},
                ),
            ],
            edges=[TaskEdge(from_node="N1", to_node="N2")],
        )

    def test_validate_passes_for_valid_graph(self) -> None:
        validate_task_graph(self._valid_graph())

    def test_duplicate_node_id_raises(self) -> None:
        graph = self._valid_graph()
        graph.nodes.append(
            TaskNode(
                id="N1",
                title="Duplicate",
                kind="audit",
                description="重複 id",
            )
        )

        with self.assertRaisesRegex(ValueError, "node.id 不可重複"):
            validate_task_graph(graph)

    def test_edge_target_missing_raises(self) -> None:
        graph = self._valid_graph()
        graph.edges.append(TaskEdge(from_node="N2", to_node="N404"))

        with self.assertRaisesRegex(ValueError, "edge 指向不存在節點"):
            validate_task_graph(graph)

    def test_cycle_raises(self) -> None:
        graph = self._valid_graph()
        graph.edges.append(TaskEdge(from_node="N2", to_node="N1"))

        with self.assertRaisesRegex(ValueError, "DAG"):
            validate_task_graph(graph)

    def test_invalid_output_type_raises(self) -> None:
        graph = self._valid_graph()
        graph.nodes[0].output = TaskNodeOutput(type="yaml", extract="strict")

        with self.assertRaisesRegex(ValueError, "node.output.type 不合法"):
            validate_task_graph(graph)

    def test_loads_supports_code_fence_and_noise(self) -> None:
        raw = """以下是結果：\n```json\n{"schema_version":"2.0","objective":"ok","session_defaults":{},"nodes":[{"id":"A","title":"A","kind":"planner","description":"d","reads":[],"writes":{},"llm":{},"tools":[],"output":{"type":"text","extract":"best_effort"},"guardrails":{"allow_interrupt":true,"require_human_approval":false,"boundaries":[]},"retry":{"max_attempts":1,"backoff_s":1.0,"jitter_s":0.0},"timeout":{"inactivity_s":60,"hard_s":120}}],"edges":[]}\n```\n補充說明"""

        graph = loads_task_graph(raw)
        self.assertEqual(graph.schema_version, "2.0")
        self.assertEqual(graph.nodes[0].id, "A")

    def test_dumps_is_stable(self) -> None:
        graph = self._valid_graph()
        self.assertEqual(dumps_task_graph(graph), dumps_task_graph(graph))

    def test_tool_step_requires_tool_name(self) -> None:
        graph = self._valid_graph()
        graph.nodes[0].steps = [{"type": "tool", "args": {"q": "x"}}]

        with self.assertRaisesRegex(ValueError, "tool_name"):
            validate_task_graph(graph)

    def test_loads_roundtrip_with_steps(self) -> None:
        raw = """{"schema_version":"2.0","objective":"ok","session_defaults":{},"nodes":[{"id":"A","title":"A","kind":"tooling","description":"d","reads":[],"writes":{"echo":"text"},"llm":{},"tools":[],"steps":[{"type":"tool","tool_name":"test.echo","args":{"text":"hi"},"store_as":"echo"}],"output":{"type":"text","extract":"best_effort"},"guardrails":{"allow_interrupt":true,"require_human_approval":false,"boundaries":[]},"retry":{"max_attempts":1,"backoff_s":1.0,"jitter_s":0.0},"timeout":{"inactivity_s":60,"hard_s":120}}],"edges":[]}"""

        graph = loads_task_graph(raw)
        self.assertEqual(graph.nodes[0].steps[0]["tool_name"], "test.echo")
        dumped = dumps_task_graph(graph)
        self.assertIn('"steps"', dumped)


if __name__ == "__main__":
    unittest.main()
