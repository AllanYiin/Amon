import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.execution_mode import decide_execution_mode


class _MockLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def generate_stream(self, messages, model=None):  # noqa: ANN001
        _ = (messages, model)
        if self._responses:
            return [self._responses.pop(0)]
        return ['{"mode":"plan_execute","confidence":0.9,"rationale":["fallback"],"requires_planning":true}']


class ExecutionModeTests(unittest.TestCase):
    def test_invalid_json_then_repair_success(self) -> None:
        llm = _MockLLM([
            "not-json",
            '{"mode":"self_critique","confidence":0.83,"rationale":["需審稿"],"requires_planning":false}',
        ])
        with patch("amon.chat.execution_mode.emit_event"):
            mode = decide_execution_mode("請協助潤稿", llm_client=llm)
        self.assertEqual(mode, "self_critique")

    def test_invalid_json_then_repair_fail_fallback_plan_execute(self) -> None:
        llm = _MockLLM(["not-json", "still-not-json"])
        with patch("amon.chat.execution_mode.emit_event"):
            mode = decide_execution_mode("請幫我修改專案", llm_client=llm)
        self.assertEqual(mode, "plan_execute")

    def test_single_low_confidence_or_requires_planning_escalates(self) -> None:
        llm = _MockLLM([
            '{"mode":"single","confidence":0.4,"rationale":["不確定"],"requires_planning":true}',
        ])
        with patch("amon.chat.execution_mode.emit_event"):
            mode = decide_execution_mode("任務", llm_client=llm)
        self.assertEqual(mode, "plan_execute")

    def test_valid_team_preserved(self) -> None:
        llm = _MockLLM([
            '{"mode":"team","confidence":0.91,"rationale":["跨域分工"],"requires_planning":true}',
        ])
        with patch("amon.chat.execution_mode.emit_event"):
            mode = decide_execution_mode("任務", llm_client=llm)
        self.assertEqual(mode, "team")


if __name__ == "__main__":
    unittest.main()
