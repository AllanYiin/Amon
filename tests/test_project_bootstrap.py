import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.chat.project_bootstrap import resolve_project_id_from_message


class ProjectBootstrapTests(unittest.TestCase):
    def test_resolve_project_id_from_message_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("影片規格")

                matched = resolve_project_id_from_message(core, f"請套用專案 {project.project_id} 然後執行")

                self.assertEqual(matched, project.project_id)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_resolve_project_id_from_message_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Anthropic Skills 規格")

                matched = resolve_project_id_from_message(core, "請延續 anthroPic skills 規格 的任務")

                self.assertEqual(matched, project.project_id)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
