import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.node_executor import NodeExecutor
from amon.taskgraph2.runtime import TaskGraphRuntime
from amon.taskgraph2.schema import TaskGraph, TaskNode, TaskNodeOutput, TaskNodeRetry


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


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


class TaskGraph2RetryValidationTests(unittest.TestCase):
    def test_node_executor_retry_injects_repair_error_and_backoff(self) -> None:
        clock = FakeClock()
        executor = NodeExecutor(sleep_func=clock.sleep, monotonic_func=clock.monotonic, min_call_interval_s=0.0)
        node = TaskNode(
            id="R1",
            title="retry",
            kind="task",
            description="d",
            output=TaskNodeOutput(type="json", schema={"required_keys": {"ok": "boolean"}}),
            retry=TaskNodeRetry(max_attempts=2, backoff_s=0.5),
        )
        captured_messages: list[list[dict[str, str]]] = []
        events: list[dict[str, object]] = []

        responses = iter(["{\"ok\": \"bad\"}", '{"ok": true}'])

        def invoke(messages: list[dict[str, str]]) -> str:
            captured_messages.append(messages)
            return next(responses)

        result = executor.execute_llm_node(
            node=node,
            base_messages=[{"role": "user", "content": "請輸出 json"}],
            invoke_llm=invoke,
            append_event=events.append,
        )

        self.assertEqual(result.extracted_output, {"ok": True})
        self.assertEqual(clock.sleeps, [0.5])
        retry_event = [item for item in events if item["event"] == "node_retry"][0]
        self.assertEqual(retry_event["attempt"], 1)
        self.assertIn("expected boolean", str(retry_event["repair_error"]))
        self.assertIn("[repair_error]", captured_messages[1][-1]["content"])

    def test_node_executor_rate_limit_waits_between_calls(self) -> None:
        clock = FakeClock()
        executor = NodeExecutor(sleep_func=clock.sleep, monotonic_func=clock.monotonic, min_call_interval_s=0.2)
        node = TaskNode(id="R2", title="rate", kind="task", description="d", output=TaskNodeOutput(type="text"))
        events: list[dict[str, object]] = []

        executor.execute_llm_node(
            node=node,
            base_messages=[{"role": "user", "content": "x"}],
            invoke_llm=lambda _messages: "ok",
            append_event=events.append,
        )
        executor.execute_llm_node(
            node=node,
            base_messages=[{"role": "user", "content": "x"}],
            invoke_llm=lambda _messages: "ok",
            append_event=events.append,
        )

        self.assertEqual(clock.sleeps, [0.2])

    def test_runtime_emits_retry_and_numeric_warning_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            graph = TaskGraph(
                schema_version="2.0",
                objective="retry+warning",
                nodes=[
                    TaskNode(
                        id="N1",
                        title="json",
                        kind="task",
                        description="輸出 json",
                        writes={"result": "json"},
                        output=TaskNodeOutput(type="json", schema={"required_keys": {"ok": "boolean"}}),
                        retry=TaskNodeRetry(max_attempts=2, backoff_s=0.1),
                    )
                ],
                edges=[],
            )
            fake_llm = FakeLLMClient(['{"ok":"no"}', '{"ok": true, "huge": 1e20}'])
            runtime = TaskGraphRuntime(project_path=project_path, graph=graph, llm_client=fake_llm, run_id="run_tg2_retry")
            result = runtime.run()

            self.assertEqual(result.state["status"], "completed")
            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertIn("node_retry", [item["event"] for item in events])
            self.assertIn("numeric_anomaly_warning", [item["event"] for item in events])


if __name__ == "__main__":
    unittest.main()
