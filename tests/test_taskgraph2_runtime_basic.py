import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.runtime import TaskGraphRuntime
from amon.taskgraph2.schema import TaskEdge, TaskGraph, TaskNode, TaskNodeTool
from amon.tooling.policy import ToolPolicy
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolResult, ToolSpec


class FakeLLMClient:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls: list[list[dict[str, str]]] = []

    def generate_stream(self, messages: list[dict[str, str]], model=None):  # noqa: ANN001
        self.calls.append(messages)
        output = self._outputs.pop(0)
        for token in output.split(" "):
            if token:
                yield token + " "


class TaskGraph2RuntimeBasicTests(unittest.TestCase):
    def test_runtime_executes_dag_and_writes_state_events_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            graph = TaskGraph(
                schema_version="2.0",
                objective="兩步驟串接",
                session_defaults={"topic": "TaskGraph2"},
                nodes=[
                    TaskNode(
                        id="N1",
                        title="起草",
                        kind="task",
                        description="請寫摘要",
                        reads=["topic"],
                        writes={"draft": "text"},
                    ),
                    TaskNode(
                        id="N2",
                        title="整合",
                        kind="synthesis",
                        description="請整合為最終內容",
                        reads=["draft"],
                        writes={"final": "md"},
                    ),
                ],
                edges=[TaskEdge(from_node="N1", to_node="N2")],
            )
            fake_llm = FakeLLMClient(["第一步輸出", "第二步輸出"])

            runtime = TaskGraphRuntime(project_path=project_path, graph=graph, llm_client=fake_llm, run_id="run_tg2_basic")
            result = runtime.run()

            run_dir = project_path / ".amon" / "runs" / "run_tg2_basic"
            self.assertEqual(result.run_dir, run_dir)

            state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["nodes"]["N1"]["status"], "completed")
            self.assertEqual(state["nodes"]["N2"]["status"], "completed")
            self.assertIn("draft", state["session"])
            self.assertIn("final", state["session"])

            events = [
                json.loads(line)
                for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            event_names = [item["event"] for item in events]
            self.assertEqual(
                event_names,
                ["run_start", "node_start", "node_complete", "node_start", "node_complete", "run_complete"],
            )

            node1_output = project_path / "docs" / "steps" / "N1.md"
            node2_output = project_path / "docs" / "steps" / "N2.md"
            self.assertTrue(node1_output.exists())
            self.assertTrue(node2_output.exists())
            self.assertEqual(node1_output.read_text(encoding="utf-8"), "第一步輸出 ")
            self.assertEqual(node2_output.read_text(encoding="utf-8"), "第二步輸出 ")

            self.assertEqual(len(fake_llm.calls), 2)
            self.assertIn("[session:topic]", fake_llm.calls[0][-1]["content"])
            self.assertIn("[session:draft]", fake_llm.calls[1][-1]["content"])

    def test_runtime_executes_allowed_tool_and_stores_session_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            registry = ToolRegistry(policy=ToolPolicy(allow=("test.echo",), deny=("test.blocked",)))
            registry.register(
                ToolSpec(name="test.echo", description="echo", input_schema={"type": "object"}),
                lambda call: ToolResult(content=[{"type": "text", "text": str(call.args.get("text") or "")}]),
            )
            graph = TaskGraph(
                schema_version="2.0",
                objective="工具步驟",
                session_defaults={},
                nodes=[
                    TaskNode(
                        id="T1",
                        title="工具節點",
                        kind="tooling",
                        description="呼叫工具",
                        writes={"echo": "text"},
                        steps=[
                            {"type": "tool", "tool_name": "test.echo", "args": {"text": "hello"}, "store_as": "echo"}
                        ],
                    )
                ],
                edges=[],
            )

            runtime = TaskGraphRuntime(project_path=project_path, graph=graph, registry=registry, run_id="run_tg2_tool_ok")
            result = runtime.run()

            self.assertEqual(result.state["status"], "completed")
            self.assertEqual(result.state["session"]["echo"], "hello")

            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertIn("tool_request", [item["event"] for item in events])
            tool_result = [item for item in events if item["event"] == "tool_result"][0]
            self.assertEqual(tool_result["meta"]["status"], "ok")
            self.assertFalse(tool_result["meta"]["is_error"])

    def test_runtime_marks_node_failed_when_tool_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            registry = ToolRegistry(policy=ToolPolicy(allow=("test.echo",), deny=("test.blocked",)))
            registry.register(
                ToolSpec(name="test.blocked", description="blocked", input_schema={"type": "object"}),
                lambda call: ToolResult(content=[{"type": "text", "text": "should not run"}]),
            )
            graph = TaskGraph(
                schema_version="2.0",
                objective="工具拒絕",
                session_defaults={},
                nodes=[
                    TaskNode(
                        id="T2",
                        title="被拒絕",
                        kind="tooling",
                        description="呼叫被拒絕工具",
                        tools=[TaskNodeTool(name="test.blocked", args_schema_hint={"text": "x"})],
                        writes={"echo": "text"},
                    )
                ],
                edges=[],
            )

            runtime = TaskGraphRuntime(project_path=project_path, graph=graph, registry=registry, run_id="run_tg2_tool_denied")
            result = runtime.run()

            self.assertEqual(result.state["status"], "failed")
            self.assertEqual(result.state["nodes"]["T2"]["status"], "failed")
            self.assertIn("tool step failed", str(result.state["nodes"]["T2"]["error"]))

            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            tool_result = [item for item in events if item["event"] == "tool_result"][0]
            self.assertEqual(tool_result["meta"]["status"], "denied")
            self.assertTrue(tool_result["meta"]["is_error"])


if __name__ == "__main__":
    unittest.main()
