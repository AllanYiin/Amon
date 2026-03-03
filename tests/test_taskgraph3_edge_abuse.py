from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amon.taskgraph3.runtime import TaskGraph3Runtime
from amon.taskgraph3.schema import GraphDefinition, GraphEdge, TaskNode, validate_graph_definition


class TaskGraph3EdgeAbuseTests(unittest.TestCase):
    def test_duplicate_node_id_raises_validation_error(self) -> None:
        graph = GraphDefinition(nodes=[TaskNode(id="dup"), TaskNode(id="dup")], edges=[])
        with self.assertRaisesRegex(ValueError, "node.id 不可重複"):
            validate_graph_definition(graph)

    def test_missing_edge_endpoints_raise_validation_error(self) -> None:
        graph = GraphDefinition(
            nodes=[TaskNode(id="a")],
            edges=[GraphEdge(from_node="a", to_node="missing", edge_type="CONTROL", kind="next")],
        )
        with self.assertRaisesRegex(ValueError, "edge 指向不存在節點"):
            validate_graph_definition(graph)

    def test_start_run_twice_is_supported_as_parallel_run_ids(self) -> None:
        graph = GraphDefinition(nodes=[TaskNode(id="a")], edges=[])
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph)
            first = runtime.run(lambda *_: "first")
            second = runtime.run(lambda *_: "second")

            self.assertNotEqual(first.run_id, second.run_id)
            self.assertEqual(first.state["status"], "completed")
            self.assertEqual(second.state["status"], "completed")
            self.assertNotEqual(first.run_dir, second.run_dir)


if __name__ == "__main__":
    unittest.main()
