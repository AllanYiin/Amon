import sys
import unittest
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.router import route_intent
from amon.commands.registry import clear_commands, get_command, register_command


class MockLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_messages: list[dict[str, str]] = []

    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        self.last_messages = messages
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

    def test_route_intent_includes_conversation_history_in_context(self) -> None:
        mock = MockLLM('{"type":"chat_response","confidence":0.9}')
        route_intent(
            "延續上一題",
            project_id="proj",
            llm_client=mock,
            context={"conversation_history": [{"role": "user", "content": "前一題內容"}]},
        )
        self.assertEqual(len(mock.last_messages), 2)
        self.assertIn("conversation_history", mock.last_messages[1]["content"])

    def test_route_intent_initializes_default_commands(self) -> None:
        clear_commands()
        self.assertIsNone(get_command("projects.list"))

        route_intent(
            "請列出專案",
            project_id="proj",
            llm_client=MockLLM('{"type":"chat_response","confidence":0.9}'),
        )

        self.assertIsNotNone(get_command("projects.list"))


if __name__ == "__main__":
    unittest.main()
