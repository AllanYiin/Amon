from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.core import AmonCore
from amon.taskgraph3.runtime import TaskGraph3Runtime
from amon.taskgraph3.schema import GraphDefinition, OutputContract, OutputPort, TaskNode


class GraphOutputBindingsTests(unittest.TestCase):
    def test_runtime_resolves_node_output_aliases_into_graph_output(self) -> None:
        graph = GraphDefinition(
            nodes=[
                TaskNode(
                    id="writer",
                    output_contract=OutputContract(ports=[OutputPort(name="draft", type_ref="string")]),
                )
            ],
            metadata={
                "workflow_semantics": {
                    "node_output_mappings": {
                        "writer": {
                            "reviewed_summary": {"source": "port", "port": "draft"},
                        }
                    },
                    "output_bindings": {
                        "final_text": {"from_node": "writer", "port": "reviewed_summary"},
                    },
                }
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-graph-output")
            result = runtime.run(lambda *_: "mapped output")

        self.assertEqual(result.state["status"], "succeeded")
        self.assertEqual(result.state["nodes"]["writer"]["output"]["ports"]["draft"], "mapped output")
        self.assertEqual(result.state["nodes"]["writer"]["output"]["ports"]["reviewed_summary"], "mapped output")
        self.assertEqual(result.state["graph_output"]["final_text"], "mapped output")

    def test_core_primary_output_prefers_graph_output_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("graph-output-binding")
                project_path = Path(project.path)
                run_dir = project_path / ".amon" / "runs" / "run-graph-output"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "graph.resolved.json").write_text(
                    json.dumps(
                        {
                            "nodes": [
                                {"id": "writer", "taskSpec": {"executor": "agent"}},
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                (run_dir / "state.json").write_text(
                    json.dumps(
                        {
                            "graph_output": {
                                "final_text": "graph level final",
                            },
                            "nodes": {
                                "writer": {"output": {"raw": "stale raw output"}},
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                self.assertEqual(core._load_graph_primary_output(run_dir), "graph level final")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
