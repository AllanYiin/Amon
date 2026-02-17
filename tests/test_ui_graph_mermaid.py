import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.ui_server import AmonUIHandler


class GraphMermaidRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = AmonUIHandler.__new__(AmonUIHandler)

    def test_graph_to_mermaid_keeps_unique_node_ids_after_sanitization(self) -> None:
        graph = {
            "nodes": [
                {"id": "task-1"},
                {"id": "task_1"},
                {"id": "task 1"},
            ],
            "edges": [
                {"from": "task-1", "to": "task_1"},
                {"from": "task_1", "to": "task 1"},
            ],
        }

        mermaid = self.handler._graph_to_mermaid(graph)

        self.assertIn('  task_1["task-1"]', mermaid)
        self.assertIn('  task_1_2["task_1"]', mermaid)
        self.assertIn('  task_1_3["task 1"]', mermaid)
        self.assertIn("  task_1 --> task_1_2", mermaid)
        self.assertIn("  task_1_2 --> task_1_3", mermaid)

    def test_graph_to_mermaid_escapes_labels_and_ignores_unknown_edge_nodes(self) -> None:
        graph = {
            "nodes": [{"id": '"quote"\\node\nline'}],
            "edges": [{"from": '"quote"\\node\nline', "to": "missing-node"}],
        }

        mermaid = self.handler._graph_to_mermaid(graph)

        self.assertIn(r'  quote__node_line["\"quote\"\\node\nline"]', mermaid)
        self.assertNotIn("missing-node", mermaid)


if __name__ == "__main__":
    unittest.main()
