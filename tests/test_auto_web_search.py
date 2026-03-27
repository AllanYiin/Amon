import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amon.core import AmonCore
from amon.models import decode_stream_event
from amon.tooling.policy import ToolPolicy
from amon.tooling.types import ToolResult


class _FakeRegistry:
    def __init__(self) -> None:
        self.policy = ToolPolicy(allow=("filesystem.read",), ask=(), deny=())
        self.last_call = None
        self.result = ToolResult(content=[{"type": "text", "text": '[{"title":"A","url":"https://example.com"}]'}])

    def call(self, call):
        self.last_call = call
        return self.result


class AutoWebSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.core = AmonCore(data_dir=Path(self.tmpdir.name))

    def test_prompt_requires_web_search_by_keyword(self) -> None:
        self.assertTrue(self.core._prompt_requires_web_search("請搜尋最新 AI 新聞"))
        self.assertFalse(self.core._prompt_requires_web_search("幫我整理目前專案檔案"))

    @patch("amon.tooling.builtin.build_registry")
    def test_auto_web_search_context_includes_payload(self, build_registry_mock) -> None:
        fake_registry = _FakeRegistry()
        build_registry_mock.return_value = fake_registry

        context = self.core._auto_web_search_context(
            "請搜尋 Python 3.13 最新變更",
            project_path=None,
            config={"amon": {"auto_web_search": True}},
        )

        self.assertIn("web.search", fake_registry.last_call.tool)
        self.assertIn("Python 3.13", fake_registry.last_call.args.get("query", ""))
        self.assertIn('"title"', context)
        self.assertNotIn("web.search", fake_registry.policy.ask)

    @patch("amon.tooling.builtin.build_registry")
    def test_auto_web_search_context_emits_args_preview_and_error_detail(self, build_registry_mock) -> None:
        fake_registry = _FakeRegistry()
        fake_registry.result = ToolResult(
            content=[{"type": "text", "text": "缺少 query 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
        build_registry_mock.return_value = fake_registry
        streamed_tokens: list[str] = []

        context = self.core._auto_web_search_context(
            "請搜尋最新 AI 新聞",
            project_path=None,
            config={"amon": {"auto_web_search": True}},
            stream_handler=streamed_tokens.append,
        )

        self.assertEqual(context, "")
        tool_events = []
        for token in streamed_tokens:
            is_event, payload = decode_stream_event(token)
            if is_event and payload.get("event") == "tool_call":
                tool_events.append(payload)
        self.assertEqual(len(tool_events), 2)
        self.assertIn('"query": "請搜尋最新 AI 新聞"', str(tool_events[0].get("args_preview") or ""))
        self.assertEqual(tool_events[1].get("status"), "invalid_args")
        self.assertEqual(tool_events[1].get("error_detail"), "缺少 query 參數。")


if __name__ == "__main__":
    unittest.main()
