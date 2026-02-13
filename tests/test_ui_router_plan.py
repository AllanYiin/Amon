import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.router_types import RouterResult
from amon.core import ProjectRecord
from amon.ui_server import _is_duplicate_project_create, _resolve_command_plan_from_router


class UIRouterPlanTests(unittest.TestCase):
    def _make_project(self) -> ProjectRecord:
        return ProjectRecord(
            project_id="demo-proj",
            name="Demo 專案",
            path="/tmp/demo",
            created_at="2026-01-01T00:00:00+08:00",
            updated_at="2026-01-01T00:00:00+08:00",
            status="active",
        )

    def test_prefers_router_api_and_args(self) -> None:
        result = RouterResult(
            type="command_plan",
            confidence=0.9,
            api="projects.delete",
            args={"project_id": "proj-123"},
        )

        command_name, args = _resolve_command_plan_from_router("列出專案", result)

        self.assertEqual(command_name, "projects.delete")
        self.assertEqual(args, {"project_id": "proj-123"})

    def test_falls_back_to_parser_when_api_missing(self) -> None:
        result = RouterResult(type="command_plan", confidence=0.9, api=None, args={})

        command_name, args = _resolve_command_plan_from_router("列出專案", result)

        self.assertEqual(command_name, "projects.list")
        self.assertEqual(args, {})

    def test_detect_duplicate_project_create_by_name(self) -> None:
        active_project = self._make_project()

        duplicated = _is_duplicate_project_create(
            active_project=active_project,
            command_name="projects.create",
            args={"name": " Demo 專案 "},
        )

        self.assertTrue(duplicated)

    def test_detect_duplicate_project_create_by_project_id(self) -> None:
        active_project = self._make_project()

        duplicated = _is_duplicate_project_create(
            active_project=active_project,
            command_name="projects.create",
            args={"name": "demo-proj"},
        )

        self.assertTrue(duplicated)

    def test_non_duplicate_project_create(self) -> None:
        active_project = self._make_project()

        duplicated = _is_duplicate_project_create(
            active_project=active_project,
            command_name="projects.create",
            args={"name": "另一個專案"},
        )

        self.assertFalse(duplicated)


if __name__ == "__main__":
    unittest.main()
