import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.domain.manifest_validation import ManifestValidationError


def _load_manifest() -> AmonManifest:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest" / "pipeline_baseline_manifest.json"
    return AmonManifest.from_dict(json.loads(fixture_path.read_text(encoding="utf-8")))


class ManifestValidationVNextTests(unittest.TestCase):
    def test_authoring_validation_allows_unbound_executor_ref(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(nodes=[replace(node, executor_ref="") for node in workflow.nodes])
        manifest.workflows[workflow.id] = workflow

        manifest.validate_references()
        manifest.validate_authoring(workflow.id)

    def test_authoring_validation_rejects_unresolved_executor_ref_when_present(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(nodes=[replace(workflow.nodes[0], executor_ref="exec.missing"), *workflow.nodes[1:]])
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(ManifestValidationError) as ctx:
            manifest.validate_authoring(workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_VALIDATION_002")
        self.assertIn("unresolved executor_ref", str(ctx.exception))

    def test_authoring_validation_rejects_duplicate_node_ids(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(nodes=[workflow.nodes[0], replace(workflow.nodes[1], id=workflow.nodes[0].id), workflow.nodes[2]])
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(ManifestValidationError) as ctx:
            manifest.validate_authoring(workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_VALIDATION_003")
        self.assertIn("duplicate node id", str(ctx.exception))

    def test_authoring_validation_rejects_missing_depends_on_node(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(nodes=[workflow.nodes[0], replace(workflow.nodes[1], depends_on=["missing-node"]), workflow.nodes[2]])
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(ManifestValidationError) as ctx:
            manifest.validate_authoring(workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_VALIDATION_004")
        self.assertIn("missing depends_on node", str(ctx.exception))

    def test_authoring_validation_rejects_self_dependency(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(nodes=[replace(workflow.nodes[0], depends_on=[workflow.nodes[0].id]), *workflow.nodes[1:]])
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(ManifestValidationError) as ctx:
            manifest.validate_authoring(workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_VALIDATION_005")
        self.assertIn("self dependency", str(ctx.exception))

    def test_authoring_validation_rejects_cycle(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(
            nodes=[
                replace(workflow.nodes[0], depends_on=["sandbox_probe"]),
                workflow.nodes[1],
                workflow.nodes[2],
            ]
        )
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(ManifestValidationError) as ctx:
            manifest.validate_authoring(workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_VALIDATION_006")
        self.assertIn("workflow cycle detected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
