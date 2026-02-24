from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amon.artifacts.store import ingest_response_artifacts


class ArtifactsStoreTests(unittest.TestCase):
    def test_ingest_writes_workspace_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-store-") as tmpdir:
            project_path = Path(tmpdir)
            response = "```python file=workspace/x.py\nprint('hello')\n```\n"
            results = ingest_response_artifacts(response, project_path)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "created")
            target = project_path / "workspace" / "x.py"
            self.assertEqual(target.read_text(encoding="utf-8"), "print('hello')\n")

    def test_reject_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-store-") as tmpdir:
            project_path = Path(tmpdir)
            response = "```python file=../x.py\nprint('hello')\n```\n"
            results = ingest_response_artifacts(response, project_path)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "error")
            self.assertFalse((project_path / "x.py").exists())

    def test_overwrite_creates_history_backup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-store-") as tmpdir:
            project_path = Path(tmpdir)
            target = project_path / "workspace" / "x.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")

            response = "```python file=workspace/x.py\nprint('new')\n```\n"
            results = ingest_response_artifacts(response, project_path)

            self.assertEqual(results[0].status, "updated")
            self.assertTrue(results[0].backup_path.startswith(".amon/artifacts/history/"))
            backup = project_path / results[0].backup_path
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), "old\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "print('new')\n")


if __name__ == "__main__":
    unittest.main()
