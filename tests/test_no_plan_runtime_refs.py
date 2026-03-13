import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_SCOPES = [
    ROOT / "src" / "amon" / "taskgraph3",
    ROOT / "src" / "amon" / "planning" / "compiler.py",
]

ALLOWED_FILES: set[Path] = set()


class NoPlanGraphRuntimeRefsTests(unittest.TestCase):
    def test_legacy_plan_schema_helpers_removed(self) -> None:
        self.assertFalse((ROOT / "src" / "amon" / "planning" / "schema.py").exists())
        self.assertFalse((ROOT / "src" / "amon" / "planning" / "render.py").exists())
        self.assertFalse((ROOT / "src" / "amon" / "planning" / "serialize.py").exists())
        self.assertFalse((ROOT / "tests" / "test_plan_schema.py").exists())

    def _iter_runtime_files(self):
        for scope in RUNTIME_SCOPES:
            if scope.is_dir():
                for path in scope.rglob("*.py"):
                    if path not in ALLOWED_FILES:
                        yield path
            elif scope.exists() and scope not in ALLOWED_FILES:
                yield scope

    def _find_matches(self, pattern: str) -> list[str]:
        regex = re.compile(pattern)
        matches: list[str] = []
        for path in self._iter_runtime_files():
            text = path.read_text(encoding="utf-8")
            if regex.search(text):
                matches.append(str(path.relative_to(ROOT)))
        return matches

    def test_no_plan_graph_as_runtime_type(self) -> None:
        matches = self._find_matches(r"\bPlanGraph\b")
        self.assertEqual(matches, [], f"runtime 主路徑不得引用 PlanGraph: {matches}")

    def test_no_plan_execute_main_mode_name(self) -> None:
        matches = self._find_matches(r"\bplan_execute\b")
        self.assertEqual(matches, [], f"runtime 主路徑不得使用 plan_execute 模式名: {matches}")

    def test_no_legacy_exec_graph_node_types_in_runtime_path(self) -> None:
        legacy_patterns = [
            r'"tool\.call"',
            r'"agent_task"',
            r'"write_file"',
            r'"condition"',
        ]
        found: dict[str, list[str]] = {}
        for pattern in legacy_patterns:
            matches = self._find_matches(pattern)
            if matches:
                found[pattern] = matches
        self.assertEqual(found, {}, f"runtime 主路徑發現 legacy node type: {found}")


if __name__ == "__main__":
    unittest.main()
