import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.session_store import create_chat_session
from amon.commands.executor import CommandPlan, execute
from amon.core import AmonCore


class CommandExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["AMON_HOME"] = self.temp_dir.name
        self.core = AmonCore()
        self.core.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        os.environ.pop("AMON_HOME", None)

    def test_projects_list_returns_result(self) -> None:
        record = self.core.create_project("測試專案")
        chat_id = create_chat_session(record.project_id)
        plan = CommandPlan(
            name="projects.list",
            args={},
            project_id=record.project_id,
            chat_id=chat_id,
        )

        result = execute(plan, confirmed=True)

        self.assertEqual(result["status"], "ok")
        self.assertIn("projects", result["result"])
        self.assertGreaterEqual(len(result["result"]["projects"]), 1)

    def test_projects_delete_requires_confirm(self) -> None:
        record = self.core.create_project("待刪除專案")
        chat_id = create_chat_session(record.project_id)
        plan = CommandPlan(
            name="projects.delete",
            args={"project_id": record.project_id},
            project_id=record.project_id,
            chat_id=chat_id,
        )

        result = execute(plan, confirmed=False)

        self.assertEqual(result["status"], "confirm_required")
        refreshed = self.core.get_project(record.project_id)
        self.assertEqual(refreshed.status, "active")


if __name__ == "__main__":
    unittest.main()
