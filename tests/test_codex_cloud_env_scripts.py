from __future__ import annotations

import os
from pathlib import Path
import unittest


class CodexCloudScriptsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_setup_script_contains_auto_then_fallback_flow(self) -> None:
        script = (self.repo_root / "scripts" / "codex_cloud_setup.sh").read_text(encoding="utf-8")
        self.assertIn('install -e', script)
        self.assertIn('install -r requirements.txt', script)
        self.assertIn('自動安裝失敗', script)

    def test_maintenance_script_runs_required_checks(self) -> None:
        script = (self.repo_root / "scripts" / "codex_cloud_maintenance.sh").read_text(encoding="utf-8")
        self.assertIn('python -m compileall src tests'.replace('python', '"${PYTHON_BIN}"'), script)
        self.assertIn("unittest discover -s tests -p 'test_*.py'", script)
        self.assertIn('"${PYTHON_BIN}" -m pip check', script)

    def test_scripts_are_executable(self) -> None:
        for relative in (
            Path("scripts/codex_cloud_setup.sh"),
            Path("scripts/codex_cloud_maintenance.sh"),
        ):
            path = self.repo_root / relative
            mode = path.stat().st_mode
            self.assertTrue(mode & os.X_OK, f"{relative} should be executable")


if __name__ == "__main__":
    unittest.main()
