from __future__ import annotations

import unittest

from amon.taskgraph3.schema import (
    GateNode,
    GateRoute,
    GraphDefinition,
    GraphEdge,
    GroupNode,
    TaskNode,
    validate_graph_definition,
)
from amon.taskgraph3.serialize import dumps_graph_definition


class TaskGraph3SchemaTests(unittest.TestCase):
    def test_invalid_edge_endpoint_fails(self) -> None:
        graph = GraphDefinition(
            nodes=[TaskNode(id="task-1")],
            edges=[GraphEdge(from_node="task-1", to_node="missing", edge_type="CONTROL", kind="next")],
        )

        with self.assertRaisesRegex(ValueError, "edge 指向不存在節點"):
            validate_graph_definition(graph)

    def test_duplicate_node_id_fails(self) -> None:
        graph = GraphDefinition(nodes=[TaskNode(id="dup"), GroupNode(id="dup")])

        with self.assertRaisesRegex(ValueError, "node.id 不可重複"):
            validate_graph_definition(graph)

    def test_invalid_gate_on_outcome_fails(self) -> None:
        graph = GraphDefinition(
            nodes=[
                GateNode(id="gate-1", routes=[GateRoute(on_outcome="maybe", to_node="task-1")]),
                TaskNode(id="task-1"),
            ]
        )

        with self.assertRaisesRegex(ValueError, "gate.routes.on_outcome 不合法"):
            validate_graph_definition(graph)

    def test_dumps_graph_definition_is_deterministic(self) -> None:
        graph = GraphDefinition(
            nodes=[
                TaskNode(id="task-1"),
                GroupNode(id="group-1", children=["task-1"]),
            ],
            edges=[GraphEdge(from_node="group-1", to_node="task-1", edge_type="CONTROL", kind="contains")],
        )

        output_one = dumps_graph_definition(graph)
        output_two = dumps_graph_definition(graph)

        self.assertEqual(output_one, output_two)
        self.assertIn('"version":"taskgraph.v3"', output_one)


if __name__ == "__main__":
    unittest.main()
