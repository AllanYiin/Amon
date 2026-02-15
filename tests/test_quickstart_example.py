import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class QuickstartExampleTests(unittest.TestCase):
    def test_quickstart_graph_contains_expected_nodes(self) -> None:
        graph_path = Path(__file__).resolve().parents[1] / "examples" / "quickstart_project" / "graph.json"
        payload = json.loads(graph_path.read_text(encoding="utf-8"))

        nodes = payload.get("nodes", [])
        node_types = [node.get("type") for node in nodes]
        self.assertIn("write_file", node_types)
        self.assertIn("agent_task", node_types)
        self.assertIn("sandbox_run", node_types)

        write_paths = {node.get("path") for node in nodes if node.get("type") == "write_file"}
        self.assertIn("docs/hello.txt", write_paths)

        sandbox_nodes = [node for node in nodes if node.get("type") == "sandbox_run"]
        self.assertEqual(len(sandbox_nodes), 1)
        sandbox_node = sandbox_nodes[0]
        self.assertEqual(sandbox_node.get("language"), "python")
        self.assertIn("docs/hello.txt", sandbox_node.get("input_paths", []))


if __name__ == "__main__":
    unittest.main()
