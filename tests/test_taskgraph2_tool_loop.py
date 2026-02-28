import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.openai_tool_client import OpenAIToolClient
from amon.taskgraph2.runtime import TaskGraphRuntime
from amon.taskgraph2.schema import TaskGraph, TaskNode, TaskNodeTool
from amon.taskgraph2.tool_loop import ToolLoopRunner
from amon.tooling.policy import ToolPolicy
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolResult, ToolSpec


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class TaskGraph2ToolLoopTests(unittest.TestCase):
    def test_tool_loop_calls_registry_and_returns_final_text(self) -> None:
        first = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "test.echo", "arguments": '{"text":"hi"}'},
                            }
                        ],
                    }
                }
            ]
        }
        second = {"choices": [{"message": {"content": "done"}}]}

        responses = [_FakeHTTPResponse(first), _FakeHTTPResponse(second)]

        registry = ToolRegistry(policy=ToolPolicy(allow=("test.echo",)))
        called: list[dict[str, str]] = []

        def _echo(call):  # noqa: ANN001
            called.append(call.args)
            return ToolResult(content=[{"type": "text", "text": str(call.args.get("text") or "")}])

        registry.register(
            ToolSpec(name="test.echo", description="echo", input_schema={"type": "object"}),
            _echo,
        )

        client = OpenAIToolClient(
            base_url="https://mock.local/v1",
            api_key_env="OPENAI_API_KEY",
            model="gpt-test",
            timeout_s=5,
        )

        with patch("os.getenv", return_value="test-key"), patch(
            "urllib.request.urlopen", side_effect=responses
        ) as mocked_urlopen:
            runner = ToolLoopRunner(client=client)
            final_text, trace = runner.run(
                messages=[{"role": "user", "content": "say hi"}],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "test.echo",
                            "description": "echo",
                            "parameters": {
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"],
                            },
                        },
                    }
                ],
                tool_choice="auto",
                max_turns=3,
                registry=registry,
                run_id="run-1",
                node_id="N1",
                project_id="/tmp/project",
            )

        self.assertEqual(mocked_urlopen.call_count, 2)
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0], {"text": "hi"})
        self.assertEqual(final_text, "done")
        self.assertEqual(trace[0]["tool"], "test.echo")

    def test_runtime_uses_tool_loop_when_enable_tools(self) -> None:
        first = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "test.echo", "arguments": '{"text":"hi"}'},
                            }
                        ],
                    }
                }
            ]
        }
        second = {"choices": [{"message": {"content": "done"}}]}

        responses = [_FakeHTTPResponse(first), _FakeHTTPResponse(second)]
        registry = ToolRegistry(policy=ToolPolicy(allow=("test.echo",)))
        registry.register(
            ToolSpec(name="test.echo", description="echo", input_schema={"type": "object"}),
            lambda call: ToolResult(content=[{"type": "text", "text": str(call.args.get("text") or "")}]),
        )
        client = OpenAIToolClient(
            base_url="https://mock.local/v1",
            api_key_env="OPENAI_API_KEY",
            model="gpt-test",
            timeout_s=5,
        )

        graph = TaskGraph(
            schema_version="2.0",
            objective="tool loop",
            nodes=[
                TaskNode(
                    id="N1",
                    title="tool loop",
                    kind="task",
                    description="run with tools",
                    tools=[
                        TaskNodeTool(
                            name="test.echo",
                            when_to_use="echo",
                            required=False,
                            args_schema_hint={
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                            },
                        )
                    ],
                )
            ],
            edges=[],
        )
        graph.nodes[0].llm.enable_tools = True

        with tempfile.TemporaryDirectory() as tmp:
            with patch("os.getenv", return_value="test-key"), patch("urllib.request.urlopen", side_effect=responses):
                runtime = TaskGraphRuntime(
                    project_path=Path(tmp),
                    graph=graph,
                    registry=registry,
                    openai_tool_client=client,
                    run_id="run_tg2_tool_loop",
                )
                result = runtime.run()

            self.assertEqual(result.state["status"], "completed")
            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            names = [item["event"] for item in events]
            self.assertIn("tool_call_requested", names)
            self.assertIn("tool_call_executed", names)


if __name__ == "__main__":
    unittest.main()
