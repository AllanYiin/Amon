import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.binder import bind_workflow
from amon.planning.compiler_vnext import CompilerError, compile_manifest_workflow


def _load_manifest() -> AmonManifest:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest" / "pipeline_baseline_manifest.json"
    return AmonManifest.from_dict(json.loads(fixture_path.read_text(encoding="utf-8")))


class BindThenCompileValidationIntegrationTests(unittest.TestCase):
    def test_unbound_workflow_cannot_compile_directly(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(nodes=[replace(node, executor_ref="", status="draft") for node in workflow.nodes])
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(CompilerError) as ctx:
            compile_manifest_workflow(manifest, workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_VALIDATION_007")
        self.assertIn("unbound executor_ref", str(ctx.exception))

    def test_authoring_valid_then_bind_then_compile_succeeds(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(nodes=[replace(node, executor_ref="", status="draft") for node in workflow.nodes])
        manifest.workflows[workflow.id] = workflow

        manifest.validate_authoring(workflow.id)
        bound = bind_workflow(manifest, workflow.id)
        manifest.workflows[workflow.id] = bound
        result = compile_manifest_workflow(manifest, workflow.id)

        self.assertEqual([node["metadata"]["executor_type"] for node in result.compiled_graph["nodes"]], ["llm", "tool", "sandbox"])


if __name__ == "__main__":
    unittest.main()
