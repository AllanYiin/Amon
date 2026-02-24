import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class PlanExecGraphSmokeTests(unittest.TestCase):
    def test_import_amon_core(self) -> None:
        from amon.core import AmonCore

        self.assertIsNotNone(AmonCore)

    def test_import_graph_runtime(self) -> None:
        from amon.graph_runtime import GraphRuntime

        self.assertIsNotNone(GraphRuntime)

    def test_import_choose_execution_mode_variants(self) -> None:
        from amon.chat.project_bootstrap import choose_execution_mode
        from amon.chat.router_llm import choose_execution_mode_with_llm

        self.assertIsNotNone(choose_execution_mode)
        self.assertIsNotNone(choose_execution_mode_with_llm)


if __name__ == "__main__":
    unittest.main()
