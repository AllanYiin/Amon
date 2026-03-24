import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.binder import bind_workflow


def _load_manifest() -> AmonManifest:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest" / "pipeline_baseline_manifest.json"
    return AmonManifest.from_dict(json.loads(fixture_path.read_text(encoding="utf-8")))


class VNextManifestBaselineTests(unittest.TestCase):
    def test_fixture_manifest_roundtrips_and_validates(self) -> None:
        manifest = _load_manifest()

        manifest.validate_references()
        restored = AmonManifest.from_dict(manifest.to_dict())

        self.assertEqual(restored.version, "amon.manifest.v1")
        self.assertIn("workflow.vnext_baseline", restored.workflows)
        self.assertEqual([node.id for node in restored.workflows["workflow.vnext_baseline"].nodes], ["research", "memory_lookup", "sandbox_probe"])

    def test_binder_resolves_expected_executor_refs_for_unbound_nodes(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"]
        manifest.workflows["workflow.vnext_baseline"] = workflow.clone()
        manifest.workflows["workflow.vnext_baseline"].update(
            nodes=[replace(node, executor_ref="", status="draft") for node in workflow.nodes]
        )

        bound = bind_workflow(manifest, "workflow.vnext_baseline")

        self.assertEqual(
            {node.id: node.executor_ref for node in bound.nodes},
            {
                "research": "exec.researcher_llm",
                "memory_lookup": "exec.memory_tool",
                "sandbox_probe": "exec.probe_sandbox",
            },
        )
        self.assertEqual([node.status for node in bound.nodes], ["valid", "valid", "valid"])

    def test_binder_keeps_explicit_executor_refs_on_bound_fixture(self) -> None:
        manifest = _load_manifest()

        bound = bind_workflow(manifest, "workflow.vnext_baseline")

        self.assertEqual(
            [(node.id, node.executor_ref) for node in bound.nodes],
            [
                ("research", "exec.researcher_llm"),
                ("memory_lookup", "exec.memory_tool"),
                ("sandbox_probe", "exec.probe_sandbox"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
