from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.models import decode_stream_event
from amon.taskgraph3.amon_node_runner import AmonNodeRunner
from amon.taskgraph3.payloads import AgentTaskConfig, TaskSpec, ToolCallSpec, ToolTaskConfig
from amon.taskgraph3.schema import TaskNode


class _RuntimeCoreStub:
    def __init__(self) -> None:
        self.tool_calls: list[dict[str, object]] = []
        self.agent_calls: list[dict[str, object]] = []

    def run_tool(self, tool_name: str, payload: dict[str, object], **kwargs: object) -> dict[str, object]:
        self.tool_calls.append({"tool_name": tool_name, "payload": payload, **kwargs})
        return {"ok": True, "text": f"{tool_name} done"}

    def run_agent_task(self, prompt: str, **kwargs: object) -> str:
        stream_handler = kwargs.get("stream_handler")
        if callable(stream_handler):
            stream_handler("alpha ")
            stream_handler("beta")
        self.agent_calls.append({"prompt": prompt, **kwargs})
        return "alpha beta"

    def load_config(self, project_path: Path) -> dict[str, object]:
        return {"sandbox": {"runner": {"base_url": "http://sandbox.local"}}}


class DeterministicVsDelegatedIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_runtime_flag = os.environ.get("AMON_VNEXT_RUNTIME")
        os.environ["AMON_VNEXT_RUNTIME"] = "1"

    def tearDown(self) -> None:
        if self._old_runtime_flag is None:
            os.environ.pop("AMON_VNEXT_RUNTIME", None)
            return
        os.environ["AMON_VNEXT_RUNTIME"] = self._old_runtime_flag

    def test_llm_executor_emits_node_chunk_events_and_preserves_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            stream_tokens: list[str] = []
            runner = AmonNodeRunner(
                core=_RuntimeCoreStub(),
                project_path=project_path,
                run_id="run-llm",
                variables={},
                stream_handler=stream_tokens.append,
            )
            node = TaskNode(
                id="llm-1",
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(prompt="請輸出內容"),
                ),
            )

            result = runner.run_task(node, {})

            events = [payload for token in stream_tokens for ok, payload in [decode_stream_event(token)] if ok]
            self.assertEqual([item["event"] for item in events if item.get("event") == "node.chunk"], ["node.chunk", "node.chunk"])
            self.assertEqual(result["raw_output"], "alpha beta")
            self.assertIn("ingest_summary", result)

    def test_deterministic_tool_executes_and_writes_audit_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            stream_tokens: list[str] = []
            core = _RuntimeCoreStub()
            runner = AmonNodeRunner(
                core=core,
                project_path=project_path,
                run_id="run-det",
                variables={},
                stream_handler=stream_tokens.append,
            )
            node = TaskNode(
                id="tool-1",
                metadata={
                    "tool_invocation_mode": "deterministic",
                    "tool_policy": {
                        "id": "policy.fs",
                        "status": "active",
                        "allowed_tools": ["filesystem.write"],
                        "allowed_paths": ["workspace"],
                        "side_effect_ceiling": "workspace_write",
                    },
                },
                task_spec=TaskSpec(
                    executor="tool",
                    tool=ToolTaskConfig(
                        tools=[ToolCallSpec(name="filesystem.write", args={"path": "workspace/out.txt", "content": "hello"})]
                    ),
                ),
            )

            result = runner.run_task(node, {})

            audit_path = project_path / ".amon" / "runs" / "run-det" / "tool_audit.jsonl"
            audit_payload = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            events = [payload for token in stream_tokens for ok, payload in [decode_stream_event(token)] if ok]
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(len(core.tool_calls), 1)
            self.assertEqual(audit_payload[0]["invocation_mode"], "deterministic")
            self.assertEqual(audit_payload[0]["selected_by"], "workflow")
            self.assertEqual(audit_payload[0]["approval_state"], "approved")
            self.assertTrue(any(item.get("event") == "node.tool_requested" for item in events))

    def test_delegated_non_readonly_tool_waits_for_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            stream_tokens: list[str] = []
            core = _RuntimeCoreStub()
            runner = AmonNodeRunner(
                core=core,
                project_path=project_path,
                run_id="run-del",
                variables={},
                stream_handler=stream_tokens.append,
            )
            node = TaskNode(
                id="tool-2",
                metadata={
                    "tool_invocation_mode": "delegated",
                    "tool_policy": {
                        "id": "policy.fs",
                        "status": "active",
                        "allowed_tools": ["filesystem.write"],
                        "allowed_paths": ["workspace"],
                        "delegated_allowed": True,
                        "side_effect_ceiling": "workspace_write",
                    },
                },
                task_spec=TaskSpec(
                    executor="tool",
                    tool=ToolTaskConfig(
                        tools=[ToolCallSpec(name="filesystem.write", args={"path": "workspace/out.txt", "content": "hello"})]
                    ),
                ),
            )

            result = runner.run_task(node, {})

            audit_path = project_path / ".amon" / "runs" / "run-del" / "tool_audit.jsonl"
            audit_payload = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            events = [payload for token in stream_tokens for ok, payload in [decode_stream_event(token)] if ok]
            self.assertEqual(result["status"], "waiting_confirmation")
            self.assertEqual(core.tool_calls, [])
            self.assertEqual(audit_payload[0]["invocation_mode"], "delegated")
            self.assertEqual(audit_payload[0]["approval_state"], "pending")
            self.assertTrue(any(item.get("event") == "node.confirmation_requested" for item in events))


if __name__ == "__main__":
    unittest.main()
