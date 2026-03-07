import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.planning.compiler import LegacyPlanCompilerRemovedError, normalize_graph_definition_payload


class PlanCompilerTests(unittest.TestCase):
    def test_normalize_graph_definition_payload_accepts_taskgraph_v3(self) -> None:
        payload = {"version": "taskgraph.v3", "nodes": [], "edges": []}
        self.assertIs(normalize_graph_definition_payload(payload), payload)

    def test_normalize_graph_definition_payload_rejects_legacy_payload(self) -> None:
        with self.assertRaises(LegacyPlanCompilerRemovedError):
            normalize_graph_definition_payload({"nodes": [], "edges": []})

    def test_removed_legacy_compiler_symbol_is_not_importable(self) -> None:
        import amon.planning.compiler as compiler

        self.assertFalse(hasattr(compiler, "compile_plan_to_exec_graph"))


if __name__ == "__main__":
    unittest.main()
