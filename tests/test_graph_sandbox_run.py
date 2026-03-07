from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph3.amon_node_runner import AmonNodeRunner
from amon.taskgraph3.payloads import SandboxRunConfig, TaskSpec
from amon.taskgraph3.runtime import TaskGraph3Runtime
from amon.taskgraph3.schema import GraphDefinition, TaskNode


class _MockHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_MockHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


class GraphSandboxRunTests(unittest.TestCase):
    @patch("amon.sandbox.client.request.urlopen")
    def test_sandbox_run_node_writes_files_records_and_variables(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _MockHTTPResponse(
            {
                "request_id": "req-1",
                "job_id": "job-1",
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 20,
                "stdout": "ok\n",
                "stderr": "",
                "output_files": [
                    {
                        "path": "result.txt",
                        "content_b64": "aGVsbG8=",
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "docs").mkdir(parents=True, exist_ok=True)

            core = SimpleNamespace(
                logger=SimpleNamespace(error=lambda *args, **kwargs: None),
                load_config=lambda project_path: {"sandbox": {"runner": {"base_url": "http://sandbox.local"}}},
            )
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="sandbox1",
                        task_spec=TaskSpec(
                            executor="sandbox_run",
                            sandbox_run=SandboxRunConfig(command="echo hi", shell="bash"),
                        ),
                    )
                ],
                edges=[],
            )
            runtime = TaskGraph3Runtime(project_path=project_path, graph=graph, run_id="run-1")
            runner = AmonNodeRunner(core=core, project_path=project_path, run_id="run-1", variables={})
            result = runtime.run(runner.run_task)

            state_payload = json.loads((result.run_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state_payload["status"], "completed")
            node_output = state_payload["nodes"]["sandbox1"]["output"]
            self.assertEqual(node_output["exit_code"], 0)

            output_file = project_path / "docs" / "artifacts" / "run-1" / "sandbox1" / "result.txt"
            self.assertTrue(output_file.exists())
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")

            result_record = project_path / ".amon" / "runs" / "run-1" / "sandbox" / "sandbox1" / "result.json"
            self.assertTrue(result_record.exists())

            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(item.get("event") == "node_status" and item.get("node_id") == "sandbox1" for item in events))


if __name__ == "__main__":
    unittest.main()
