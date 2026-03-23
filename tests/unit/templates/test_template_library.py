import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.templates import TemplateLibrary, instantiate_builtin_template


class TemplateLibraryTests(unittest.TestCase):
    def test_builtin_templates_are_loaded_from_library(self) -> None:
        library = TemplateLibrary()

        self.assertEqual(library.list_template_ids(), ["self_critique", "single", "team"])

    def test_instantiate_builtin_template_merges_defaults_and_returns_graph(self) -> None:
        instantiation = instantiate_builtin_template("single", {"prompt": "測試"})

        self.assertEqual(instantiation.template_id, "single")
        self.assertEqual(instantiation.variables["mode"], "single")
        self.assertEqual(instantiation.variables["prompt"], "測試")
        self.assertEqual(instantiation.graph_payload["nodes"][0]["id"], "single_task")


if __name__ == "__main__":
    unittest.main()
