import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest


class ManifestContractTests(unittest.TestCase):
    def test_manifest_fixture_round_trip_and_refs_are_valid(self) -> None:
        fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "manifests" / "spec_pipeline_manifest.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))

        manifest = AmonManifest.from_dict(payload)
        manifest.validate_references()

        self.assertEqual(manifest.version, "amon.manifest.v1")
        self.assertEqual(manifest.project.id, "project.demo")
        self.assertIn("workflow.spec_pipeline", manifest.workflows)
        self.assertEqual(manifest.to_dict()["project"]["name"], "Demo")

    def test_manifest_validation_fails_for_unresolved_executor_ref(self) -> None:
        fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "manifests" / "spec_pipeline_manifest.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["workflows"]["workflow.spec_pipeline"]["nodes"][0]["executor_ref"] = "exec.missing"

        manifest = AmonManifest.from_dict(payload)

        with self.assertRaisesRegex(ValueError, "unresolved executor_ref"):
            manifest.validate_references()


if __name__ == "__main__":
    unittest.main()
