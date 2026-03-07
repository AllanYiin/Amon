from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from amon.taskgraph3.amon_node_runner import AmonNodeRunner
from amon.taskgraph3.payloads import AgentTaskConfig, TaskSpec
from amon.taskgraph3.runtime import TaskGraph3Runtime
from amon.taskgraph3.schema import GraphDefinition, TaskNode


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
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="agent",
                        task_spec=TaskSpec(executor="agent", agent=AgentTaskConfig(prompt="請輸出程式")),
                    )
                ],
                edges=[],
            )

            runtime = TaskGraph3Runtime(project_path=project_path, graph=graph, run_id="run-1")
            os.environ["AMON_PROJECT_PATH"] = str(project_path)
            try:
                runner = AmonNodeRunner(
                    core=_StubCore(),
                    project_path=project_path,
                    run_id="run-1",
                    variables={},
                )
                result = runtime.run(runner.run_task)
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
