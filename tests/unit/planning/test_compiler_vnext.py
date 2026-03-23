import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.domain import AmonManifest
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.taskgraph3.validate import validate_v3_graph_json


class CompilerVNextTests(unittest.TestCase):
    def test_compile_manifest_workflow_outputs_valid_taskgraph(self) -> None:
        fixtures_root = Path(__file__).resolve().parents[2] / "fixtures"
        manifest = AmonManifest.from_dict(
            json.loads((fixtures_root / "manifests" / "spec_pipeline_manifest.json").read_text(encoding="utf-8"))
        )

        result = compile_manifest_workflow(manifest, "workflow.spec_pipeline")
        payload = result.compiled_graph

        validate_v3_graph_json(payload)
        self.assertEqual(payload["version"], "taskgraph.v3")
        self.assertEqual(payload["id"], "workflow.spec_pipeline")
        self.assertEqual(payload["nodes"][0]["taskSpec"]["executor"], "agent")
        self.assertEqual(payload["nodes"][0]["taskSpec"]["agent"]["allowedTools"], ["web.search"])
        self.assertIn("workflow", result.snapshot_pins)
        self.assertIn("task:task.concept_alignment", result.snapshot_pins)
        self.assertIn("executor:exec.researcher_llm", result.snapshot_pins)
        self.assertIn("agent:agent.researcher.v1", result.snapshot_pins)
        self.assertIn("tool_policy:policy.readonly_web", result.snapshot_pins)

    def test_fixture_compiled_graph_matches_expected_shape(self) -> None:
        fixtures_root = Path(__file__).resolve().parents[2] / "fixtures"
        manifest = AmonManifest.from_dict(
            json.loads((fixtures_root / "manifests" / "spec_pipeline_manifest.json").read_text(encoding="utf-8"))
        )
        expected = json.loads((fixtures_root / "compiled_graphs" / "spec_pipeline_compiled.json").read_text(encoding="utf-8"))

        result = compile_manifest_workflow(manifest, "workflow.spec_pipeline")

        self.assertEqual(result.compiled_graph, expected)


if __name__ == "__main__":
    unittest.main()
