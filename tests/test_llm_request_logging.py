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


if __name__ == "__main__":
    unittest.main()
