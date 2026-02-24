from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amon.artifacts.safety import resolve_workspace_target


class ArtifactsSafetyTests(unittest.TestCase):
    def test_reject_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-safety-") as tmpdir:
            project_path = Path(tmpdir)
            with self.assertRaises(ValueError):
                resolve_workspace_target(project_path, "../evil.py")

    def test_reject_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-safety-") as tmpdir:
            project_path = Path(tmpdir)
            with self.assertRaises(ValueError):
                resolve_workspace_target(project_path, "/tmp/evil.py")

    def test_reject_windows_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-safety-") as tmpdir:
            project_path = Path(tmpdir)
            with self.assertRaises(ValueError):
                resolve_workspace_target(project_path, "C:/evil.py")

    def test_allow_unicode_filename(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-safety-") as tmpdir:
            project_path = Path(tmpdir)
            target = resolve_workspace_target(project_path, "workspace/資料夾/測試.py")
            self.assertTrue(str(target).endswith("workspace/資料夾/測試.py"))


if __name__ == "__main__":
    unittest.main()
