import sys
import unittest
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.router import route_intent
from amon.chat.router_llm import choose_execution_mode_with_llm, should_continue_run_with_llm
from amon.commands.registry import clear_commands, get_command, register_command


class MockLLM:
    def __init__(self, response: str | list[str]) -> None:
        if isinstance(response, list):
            self.responses = list(response)
        else:
            self.responses = [response]
        self.last_messages: list[dict[str, str]] = []

    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        self.last_messages = messages
        _ = model
        if self.responses:
            return [self.responses.pop(0)]
        return ['{"mode":"plan_execute","confidence":0.95,"rationale":["fallback"],"requires_planning":true}']


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

    def test_choose_execution_mode_with_llm_uses_model_decision(self) -> None:
        mock = MockLLM('{"mode":"self_critique","confidence":0.84,"rationale":["正式輸出"],"requires_planning":false}')
        mode = choose_execution_mode_with_llm("我要把模型改裝為擴散語言模型", llm_client=mock)
        self.assertEqual(mode, "self_critique")

    def test_choose_execution_mode_with_llm_keeps_team_when_legal(self) -> None:
        mock = MockLLM('{"mode":"team","confidence":0.92,"rationale":["需要分工"],"requires_planning":true}')
        mode = choose_execution_mode_with_llm("請產出多代理協作架構研究報告", llm_client=mock)
        self.assertEqual(mode, "team")

    def test_choose_execution_mode_single_low_confidence_escalates_to_plan_execute(self) -> None:
        mock = MockLLM('{"mode":"single","confidence":0.4,"rationale":["不確定"],"requires_planning":true}')
        mode = choose_execution_mode_with_llm("請幫我修改多個檔案並執行測試", llm_client=mock)
        self.assertEqual(mode, "plan_execute")

    def test_should_continue_run_with_llm_returns_true_for_semantic_followup(self) -> None:
        mock = MockLLM('{"continue_run":true,"confidence":0.93}')
        should_continue = should_continue_run_with_llm(
            user_message="先做後端",
            last_assistant_text="收到，你想先從哪個部分開始？",
            llm_client=mock,
        )
        self.assertTrue(should_continue)

    def test_should_continue_run_with_llm_returns_false_for_topic_switch(self) -> None:
        mock = MockLLM('{"continue_run":false,"confidence":0.91}')
        should_continue = should_continue_run_with_llm(
            user_message="另外幫我寫旅遊行程",
            last_assistant_text="你要先做前端還是後端？",
            llm_client=mock,
        )
        self.assertFalse(should_continue)

    def test_should_continue_run_with_llm_fallbacks_false_on_invalid_json(self) -> None:
        mock = MockLLM('not-json')
        should_continue = should_continue_run_with_llm(
            user_message="後端",
            last_assistant_text="請提供你要先做哪一塊",
            llm_client=mock,
        )
        self.assertFalse(should_continue)

    def test_choose_execution_mode_with_llm_repairs_invalid_json_once(self) -> None:
        mock = MockLLM([
            "not-json",
            '{"mode":"self_critique","confidence":0.73,"rationale":["需要自我審查"],"requires_planning":false}',
        ])
        mode = choose_execution_mode_with_llm("請幫我潤稿", llm_client=mock)
        self.assertEqual(mode, "self_critique")

    def test_choose_execution_mode_with_llm_fallbacks_to_plan_execute_on_double_failure(self) -> None:
        mock = MockLLM(["not-json", "still-not-json"])
        mode = choose_execution_mode_with_llm("我要把模型改裝為擴散語言模型", llm_client=mock)
        self.assertEqual(mode, "plan_execute")


if __name__ == "__main__":
    unittest.main()
