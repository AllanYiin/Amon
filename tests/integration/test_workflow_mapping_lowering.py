from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.taskgraph3.amon_node_runner import AmonNodeRunner
from amon.taskgraph3.runtime import TaskGraph3Runtime


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest"


def _load_manifest() -> AmonManifest:
    return AmonManifest.from_dict(json.loads((_fixture_root() / "workflow_mapping_manifest.json").read_text(encoding="utf-8")))


class _AgentCoreStub:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def run_agent_task(self, prompt: str, **kwargs: object) -> str:
        self.prompts.append(prompt)
        return prompt


class WorkflowMappingLoweringTests(unittest.TestCase):
    def test_manifest_mapping_lowers_to_runtime_data_flow(self) -> None:
        compile_result = compile_manifest_workflow(_load_manifest(), "workflow.vnext_mapping")
        graph = compile_result.graph
        nodes = {node.id: node for node in graph.nodes}
        edges = {edge.id: edge for edge in graph.edges}

        self.assertEqual(
            [binding.from_node for binding in nodes["writer"].task_spec.input_bindings if binding.source == "upstream"],
            ["research"],
        )
        self.assertEqual(
            [binding.port for binding in nodes["publisher"].task_spec.input_bindings if binding.source == "upstream"],
            ["reviewed_summary"],
        )
        self.assertIn("research->writer:source_summary", edges)
        self.assertEqual(edges["research->writer:source_summary"].edge_type, "DATA")
        self.assertIn("writer->publisher:content", edges)
        self.assertEqual(
            graph.metadata["workflow_semantics"]["output_bindings"]["writer_reviewed"]["port"],
            "reviewed_summary",
        )

        core = _AgentCoreStub()
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskGraph3Runtime(project_path=Path(tmp), graph=graph, run_id="run-stage6")
            runner = AmonNodeRunner(
                core=core,
                project_path=Path(tmp),
                run_id="run-stage6",
                variables={},
            )
            with patch("amon.taskgraph3.amon_node_runner.load_feature_flags", return_value=SimpleNamespace(runtime=False)):
                result = runtime.run(runner.run_task)

        self.assertEqual(result.state["status"], "succeeded")
        self.assertEqual(core.prompts, ["stage6 seed", "reviewed:stage6 seed", "final:reviewed:stage6 seed"])
        self.assertEqual(
            result.state["nodes"]["writer"]["output"]["ports"]["reviewed_summary"],
            "reviewed:stage6 seed",
        )
        self.assertEqual(
            result.state["nodes"]["publisher"]["output"]["ports"]["final_text"],
            "final:reviewed:stage6 seed",
        )
        self.assertEqual(
            result.state["graph_output"],
            {
                "final_text": "final:reviewed:stage6 seed",
                "writer_reviewed": "reviewed:stage6 seed",
            },
        )


if __name__ == "__main__":
    unittest.main()
