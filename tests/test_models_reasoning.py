import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.models import OpenAICompatibleProvider, OpenAIProviderConfig, decode_reasoning_chunk, encode_reasoning_chunk


class ModelsReasoningTests(unittest.TestCase):
    def test_encode_decode_reasoning_chunk_roundtrip(self) -> None:
        payload = "先拆解需求，再評估風險"
        token = encode_reasoning_chunk(payload)
        is_reasoning, text = decode_reasoning_chunk(token)
        self.assertTrue(is_reasoning)
        self.assertEqual(text, payload)

    def test_provider_emits_reasoning_chunk_from_delta(self) -> None:
        cfg = OpenAIProviderConfig(
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-5.2",
            timeout_s=5,
        )
        provider = OpenAICompatibleProvider(cfg)

        stream_lines = [
            f"data: {json.dumps({'choices': [{'delta': {'reasoning_content': '先定義問題'}}]})}\n".encode("utf-8"),
            f"data: {json.dumps({'choices': [{'delta': {'content': '最終答案'}}]})}\n".encode("utf-8"),
            b"data: [DONE]\n",
        ]

        class FakeResponse:
            def __iter__(self):
                return iter(stream_lines)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("os.getenv", return_value="test-key"), patch("urllib.request.urlopen", return_value=FakeResponse()):
            chunks = list(provider.generate_stream([{"role": "user", "content": "hi"}], model="gpt-5.2"))

        self.assertEqual(len(chunks), 2)
        is_reasoning, reasoning_text = decode_reasoning_chunk(chunks[0])
        self.assertTrue(is_reasoning)
        self.assertEqual(reasoning_text, "先定義問題")
        self.assertEqual(chunks[1], "最終答案")

    def test_run_tool_conversation_rejects_empty_tool_arguments_before_execute(self) -> None:
        cfg = OpenAIProviderConfig(
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-5.2",
            timeout_s=5,
        )

        class FakeToolConversationProvider(OpenAICompatibleProvider):
            def __init__(self, config: OpenAIProviderConfig, rounds: list[list[dict[str, object]]]) -> None:
                super().__init__(config)
                self._rounds = rounds
                self.payloads: list[dict[str, object]] = []

            def _iter_streaming_chunks(self, payload: dict[str, object]):
                self.payloads.append(payload)
                round_index = len(self.payloads) - 1
                yield from self._rounds[round_index]

        provider = FakeToolConversationProvider(
            cfg,
            rounds=[
                [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {"name": "web.search"},
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                ],
                [
                    {"choices": [{"delta": {"content": "done"}}]},
                    {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                ],
            ],
        )
        execute_tool = Mock(return_value={"content_text": "should not run"})

        result = provider.run_tool_conversation(
            messages=[{"role": "user", "content": "請查詢"}],
            model="gpt-5.2",
            tools=[{"type": "function", "function": {"name": "web.search"}}],
            execute_tool=execute_tool,
        )

        execute_tool.assert_not_called()
        self.assertEqual(result["text"], "done")
        self.assertTrue(
            any(
                message.get("role") == "tool"
                and "工具呼叫缺少 arguments JSON。" in str(message.get("content") or "")
                for message in result["messages"]
                if isinstance(message, dict)
            )
        )


if __name__ == "__main__":
    unittest.main()
