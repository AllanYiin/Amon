from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from amon.graph_runtime import GraphRuntime


class _StubCore:
    def __init__(self) -> None:
        import logging

        self.logger = logging.getLogger("amon.test.graph-artifacts")

    def run_agent_task(self, prompt: str, **_: object) -> str:
        _ = prompt
        return """這是輸出\n```python file=workspace/a.py\nprint('ok')\n```\n"""


class GraphArtifactsIngestTests(unittest.TestCase):
    def test_agent_task_auto_ingest_workspace_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-graph-artifacts-") as tmpdir:
            project_path = Path(tmpdir)
            graph = {
                "nodes": [
                    {
                        "id": "agent",
                        "type": "agent_task",
                        "prompt": "請輸出程式",
                        "output_path": "docs/out.md",
                    }
                ],
                "edges": [],
            }
            graph_path = project_path / "graph.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

            os.environ["AMON_PROJECT_PATH"] = str(project_path)
            try:
                runtime = GraphRuntime(core=_StubCore(), project_path=project_path, graph_path=graph_path, run_id="run-1")
                result = runtime.run()
            finally:
                os.environ.pop("AMON_PROJECT_PATH", None)

            workspace_file = project_path / "workspace" / "a.py"
            self.assertTrue(workspace_file.exists())
            self.assertIn("print('ok')", workspace_file.read_text(encoding="utf-8"))

            manifest_path = project_path / ".amon" / "artifacts" / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("workspace/a.py", manifest.get("files", {}))

            state = result.state
            node_output = state["nodes"]["agent"]["output"]
            self.assertIn("ingest_summary", node_output)
            self.assertEqual(node_output["ingest_summary"]["created"], 1)
            self.assertEqual(node_output["ingest_summary"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
