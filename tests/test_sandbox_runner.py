import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon_sandbox_runner.config import RunnerLimits, RunnerSettings
from amon_sandbox_runner.runner import SandboxRunner


class SandboxRunnerTests(unittest.TestCase):
    def test_docker_run_has_mandatory_security_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = SandboxRunner(RunnerSettings(jobs_dir=Path(temp_dir)))
            with patch("amon_sandbox_runner.runner.subprocess.run") as run_mock:
                run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"ok", stderr=b"")
                result = runner.run({"language": "python", "code": "print('ok')", "timeout_s": 5, "input_files": []})

            self.assertEqual(result["exit_code"], 0)
            docker_args = run_mock.call_args_list[0].args[0]
            joined = " ".join(docker_args)
            for flag in (
                "--network none",
                "--read-only",
                "--cap-drop ALL",
                "--security-opt no-new-privileges",
                "--tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m",
                "--tmpfs /work:rw,nosuid,nodev,noexec,size=64m",
                ":/input:ro",
                ":/output:rw",
            ):
                self.assertIn(flag, joined)

    def test_collect_output_files_base64(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = SandboxRunner(RunnerSettings(jobs_dir=Path(temp_dir)))

            def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
                if cmd[:2] == ["docker", "run"]:
                    output_host = None
                    for idx, token in enumerate(cmd):
                        if token == "-v" and cmd[idx + 1].endswith(":/output:rw"):
                            output_host = cmd[idx + 1].split(":/output:rw", 1)[0]
                            break
                    assert output_host is not None
                    out_file = Path(output_host) / "result.txt"
                    out_file.write_text("hello", encoding="utf-8")
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"done", stderr=b"")
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

            with patch("amon_sandbox_runner.runner.subprocess.run", side_effect=fake_run):
                result = runner.run({"language": "python", "code": "print('ok')", "timeout_s": 5, "input_files": []})

            self.assertEqual(len(result["output_files"]), 1)
            self.assertEqual(result["output_files"][0]["path"], "result.txt")
            self.assertEqual(base64.b64decode(result["output_files"][0]["content_b64"]), b"hello")

    def test_timeout_triggers_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = SandboxRunner(RunnerSettings(jobs_dir=Path(temp_dir)))

            timeout = subprocess.TimeoutExpired(cmd=["docker", "run"], timeout=2)
            with patch(
                "amon_sandbox_runner.runner.subprocess.run",
                side_effect=[timeout, subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")],
            ) as run_mock:
                result = runner.run({"language": "python", "code": "while True: pass", "timeout_s": 2, "input_files": []})

            self.assertTrue(result["timed_out"])
            self.assertEqual(result["exit_code"], 124)
            cleanup_cmd = run_mock.call_args_list[1].args[0]
            self.assertEqual(cleanup_cmd[:3], ["docker", "rm", "-f"])

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = SandboxRunner(RunnerSettings(jobs_dir=Path(temp_dir)))
            payload = {
                "language": "python",
                "code": "print('x')",
                "timeout_s": 5,
                "input_files": [
                    {
                        "path": "../escape.txt",
                        "content_b64": base64.b64encode(b"x").decode("ascii"),
                    }
                ],
            }
            with self.assertRaises(ValueError):
                runner.run(payload)

    def test_rejects_too_many_input_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = RunnerSettings(jobs_dir=Path(temp_dir), limits=RunnerLimits(max_file_count=1))
            runner = SandboxRunner(settings)
            payload = {
                "language": "python",
                "code": "print('x')",
                "timeout_s": 5,
                "input_files": [
                    {"path": "a.txt", "content_b64": base64.b64encode(b"a").decode("ascii")},
                    {"path": "b.txt", "content_b64": base64.b64encode(b"b").decode("ascii")},
                ],
            }
            with self.assertRaisesRegex(ValueError, "input_files 數量超過上限"):
                runner.run(payload)

    def test_rejects_output_total_too_large(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = RunnerSettings(
                jobs_dir=Path(temp_dir),
                limits=RunnerLimits(max_output_total_bytes=4, max_single_file_bytes=4, max_file_count=4),
            )
            runner = SandboxRunner(settings)

            def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
                if cmd[:2] == ["docker", "run"]:
                    output_host = None
                    for idx, token in enumerate(cmd):
                        if token == "-v" and cmd[idx + 1].endswith(":/output:rw"):
                            output_host = cmd[idx + 1].split(":/output:rw", 1)[0]
                            break
                    assert output_host is not None
                    (Path(output_host) / "1.txt").write_bytes(b"aa")
                    (Path(output_host) / "2.txt").write_bytes(b"bbb")
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"done", stderr=b"")
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

            with patch("amon_sandbox_runner.runner.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, "output files 總大小超過上限"):
                    runner.run({"language": "python", "code": "print('ok')", "timeout_s": 5, "input_files": []})


    def test_health_snapshot_reports_docker_and_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = SandboxRunner(RunnerSettings(jobs_dir=Path(temp_dir), max_concurrency=3))

            def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
                if cmd[:3] == ["docker", "version", "--format"]:
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"24.0.0", stderr=b"")
                if cmd[:3] == ["docker", "image", "inspect"]:
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"[]", stderr=b"")
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

            with patch("amon_sandbox_runner.runner.subprocess.run", side_effect=fake_run):
                snapshot = runner.health_snapshot()

            self.assertTrue(snapshot["docker"]["available"])
            self.assertTrue(snapshot["docker"]["image_present"])
            self.assertEqual(snapshot["concurrency"]["max"], 3)
            self.assertEqual(snapshot["concurrency"]["inflight"], 0)
            self.assertEqual(snapshot["concurrency"]["utilization"], 0.0)

    def test_logs_include_request_and_job_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = SandboxRunner(RunnerSettings(jobs_dir=Path(temp_dir)))
            with patch("amon_sandbox_runner.runner.subprocess.run") as run_mock:
                run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"ok", stderr=b"")
                with self.assertLogs("amon_sandbox_runner", level="INFO") as logs:
                    result = runner.run(
                        {
                            "request_id": "req-123",
                            "language": "python",
                            "code": "print('ok')",
                            "timeout_s": 5,
                            "input_files": [],
                        }
                    )

            joined = "\n".join(logs.output)
            self.assertIn("sandbox.run.start", joined)
            self.assertIn("sandbox.run.finish", joined)
            self.assertEqual(result["request_id"], "req-123")
            self.assertTrue(result["job_id"])
            self.assertTrue(result["id"])
            self.assertNotEqual(result["job_id"], "")
            for line in logs.output:
                payload = json.loads(line.split(":", 2)[2].strip())
                self.assertIn("event", payload)


if __name__ == "__main__":
    unittest.main()
