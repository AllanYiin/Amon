import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.taskgraph3.validate import validate_v3_graph_json


class CompiledGraphContractTests(unittest.TestCase):
    def test_compiled_graph_fixture_is_valid_v3_payload(self) -> None:
        fixtures_root = Path(__file__).resolve().parents[1] / "fixtures"
        manifest = AmonManifest.from_dict(
            json.loads((fixtures_root / "manifests" / "spec_pipeline_manifest.json").read_text(encoding="utf-8"))
        )

        result = compile_manifest_workflow(manifest, "workflow.spec_pipeline")
        payload = result.compiled_graph

        validate_v3_graph_json(payload)
        self.assertEqual(payload["version"], "taskgraph.v3")
        self.assertEqual(payload["metadata"]["source_manifest_version"], "amon.manifest.v1")
        self.assertIn("snapshotPins", payload["metadata"])
        self.assertEqual(payload["metadata"]["snapshotPins"]["workflow"]["ref"], "workflow.spec_pipeline")

    def test_compiled_graph_snapshot_pins_cover_task_executor_agent_and_policy(self) -> None:
        fixtures_root = Path(__file__).resolve().parents[1] / "fixtures"
        manifest = AmonManifest.from_dict(
            json.loads((fixtures_root / "manifests" / "spec_pipeline_manifest.json").read_text(encoding="utf-8"))
        )

        result = compile_manifest_workflow(manifest, "workflow.spec_pipeline")
        pins = {key: value.to_dict() for key, value in result.snapshot_pins.items()}

        self.assertEqual(pins["workflow"]["kind"], "workflow")
        self.assertEqual(pins["task:task.concept_alignment"]["kind"], "task")
        self.assertEqual(pins["executor:exec.researcher_llm"]["kind"], "executor")
        self.assertEqual(pins["agent:agent.researcher.v1"]["kind"], "agent_profile")
        self.assertEqual(pins["tool_policy:policy.readonly_web"]["kind"], "tool_policy")


if __name__ == "__main__":
    unittest.main()
