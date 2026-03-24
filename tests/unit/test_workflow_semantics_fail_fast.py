import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.compiler_vnext import CompilerError, compile_manifest_workflow


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest"


def _load_manifest() -> AmonManifest:
    return AmonManifest.from_dict(json.loads((_fixture_root() / "pipeline_baseline_manifest.json").read_text(encoding="utf-8")))


class WorkflowSemanticsFailFastTests(unittest.TestCase):
    def test_condition_is_rejected_at_compile_time(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.nodes[1].update(condition={"type": "expression", "expr": "x > 0"})
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(CompilerError) as ctx:
            compile_manifest_workflow(manifest, workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_WORKFLOW_001")
        self.assertIn("field=condition", str(ctx.exception))

    def test_routes_are_rejected_at_compile_time(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"].clone()
        workflow.update(routes=[{"from": "research", "when": "success", "to": "memory_lookup"}])
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(CompilerError) as ctx:
            compile_manifest_workflow(manifest, workflow.id)

        self.assertEqual(ctx.exception.code, "AMON_WORKFLOW_001")
        self.assertIn("field=routes", str(ctx.exception))

    def test_depends_on_only_workflow_still_compiles(self) -> None:
        manifest = _load_manifest()

        result = compile_manifest_workflow(manifest, "workflow.vnext_baseline")

        self.assertEqual(result.workflow_ref, "workflow.vnext_baseline")
        self.assertEqual([edge.id for edge in result.graph.edges], ["research->memory_lookup", "memory_lookup->sandbox_probe"])


if __name__ == "__main__":
    unittest.main()
