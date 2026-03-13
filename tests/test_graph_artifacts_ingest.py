from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from amon.taskgraph3.amon_node_runner import AmonNodeRunner
from amon.taskgraph3.payloads import AgentTaskConfig, InputBinding, TaskSpec
from amon.taskgraph3.runtime import TaskGraph3Runtime
from amon.taskgraph3.schema import GraphDefinition, TaskNode


class _StubCore:
    def __init__(self) -> None:
        import logging

        self.logger = logging.getLogger("amon.test.graph-artifacts")
        self.calls: list[dict[str, object]] = []

    def run_agent_task(self, prompt: str, **_: object) -> str:
        self.calls.append({"prompt": prompt, **_})
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

    def test_agent_task_resolves_upstream_input_bindings_and_conversation_history(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-graph-bindings-") as tmpdir:
            project_path = Path(tmpdir)
            history = [
                {"role": "user", "content": "前一輪需求"},
                {"role": "assistant", "content": "先做概念對齊"},
            ]
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        task_spec=TaskSpec(executor="agent", agent=AgentTaskConfig(prompt="先整理概念")),
                    ),
                    TaskNode(
                        id="writer",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="請延續以下內容：\n${concept_alignment_context}"),
                            input_bindings=[
                                InputBinding(
                                    source="upstream",
                                    key="concept_alignment_context",
                                    from_node="concept_alignment",
                                    port="raw",
                                )
                            ],
                        ),
                    ),
                ],
                edges=[],
            )

            core = _StubCore()
            runner = AmonNodeRunner(
                core=core,
                project_path=project_path,
                run_id="run-bindings",
                variables={"conversation_history": history},
            )
            writer = next(node for node in graph.nodes if isinstance(node, TaskNode) and node.id == "writer")
            context = {
                "nodes": {
                    "concept_alignment": {
                        "status": "SUCCEEDED",
                        "output": {
                            "raw": "概念摘要：TaskGraph v3 需承接上一節點結果。",
                            "ports": {},
                        },
                    }
                }
            }

            runner.run_task(writer, context)

            self.assertEqual(len(core.calls), 1)
            self.assertIn("概念摘要：TaskGraph v3", str(core.calls[0]["prompt"]))
            self.assertEqual(core.calls[0]["conversation_history"], history)


if __name__ == "__main__":
    unittest.main()
