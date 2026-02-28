import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.node_executor import NodeExecutor, ValidationError, validate_output
from amon.taskgraph2.schema import TaskNodeOutput, TaskNodeRetry

import tempfile

from amon.taskgraph2.runtime import TaskGraphRuntime
from amon.taskgraph2.schema import TaskGraph, TaskNode


class _FakeLLMClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)

    def generate_stream(self, messages, model=None):  # noqa: ANN001
        output = self.outputs.pop(0)
        for token in output.split(" "):
            if token:
                yield token + " "


class TaskGraph2RetryAndValidationTests(unittest.TestCase):
    def test_validate_output_checks_required_keys_and_types(self) -> None:
        spec = TaskNodeOutput(
            type="json",
            schema={"required_keys": ["name", "score"], "types": {"name": "string", "score": "number"}},
        )
        validate_output({"name": "amon", "score": 0.9}, spec)
        with self.assertRaises(ValidationError):
            validate_output({"name": "amon"}, spec)
        with self.assertRaises(ValidationError):
            validate_output({"name": "amon", "score": "oops"}, spec)

    def test_node_executor_retry_with_repair_error_and_backoff(self) -> None:
        sleep_calls: list[float] = []
        calls: list[list[dict[str, str]]] = []
        outputs = iter(["not-json", '{"name":"ok"}'])

        executor = NodeExecutor(sleep_func=lambda s: sleep_calls.append(s), min_call_interval_s=0)

        def generate(messages):
            calls.append(messages)
            return next(outputs)

        retries: list[tuple[int, str]] = []
        raw, extracted = executor.run_llm_with_retry(
            generate_text=generate,
            base_messages=[{"role": "user", "content": "請回 JSON"}],
            output_spec=TaskNodeOutput(type="json", schema={"required_keys": ["name"]}),
            retry_spec=TaskNodeRetry(max_attempts=2, backoff_s=0.25),
            on_retry=lambda attempt, error: retries.append((attempt, error)),
        )

        self.assertEqual(json.loads(raw), {"name": "ok"})
        self.assertEqual(extracted, {"name": "ok"})
        self.assertEqual(retries[0][0], 1)
        self.assertEqual(sleep_calls, [0.25])
        self.assertEqual(len(calls), 2)
        self.assertIn("[repair_error]", calls[1][-1]["content"])

    def test_node_executor_emits_numeric_anomaly_warning(self) -> None:
        warnings: list[dict[str, str]] = []
        executor = NodeExecutor()

        executor.run_llm_with_retry(
            generate_text=lambda _: '{"x": 1e309, "y": [1, 2, 1e20]}',
            base_messages=[{"role": "user", "content": "json"}],
            output_spec=TaskNodeOutput(type="json"),
            retry_spec=TaskNodeRetry(max_attempts=1),
            on_warning=lambda payload: warnings.append(payload),
        )

        self.assertTrue(any(item.get("path") == "$.x" for item in warnings))
        self.assertTrue(any(item.get("path") == "$.y[2]" for item in warnings))


    def test_runtime_records_node_retry_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            graph = TaskGraph(
                schema_version="2.0",
                objective="retry",
                nodes=[
                    TaskNode(
                        id="N1",
                        title="json",
                        kind="task",
                        description="return json",
                        writes={"result": "json"},
                        output=TaskNodeOutput(type="json", schema={"required_keys": ["ok"]}),
                        retry=TaskNodeRetry(max_attempts=2, backoff_s=0.01),
                    )
                ],
                edges=[],
            )
            fake = _FakeLLMClient(["oops", '{"ok": true}'])
            runtime = TaskGraphRuntime(project_path=Path(tmp), graph=graph, llm_client=fake, run_id="retry_case")
            result = runtime.run()
            self.assertEqual(result.state["status"], "completed")

            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertIn("node_retry", [item["event"] for item in events])


if __name__ == "__main__":
    unittest.main()
