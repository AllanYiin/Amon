import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class GraphRuntimeTests(unittest.TestCase):
    def test_graph_run_creates_state_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Graph 專案")
                project_path = Path(project.path)
                core.set_config_value(
                    "providers.mock",
                    {
                        "type": "mock",
                        "default_model": "mock-model",
                        "stream_chunks": ["OK"],
                    },
                    project_path=project_path,
                )
                core.set_config_value("amon.provider", "mock", project_path=project_path)

                graph = {
                    "variables": {"name": "Amon"},
                    "nodes": [
                        {
                            "id": "write",
                            "type": "write_file",
                            "path": "output.txt",
                            "content": "Hello ${name}",
                        },
                        {
                            "id": "agent",
                            "type": "agent_task",
                            "prompt": "Hi ${name}",
                        },
                    ],
                    "edges": [{"from": "write", "to": "agent"}],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                result = core.run_graph(project_path=project_path, graph_path=graph_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            run_dir = result.run_dir
            state_path = run_dir / "state.json"
            resolved_path = run_dir / "graph.resolved.json"
            events_path = run_dir / "events.jsonl"

            self.assertTrue(state_path.exists())
            self.assertTrue(resolved_path.exists())
            self.assertTrue(events_path.exists())

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "completed")
            self.assertIn("write", state["nodes"])
            self.assertIn("agent", state["nodes"])
            self.assertEqual(state["nodes"]["write"]["status"], "completed")
            self.assertEqual(state["nodes"]["agent"]["status"], "completed")

            output_path = project_path / "output.txt"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "Hello Amon")


if __name__ == "__main__":
    unittest.main()
