import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class QuickstartExampleTests(unittest.TestCase):
    def test_quickstart_graph_is_valid_v3_and_contains_expected_nodes(self) -> None:
        graph_path = Path(__file__).resolve().parents[1] / "examples" / "quickstart_project" / "graph.json"
        payload = json.loads(graph_path.read_text(encoding="utf-8"))

        self.assertEqual(payload.get("version"), "taskgraph.v3")
        nodes = payload.get("nodes", [])
        task_nodes = [node for node in nodes if node.get("node_type") == "TASK"]
        artifact_nodes = [node for node in nodes if node.get("node_type") == "ARTIFACT"]
        self.assertEqual(len(task_nodes), 4)
        self.assertGreaterEqual(len(artifact_nodes), 3)
        self.assertTrue(any(node.get("id") == "write_hello" for node in task_nodes))
        self.assertTrue(any(node.get("id") == "sandbox_transform" for node in task_nodes))

        artifact_titles = {node.get("title") for node in artifact_nodes}
        self.assertIn("docs/hello.txt", artifact_titles)
        self.assertIn("docs/agent_brief.md", artifact_titles)

        control_edges = [edge for edge in payload.get("edges", []) if edge.get("edge_type") == "CONTROL"]
        self.assertEqual(len(control_edges), 3)


if __name__ == "__main__":
    unittest.main()
