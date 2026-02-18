import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
