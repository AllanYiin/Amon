import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.router_types import RouterResult
from amon.ui_server import _resolve_command_plan_from_router


class UIRouterPlanTests(unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()
