import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate_stream(self, messages, model=None):
        self.calls.append(messages)
        yield "trace-ok"


class _FakeToolProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []
        self.tools: list[dict[str, object]] = []

    def run_tool_conversation(self, *, messages, model, tools, execute_tool, stream_handler=None, **kwargs):
        self.calls.append(messages)
        self.tools = list(tools)
        for tool in tools:
            function = tool.get("function", {})
            alias = function.get("name")
            execute_tool(alias, {"sample": alias})
        if callable(stream_handler):
            stream_handler("tool-loop-ok")
        return {"text": "tool-loop-ok", "messages": messages, "finish_reason": "stop"}


class LLMRequestLoggingTests(unittest.TestCase):
    def test_run_agent_task_records_llm_request_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("llm-trace")
                project_path = Path(project.path)
                fake_provider = _FakeProvider()

                with patch("amon.core.build_provider", return_value=fake_provider), patch.object(
                    core,
                    "_auto_web_search_context",
                    return_value="",
                ):
                    response = core.run_agent_task(
                        "請整理目前需求",
                        project_path=project_path,
                        run_id="run-ctx-001",
                        node_id="task-clarify",
                        thread_id="thread-001",
                        request_id="req-001",
                    )

                self.assertEqual(response, "trace-ok")
                self.assertEqual(len(fake_provider.calls), 1)

                trace_path = project_path / ".amon" / "runs" / "run-ctx-001" / "llm_requests.jsonl"
                self.assertTrue(trace_path.exists())

                payloads = [
                    json.loads(line)
                    for line in trace_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertEqual(len(payloads), 1)
                payload = payloads[0]
                self.assertEqual(payload["source"], "run_agent_task")
                self.assertEqual(payload["node_id"], "task-clarify")
                self.assertEqual(payload["thread_id"], "thread-001")
                self.assertEqual(payload["request_id"], "req-001")
                self.assertEqual(payload["message_count"], 2)
                self.assertEqual(payload["chat_messages"][0]["role"], "system")
                self.assertEqual(payload["chat_messages"][-1]["content"], "請整理目前需求")
                self.assertEqual(payload["openai_messages"][-1]["role"], "user")
                self.assertEqual(payload["openai_messages"][-1]["content"][0]["type"], "input_text")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_agent_task_uses_structured_tool_calling_for_mcp_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("llm-tool-trace")
                project_path = Path(project.path)
                fake_provider = _FakeToolProvider()
                observed_tokens: list[str] = []
                available_tools = [
                    {
                        "name": "server:echo",
                        "description": "Echo text from MCP",
                        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
                        "source": "mcp",
                    },
                    {
                        "name": "my_cli",
                        "description": "Run CLI helper",
                        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                        "source": "toolforge",
                    },
                ]

                def _fake_call_tool(tool_name, tool_args, **kwargs):
                    return {
                        "is_error": False,
                        "meta": {"status": "ok"},
                        "content_text": json.dumps({"tool": tool_name, "args": tool_args}, ensure_ascii=False),
                    }

                with patch("amon.core.build_provider", return_value=fake_provider), patch.object(
                    core,
                    "_auto_web_search_context",
                    return_value="",
                ), patch.object(
                    core,
                    "describe_available_tools",
                    return_value=available_tools,
                ), patch.object(
                    core,
                    "call_tool_unified",
                    side_effect=_fake_call_tool,
                ) as mock_call_tool:
                    response = core.run_agent_task(
                        "請先呼叫工具再整理",
                        project_path=project_path,
                        allowed_tools=["server:echo", "my_cli"],
                        stream_handler=observed_tokens.append,
                    )

                self.assertEqual(response, "tool-loop-ok")
                self.assertEqual(len(fake_provider.calls), 1)
                self.assertEqual(
                    [call.args[0] for call in mock_call_tool.call_args_list],
                    ["server:echo", "my_cli"],
                )
                self.assertEqual(len(fake_provider.tools), 2)
                for tool in fake_provider.tools:
                    alias = str(tool.get("function", {}).get("name") or "")
                    self.assertTrue(alias)
                    self.assertNotIn(":", alias)
                    self.assertNotIn(".", alias)
                    self.assertLessEqual(len(alias), 64)
                self.assertIn("tool-loop-ok", observed_tokens)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
