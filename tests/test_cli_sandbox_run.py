import io
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.cli import _handle_sandbox, build_parser  # noqa: E402


class _FixedDateTime:
    @staticmethod
    def now() -> datetime:
        return datetime(2026, 2, 15, 12, 34, 56)


class CliSandboxRunTests(unittest.TestCase):
    def test_parser_supports_sandbox_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "sandbox",
                "run",
                "--project",
                "p1",
                "--language",
                "python",
                "--code",
                "print('ok')",
                "--input",
                "docs/a.txt",
                "--timeout-s",
                "30",
            ]
        )

        self.assertEqual(args.command, "sandbox")
        self.assertEqual(args.sandbox_command, "run")
        self.assertEqual(args.project, "p1")
        self.assertEqual(args.input, ["docs/a.txt"])
        self.assertEqual(args.timeout_s, 30)

    @patch("amon.cli.run_sandbox_step")
    @patch("amon.cli.ConfigLoader")
    @patch("amon.cli.datetime", _FixedDateTime)
    def test_handle_sandbox_run_builds_service_args(self, config_loader_cls, run_step_mock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            code_file = project_path / "code.py"
            code_file.write_text("print('from file')", encoding="utf-8")

            fake_loader = MagicMock()
            fake_loader.resolve.return_value = SimpleNamespace(effective={"sandbox": {"runner": {"base_url": "http://runner"}}})
            config_loader_cls.return_value = fake_loader

            run_step_mock.return_value = {
                "exit_code": 0,
                "stdout": "ok",
                "stderr": "",
                "manifest_path": str(project_path / "docs" / "artifacts" / "run-20260215123456" / "cli" / "manifest.json"),
                "written_files": ["/tmp/f1.txt"],
            }

            core = SimpleNamespace(
                data_dir=project_path,
                get_project=lambda project_id: SimpleNamespace(project_id=project_id, path=project_path),
            )
            args = SimpleNamespace(
                sandbox_command="run",
                project="proj-1",
                language="python",
                code_file=str(code_file),
                code=None,
                input=["docs/input.txt", "workspace/config.yaml"],
                output_prefix=None,
                timeout_s=90,
            )

            buffer = io.StringIO()
            with patch("sys.stdout", buffer):
                _handle_sandbox(core, args)

            run_step_mock.assert_called_once()
            called = run_step_mock.call_args.kwargs
            self.assertEqual(called["project_path"], project_path)
            self.assertEqual(called["run_id"], "run-20260215123456")
            self.assertEqual(called["step_id"], "cli")
            self.assertEqual(called["language"], "python")
            self.assertEqual(called["code"], "print('from file')")
            self.assertEqual(called["input_paths"], ["docs/input.txt", "workspace/config.yaml"])
            self.assertEqual(called["output_prefix"], "docs/artifacts/run-20260215123456/cli")
            self.assertEqual(called["timeout_s"], 90)
            self.assertIn("exit_code: 0", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
