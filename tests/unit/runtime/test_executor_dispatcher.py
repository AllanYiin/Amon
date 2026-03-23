import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.runtime_vnext import ExecutorDispatcher, RuntimeExecutionContext
from amon.taskgraph3.payloads import AgentTaskConfig, TaskSpec
from amon.taskgraph3.schema import TaskNode


class ExecutorDispatcherTests(unittest.TestCase):
    def test_metadata_executor_type_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = ExecutorDispatcher(project_path=Path(tmp))
            dispatcher._tool = SimpleNamespace(execute=lambda node, context, runtime_context: {"kind": "tool"})
            node = TaskNode(
                id="n1",
                metadata={"executor_type": "tool"},
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(prompt="noop"),
                ),
            )
            runtime_context = RuntimeExecutionContext(
                core=SimpleNamespace(),
                project_path=Path(tmp),
                run_id="run-1",
                variables={},
            )

            result = dispatcher.dispatch(node, {}, runtime_context)

            self.assertEqual(result["kind"], "tool")

    def test_human_gate_dispatch_creates_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events: list[dict[str, object]] = []
            dispatcher = ExecutorDispatcher(project_path=Path(tmp))
            node = TaskNode(
                id="gate-1",
                metadata={"executor_type": "human_gate"},
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(prompt="noop"),
                ),
            )
            runtime_context = RuntimeExecutionContext(
                core=SimpleNamespace(),
                project_path=Path(tmp),
                run_id="run-1",
                variables={},
                event_sink=events.append,
            )

            result = dispatcher.dispatch(node, {}, runtime_context)

            self.assertEqual(result["status"], "waiting_confirmation")
            self.assertTrue((Path(tmp) / ".amon" / "runs" / "run-1" / "confirmations").exists())
            self.assertEqual(events[0]["event"], "node.confirmation_requested")

    def test_unsupported_executor_type_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = ExecutorDispatcher(project_path=Path(tmp))
            node = TaskNode(
                id="n1",
                metadata={"executor_type": "unknown"},
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(prompt="noop"),
                ),
            )
            runtime_context = RuntimeExecutionContext(
                core=SimpleNamespace(),
                project_path=Path(tmp),
                run_id="run-1",
                variables={},
            )

            with self.assertRaisesRegex(ValueError, "AMON_RUNTIME_001"):
                dispatcher.dispatch(node, {}, runtime_context)


if __name__ == "__main__":
    unittest.main()
