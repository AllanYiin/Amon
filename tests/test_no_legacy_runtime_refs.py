import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class NoLegacyRuntimeRefsTests(unittest.TestCase):
    def test_legacy_runtime_compatibility_modules_removed(self) -> None:
        self.assertFalse((SRC / "amon" / "taskgraph3" / "engine_runtime.py").exists())
        self.assertFalse((SRC / "amon" / "taskgraph3" / "migrate.py").exists())

    def test_no_legacy_graph_runtime_filename_in_tests(self) -> None:
        legacy_test_path = ROOT / "tests" / "test_legacy_graph_runtime.py"
        self.assertFalse(
            legacy_test_path.exists(),
            f"發現 legacy 測試檔名，請改名避免觸發 anti-legacy-graph: {legacy_test_path.relative_to(ROOT)}",
        )

    def _scan(self, pattern: str, *, include_tests: bool = False) -> list[str]:
        roots = [SRC]
        if include_tests:
            roots.append(ROOT / "tests")

        matches: list[str] = []
        regex = re.compile(pattern)
        for base in roots:
            for path in base.rglob("*.py"):
                if path.name.startswith("test_no_legacy_runtime_refs"):
                    continue
                text = path.read_text(encoding="utf-8")
                if regex.search(text):
                    matches.append(str(path.relative_to(ROOT)))
        return matches

    def test_no_compile_plan_to_exec_graph_symbol(self) -> None:
        matches = self._scan(r"\bcompile_plan_to_exec_graph\b")
        self.assertEqual(matches, [], f"發現 legacy compiler symbol: {matches}")

    def test_no_legacy_graph_runtime_symbol_or_import(self) -> None:
        symbol_matches = self._scan(r"\bGraphRuntime\b")
        import_matches = self._scan(r"legacy_graph_runtime|LegacyGraphRuntime|amon\.taskgraph3\.engine_runtime")
        self.assertEqual(symbol_matches, [], f"發現 legacy runtime symbol: {symbol_matches}")
        self.assertEqual(import_matches, [], f"發現 legacy runtime import: {import_matches}")


if __name__ == "__main__":
    unittest.main()
