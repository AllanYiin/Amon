from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from amon.artifacts.store import ingest_artifacts, ingest_response_artifacts


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
            manifest_path = project_path / ".amon" / "artifacts" / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = manifest["files"]["workspace/x.py"]
            self.assertEqual(entry["write_status"], "created")
            self.assertEqual(entry["status"], "valid")

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
            manifest = json.loads((project_path / ".amon" / "artifacts" / "manifest.json").read_text(encoding="utf-8"))
            entry = manifest["files"]["workspace/x.py"]
            self.assertEqual(entry["write_status"], "updated")


    def test_ingest_supports_filename_info_and_returns_artifact_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-store-") as tmpdir:
            project_path = Path(tmpdir)
            response = "```html filename=index.html\n<html><body>tetris</body></html>\n```\n"
            summary = ingest_artifacts(
                response_text=response,
                project_path=project_path,
                source={"run_id": "run-demo", "node_id": "writer"},
            )
            target = project_path / "workspace" / "index.html"
            self.assertTrue(target.exists())
            self.assertEqual(summary["created"], 1)
            self.assertEqual(summary["artifacts"][0]["path"], "workspace/index.html")
            self.assertEqual(summary["artifacts"][0]["mime"], "text/html")
            self.assertEqual(summary["artifacts"][0]["run_id"], "run-demo")
            self.assertEqual(summary["artifacts"][0]["node_id"], "writer")


if __name__ == "__main__":
    unittest.main()
