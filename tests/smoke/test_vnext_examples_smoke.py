import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest


class VNextExamplesSmokeTests(unittest.TestCase):
    def test_manifest_example_is_parseable_and_valid(self) -> None:
        root = Path(__file__).resolve().parents[2]
        payload = json.loads((root / "examples" / "manifests" / "spec_pipeline.manifest.json").read_text(encoding="utf-8"))
        manifest = AmonManifest.from_dict(payload)
        manifest.validate_references()
        self.assertEqual(manifest.version, "amon.manifest.v1")

    def test_template_examples_are_parseable(self) -> None:
        root = Path(__file__).resolve().parents[2]
        for name in ("single", "self_critique", "team"):
            payload = json.loads((root / "examples" / "templates" / f"{name}.template.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["id"], name)
            self.assertIn("parameters", payload)


if __name__ == "__main__":
    unittest.main()
