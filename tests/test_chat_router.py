import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.router import route_intent


class ChatRouterTests(unittest.TestCase):
    def test_route_command_slash(self) -> None:
        result = route_intent("/projects list", project_id="proj", run_id=None)
        self.assertEqual(result.type, "command_plan")

    def test_route_command_keywords(self) -> None:
        result = route_intent("請幫我列出專案", project_id="proj", run_id=None)
        self.assertEqual(result.type, "command_plan")

    def test_route_graph_patch_keywords(self) -> None:
        result = route_intent("把這次任務存成範本", project_id="proj", run_id=None)
        self.assertEqual(result.type, "graph_patch_plan")

    def test_route_run_context_update(self) -> None:
        result = route_intent("請改成使用繁中", project_id="proj", run_id="run-123")
        self.assertEqual(result.type, "run_context_update")

    def test_route_chat_response_default(self) -> None:
        result = route_intent("請問目前狀態如何", project_id="proj", run_id=None)
        self.assertEqual(result.type, "chat_response")


if __name__ == "__main__":
    unittest.main()
