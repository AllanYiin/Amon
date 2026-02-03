import os
import tempfile
import unittest
import zipfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class ExportEvalTests(unittest.TestCase):
    def test_export_project_creates_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                docs_path = project_path / "docs" / "notes.md"
                docs_path.write_text("測試內容", encoding="utf-8")

                output_path = Path(temp_dir) / "export.zip"
                core.export_project(project.project_id, output_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            with zipfile.ZipFile(output_path, "r") as archive:
                names = set(archive.namelist())
            base_prefix = project.project_id
            self.assertIn(f"{base_prefix}/amon.project.yaml", names)
            self.assertIn(f"{base_prefix}/docs/notes.md", names)
            self.assertIn(f"{base_prefix}/tasks/tasks.json", names)

    def test_eval_basic_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                result = core.run_eval("basic")
            finally:
                os.environ.pop("AMON_HOME", None)

            self.assertEqual(result["suite"], "basic")
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["tasks"])
            self.assertTrue(result["checks"])


if __name__ == "__main__":
    unittest.main()
