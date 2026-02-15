import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.sandbox.records import ensure_run_step_dirs, truncate_text  # noqa: E402
from amon.sandbox.service import run_sandbox_step  # noqa: E402


class _MockHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_MockHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


class SandboxServiceTests(unittest.TestCase):
    @patch("amon.sandbox.client.request.urlopen")
    def test_run_sandbox_step_writes_records_and_artifacts(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _MockHTTPResponse(
            {
                "request_id": "req-1",
                "job_id": "job-1",
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 42,
                "stdout": "ok",
                "stderr": "",
                "output_files": [
                    {
                        "path": "hello.txt",
                        "content_b64": "aGVsbG8=",
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "docs").mkdir(parents=True, exist_ok=True)
            (project / ".amon" / "runs").mkdir(parents=True, exist_ok=True)
            (project / "docs" / "input.txt").write_text("abc", encoding="utf-8")

            config = {
                "sandbox": {
                    "runner": {
                        "base_url": "http://sandbox.local",
                        "timeout_s": 12,
                    },
                    "max_stdout_kb": 1,
                    "max_stderr_kb": 1,
                }
            }

            summary = run_sandbox_step(
                project_path=project,
                config=config,
                run_id="run-1",
                step_id="step-1",
                language="python",
                code="print('ok')",
                input_paths=["docs/input.txt"],
            )

            run_step_dir = project / ".amon" / "runs" / "run-1" / "sandbox" / "step-1"
            artifacts_dir = project / "docs" / "artifacts" / "run-1" / "step-1"

            self.assertTrue((run_step_dir / "code.py").exists())
            self.assertTrue((run_step_dir / "request.json").exists())
            self.assertTrue((run_step_dir / "result.json").exists())
            self.assertTrue((artifacts_dir / "manifest.json").exists())
            self.assertTrue((artifacts_dir / "hello.txt").exists())

            request_data = json.loads((run_step_dir / "request.json").read_text(encoding="utf-8"))
            self.assertEqual(request_data["input_total_bytes"], 3)
            self.assertEqual(request_data["input_files"][0]["path"], "docs/input.txt")
            self.assertNotIn("api_key", request_data)

            result_data = json.loads((run_step_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result_data["exit_code"], 0)
            self.assertEqual(result_data["stdout"], "ok")

            manifest_data = json.loads((artifacts_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest_data["outputs"][0]["path"], "docs/artifacts/run-1/step-1/hello.txt")
            self.assertEqual(manifest_data["result"]["duration_ms"], 42)

            self.assertEqual(summary["exit_code"], 0)
            self.assertEqual(summary["outputs"][0]["path"], "docs/artifacts/run-1/step-1/hello.txt")

    @patch("amon.sandbox.client.request.urlopen")
    def test_run_sandbox_step_writes_bash_source_file(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _MockHTTPResponse(
            {
                "request_id": "req-bash",
                "job_id": "job-bash",
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 10,
                "stdout": "ok",
                "stderr": "",
                "output_files": [],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "audits").mkdir(parents=True, exist_ok=True)
            summary = run_sandbox_step(
                project_path=project,
                config={"sandbox": {"runner": {"base_url": "http://sandbox.local"}}},
                run_id="run-bash",
                step_id="step-bash",
                language="bash",
                code="echo ok",
                output_prefix="audits/artifacts/run-bash/step-bash/",
            )

            run_step_dir = project / ".amon" / "runs" / "run-bash" / "sandbox" / "step-bash"
            self.assertTrue((run_step_dir / "code.sh").exists())
            self.assertEqual(summary["exit_code"], 0)

    def test_records_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            run_dir, artifacts = ensure_run_step_dirs(project, "run-x", "step-y")
            self.assertTrue(run_dir.exists())
            self.assertTrue(artifacts.exists())

        long_text = "x" * 5000
        truncated = truncate_text(long_text, 1)
        self.assertIn("...[truncated]", truncated)


if __name__ == "__main__":
    unittest.main()
