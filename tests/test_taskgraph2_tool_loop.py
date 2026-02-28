import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.openai_tool_client import OpenAIToolClient
from amon.taskgraph2.runtime import TaskGraphRuntime
from amon.taskgraph2.schema import TaskGraph, TaskNode, TaskNodeLLM, TaskNodeTool
from amon.taskgraph2.tool_loop import ToolLoopRunner
from amon.tooling.policy import ToolPolicy
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolResult, ToolSpec


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return None


class TaskGraph2ToolLoopTests(unittest.TestCase):
    def test_openai_tool_loop_executes_tool_and_returns_final_content(self) -> None:
        responses = [
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "test.echo",
                                        "arguments": '{"text":"hi"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {"choices": [{"message": {"content": "done"}}]},
        ]

        opened_requests = []

        def _fake_urlopen(req, timeout=0):  # noqa: ANN001
            opened_requests.append((req, timeout))
            return _FakeHTTPResponse(responses.pop(0))

        registry = ToolRegistry(policy=ToolPolicy(allow=("test.echo",)))
        calls: list[dict] = []

        def _handler(call):  # noqa: ANN001
            calls.append(dict(call.args))
            return ToolResult(content=[{"type": "text", "text": str(call.args.get("text") or "")}])

        registry.register(
            ToolSpec(name="test.echo", description="echo", input_schema={"type": "object"}),
            _handler,
        )

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            client = OpenAIToolClient(base_url="http://mocked.local/v1", api_key="test-key")
            runner = ToolLoopRunner(client=client, model="gpt-4o-mini")
            result = runner.run(
                messages=[{"role": "user", "content": "say hi"}],
                tools=[TaskNodeTool(name="test.echo", when_to_use="echo text", args_schema_hint={"type": "object"})],
                tool_choice="auto",
                max_turns=3,
                registry=registry,
                run_id="run_1",
                node_id="node_1",
            )

        self.assertEqual(len(opened_requests), 2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], {"text": "hi"})
        self.assertEqual(result.final_text, "done")

    def test_runtime_uses_tool_loop_when_enable_tools(self) -> None:
        responses = [
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_2",
                                    "type": "function",
                                    "function": {
                                        "name": "test.echo",
                                        "arguments": '{"text":"hi"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {"choices": [{"message": {"content": "done"}}]},
        ]

        def _fake_urlopen(req, timeout=0):  # noqa: ANN001
            return _FakeHTTPResponse(responses.pop(0))

        registry = ToolRegistry(policy=ToolPolicy(allow=("test.echo",)))
        registry.register(
            ToolSpec(name="test.echo", description="echo", input_schema={"type": "object"}),
            lambda call: ToolResult(content=[{"type": "text", "text": str(call.args.get("text") or "")}]),
        )

        graph = TaskGraph(
            schema_version="2.0",
            objective="tool loop",
            session_defaults={},
            nodes=[
                TaskNode(
                    id="N1",
                    title="Tool Loop",
                    kind="task",
                    description="請使用工具",
                    llm=TaskNodeLLM(model="gpt-4o-mini", enable_tools=True),
                    tools=[TaskNodeTool(name="test.echo", when_to_use="echo", args_schema_hint={"type": "object"})],
                )
            ],
            edges=[],
        )

        with tempfile.TemporaryDirectory() as tmp, patch("urllib.request.urlopen", side_effect=_fake_urlopen), patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "http://mocked.local/v1", "OPENAI_API_KEY": "test-key"},
            clear=False,
        ):
            runtime = TaskGraphRuntime(project_path=Path(tmp), graph=graph, registry=registry, run_id="run_tool_loop")
            result = runtime.run()

            self.assertEqual(result.state["status"], "completed")
            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            event_names = [item["event"] for item in events]
            self.assertIn("tool_call_requested", event_names)
            self.assertIn("tool_call_executed", event_names)


if __name__ == "__main__":
    unittest.main()
