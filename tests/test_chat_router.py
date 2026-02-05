import sys
import unittest
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.router import route_intent
from amon.commands.registry import clear_commands, register_command


class MockLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        _ = messages
        _ = model
        return [self.response]


class ChatRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_commands()
        register_command("projects.delete", {"type": "object", "properties": {"project_id": {"type": "string"}}}, lambda: {})

    def tearDown(self) -> None:
        clear_commands()

    def test_policy_guard_requires_confirm(self) -> None:
        mock_response = (
            '{\"type\":\"command_plan\",\"confidence\":0.9,\"api\":\"projects.delete\",'
            '\"args\":{\"project_id\":\"proj\"},\"requires_confirm\":false}'
        )
        result = route_intent(
            "請刪除專案",
            project_id="proj",
            run_id=None,
            llm_client=MockLLM(mock_response),
        )
        self.assertTrue(result.requires_confirm)

    def test_policy_guard_rejects_unregistered_api(self) -> None:
        mock_response = (
            '{\"type\":\"command_plan\",\"confidence\":0.9,\"api\":\"projects.unknown\",'
            '\"args\":{},\"requires_confirm\":false}'
        )
        result = route_intent(
            "請執行未知指令",
            project_id="proj",
            run_id=None,
            llm_client=MockLLM(mock_response),
        )
        self.assertEqual(result.type, "chat_response")

    def test_malformed_json_falls_back(self) -> None:
        result = route_intent(
            "請問狀態",
            project_id="proj",
            run_id=None,
            llm_client=MockLLM("not-json"),
        )
        self.assertEqual(result.type, "chat_response")


if __name__ == "__main__":
    unittest.main()
