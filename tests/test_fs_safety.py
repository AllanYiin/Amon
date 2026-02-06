import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.fs.safety import validate_project_id


class FsSafetyTests(unittest.TestCase):
    def test_delete_restore_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                record = core.create_project("demo")
                file_path = Path(record.path) / "workspace" / "note.txt"
                file_path.write_text("hello", encoding="utf-8")
                with patch("amon.core.require_confirm", return_value=True):
                    trash_id = core.fs_delete(file_path)
                self.assertIsNotNone(trash_id)
                self.assertFalse(file_path.exists())
                restored_path = core.fs_restore(trash_id or "")
                self.assertTrue(restored_path.exists())
                self.assertEqual(restored_path.read_text(encoding="utf-8"), "hello")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_delete_not_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                record = core.create_project("demo")
                file_path = Path(record.path) / "workspace" / "note.txt"
                file_path.write_text("hello", encoding="utf-8")
                with patch("amon.core.require_confirm", return_value=False):
                    trash_id = core.fs_delete(file_path)
                self.assertIsNone(trash_id)
                self.assertTrue(file_path.exists())
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_path_not_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                outside_path = Path(temp_dir) / "outside.txt"
                outside_path.write_text("nope", encoding="utf-8")
                with patch("amon.core.require_confirm", return_value=True):
                    with self.assertRaises(ValueError):
                        core.fs_delete(outside_path)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_project_id_allows_unicode_and_rejects_traversal(self) -> None:
        validate_project_id("排程專案-9150a8")
        with self.assertRaises(ValueError):
            validate_project_id("../escape")


if __name__ == "__main__":
    unittest.main()
