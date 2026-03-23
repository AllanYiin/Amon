import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.compat import import_legacy_graph_payload
from amon.graph_presets import build_single_graph_payload


class LegacyGraphImporterIntegrationTests(unittest.TestCase):
    def test_builtin_single_graph_is_recognized_as_template(self) -> None:
        payload = build_single_graph_payload()

        imported = import_legacy_graph_payload(payload)

        self.assertEqual(imported["template_id"], "single")
        self.assertEqual(imported["source"], "builtin_template")
        self.assertEqual(imported["graph_payload"], payload)

    def test_unknown_legacy_graph_is_preserved_without_template_match(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [{"id": "custom", "node_type": "TASK", "taskSpec": {"executor": "agent", "agent": {"prompt": "x"}}}],
            "edges": [],
        }

        imported = import_legacy_graph_payload(payload)

        self.assertIsNone(imported["template_id"])
        self.assertEqual(imported["source"], "legacy_graph")
        self.assertEqual(imported["graph_payload"], payload)


if __name__ == "__main__":
    unittest.main()
