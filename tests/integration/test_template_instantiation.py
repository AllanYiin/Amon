import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.core import AmonCore
from amon.graph_presets import (
    build_self_critique_graph_payload,
    build_single_graph_payload,
    build_team_graph_payload,
)
from amon.templates import instantiate_builtin_template


class TemplateInstantiationIntegrationTests(unittest.TestCase):
    def test_single_template_matches_graph_preset_adapter(self) -> None:
        self.assertEqual(instantiate_builtin_template("single").graph_payload, build_single_graph_payload())

    def test_self_critique_template_matches_graph_preset_adapter(self) -> None:
        self.assertEqual(
            instantiate_builtin_template("self_critique").graph_payload,
            build_self_critique_graph_payload(),
        )

    def test_team_template_matches_core_builder(self) -> None:
        core = AmonCore()

        self.assertEqual(instantiate_builtin_template("team").graph_payload, core._build_team_graph())


if __name__ == "__main__":
    unittest.main()
