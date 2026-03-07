from __future__ import annotations

from pathlib import Path
import unittest


class AntiLegacyGraphScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_path_name_scan_avoids_substring_false_positive(self) -> None:
        script = (self.repo_root / "scripts" / "anti_legacy_graph.sh").read_text(encoding="utf-8")
        self.assertIn("if 'taskgraph2' in rel_parts:", script)
        self.assertIn("if path.name == 'graph_runtime.py':", script)
        self.assertNotIn("if 'taskgraph2' in rel or 'graph_runtime' in rel:", script)


if __name__ == "__main__":
    unittest.main()
