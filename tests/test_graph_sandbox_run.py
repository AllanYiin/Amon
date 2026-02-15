import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.graph_runtime import GraphRuntime


class GraphSandboxRunTests(unittest.TestCase):
    def test_sandbox_run_node_writes_state_and_artifact_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "docs").mkdir(parents=True, exist_ok=True)

            graph_payload = {
                "nodes": [
                    {
                        "id": "sandbox1",
                        "type": "sandbox_run",
                        "language": "python",
                        "code": "print('ok')",
                    }
                ],
                "edges": [],
            }
            graph_path = project_path / "graph.json"
            graph_path.write_text(json.dumps(graph_payload, ensure_ascii=False), encoding="utf-8")

            core = SimpleNamespace(
                logger=SimpleNamespace(error=lambda *args, **kwargs: None),
                load_config=lambda project_path: {},
            )

            fake_service_result = {
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 123,
                "stdout": "ok\n",
                "stderr": "",
                "manifest_path": str(project_path / "docs" / "artifacts" / "run-1" / "sandbox1" / "manifest.json"),
                "written_files": [
                    str(project_path / "docs" / "artifacts" / "run-1" / "sandbox1" / "result.txt")
                ],
                "outputs": [{"path": "docs/artifacts/run-1/sandbox1/result.txt", "size": 3, "sha256": "abc"}],
            }

            with patch("amon.graph_runtime.run_sandbox_step", return_value=fake_service_result) as run_step_mock:
                runtime = GraphRuntime(
                    core=core,
                    project_path=project_path,
                    graph_path=graph_path,
                    run_id="run-1",
                )
                result = runtime.run()

            run_step_mock.assert_called_once()
            kwargs = run_step_mock.call_args.kwargs
            self.assertEqual(kwargs["run_id"], "run-1")
            self.assertEqual(kwargs["step_id"], "sandbox1")
            self.assertEqual(kwargs["output_prefix"], "docs/artifacts/run-1/sandbox1/")

            state_payload = json.loads((result.run_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state_payload["status"], "completed")
            node_output = state_payload["nodes"]["sandbox1"]["output"]
            self.assertEqual(node_output["exit_code"], 0)
            self.assertFalse(node_output["timed_out"])
            self.assertEqual(node_output["duration_ms"], 123)
            self.assertEqual(node_output["stdout"], "ok\n")
            self.assertEqual(node_output["stderr"], "")
            self.assertEqual(
                node_output["artifacts"]["manifest_path"],
                "docs/artifacts/run-1/sandbox1/manifest.json",
            )

            events = [
                json.loads(line)
                for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            artifact_events = [item for item in events if item.get("event") == "artifact_written"]
            self.assertEqual(len(artifact_events), 1)
            self.assertEqual(artifact_events[0]["node_id"], "sandbox1")
            self.assertEqual(
                artifact_events[0]["artifact_path"],
                "docs/artifacts/run-1/sandbox1/result.txt",
            )

            node_complete_events = [item for item in events if item.get("event") == "node_complete"]
            self.assertEqual(len(node_complete_events), 1)
            self.assertEqual(
                node_complete_events[0]["artifact_path"],
                "docs/artifacts/run-1/sandbox1/manifest.json",
            )


if __name__ == "__main__":
    unittest.main()
