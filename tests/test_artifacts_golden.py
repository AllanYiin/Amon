from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amon.artifacts.store import ingest_artifacts


class ArtifactsGoldenTests(unittest.TestCase):
    def test_valid_single_multi_and_subdir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-golden-") as tmpdir:
            project_path = Path(tmpdir)
            response = (
                "```python file=workspace/app.py\nprint('a')\n```\n"
                "```js file=workspace/web/main.js\nconsole.log('b');\n```\n"
            )
            summary = ingest_artifacts(response, project_path)
            self.assertEqual(summary["total"], 2)
            self.assertEqual(summary["created"], 2)
            self.assertEqual(summary["errors"], 0)
            self.assertTrue((project_path / "workspace" / "app.py").exists())
            self.assertTrue((project_path / "workspace" / "web" / "main.js").exists())

    def test_invalid_paths_and_fence_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-golden-") as tmpdir:
            project_path = Path(tmpdir)
            response = (
                "```python file=../evil.py\nprint('x')\n```\n"
                "```python file=/tmp/evil.py\nprint('x')\n```\n"
                "```python\nprint('missing file')\n```\n"
                "```python file=workspace/unclosed.py\nprint('x')\n"
            )
            summary = ingest_artifacts(response, project_path)
            self.assertEqual(summary["total"], 2)
            self.assertEqual(summary["errors"], 2)
            self.assertFalse((project_path / "evil.py").exists())
            self.assertFalse((project_path / "workspace" / "unclosed.py").exists())

    def test_overwrite_creates_history_backup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-golden-") as tmpdir:
            project_path = Path(tmpdir)
            target = project_path / "workspace" / "app.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")
            summary = ingest_artifacts("```python file=workspace/app.py\nprint('new')\n```\n", project_path)
            self.assertEqual(summary["updated"], 1)
            backup_path = summary["results"][0]["backup_path"]
            self.assertTrue(backup_path)
            self.assertTrue((project_path / backup_path).exists())


if __name__ == "__main__":
    unittest.main()
