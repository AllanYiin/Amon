from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.cli import _handle_artifacts, build_parser  # noqa: E402


class CliArtifactsTests(unittest.TestCase):
    def test_parser_supports_artifacts_commands(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["artifacts", "run", "workspace/app.py", "--language", "auto", "--args", "a", "b"])
        self.assertEqual(args.command, "artifacts")
        self.assertEqual(args.artifacts_command, "run")
        self.assertEqual(args.path, "workspace/app.py")
        self.assertEqual(args.args, ["a", "b"])

    def test_artifacts_list_reads_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-cli-artifacts-") as tmpdir:
            project_path = Path(tmpdir)
            manifest_path = project_path / ".amon" / "artifacts" / "manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "updated_at": "2026-01-01T00:00:00Z",
                        "files": {
                            "workspace/app.py": {
                                "status": "valid",
                                "updated_at": "2026-01-01T00:00:00Z",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            core = SimpleNamespace(data_dir=project_path, get_project_path=lambda project: project_path)
            args = SimpleNamespace(artifacts_command="list", project=None)
            buffer = io.StringIO()
            cwd = Path.cwd()
            try:
                os.chdir(project_path)
                with patch("sys.stdout", buffer):
                    _handle_artifacts(core, args)
            finally:
                os.chdir(cwd)
            self.assertIn("workspace/app.py", buffer.getvalue())
            self.assertIn("valid", buffer.getvalue())

    @patch("amon.cli.run_sandbox_step")
    @patch("amon.cli.ConfigLoader")
    def test_artifacts_run_uses_auto_language_and_blocks_invalid(self, config_loader_cls, run_step_mock) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-cli-artifacts-") as tmpdir:
            project_path = Path(tmpdir)
            file_path = project_path / "workspace" / "app.py"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("print('ok')\n", encoding="utf-8")

            manifest_path = project_path / ".amon" / "artifacts" / "manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps({"version": "1", "updated_at": "", "files": {"workspace/app.py": {"status": "valid"}}}),
                encoding="utf-8",
            )

            fake_loader = MagicMock()
            fake_loader.resolve.return_value = SimpleNamespace(effective={"sandbox": {"runner": {"base_url": "http://runner"}}})
            config_loader_cls.return_value = fake_loader
            run_step_mock.return_value = {"exit_code": 0}

            core = SimpleNamespace(data_dir=project_path, get_project_path=lambda project: project_path)
            args = SimpleNamespace(
                artifacts_command="run",
                project=None,
                path="workspace/app.py",
                language="auto",
                args=["--name", "A"],
            )
            buffer = io.StringIO()
            cwd = Path.cwd()
            try:
                os.chdir(project_path)
                with patch("sys.stdout", buffer):
                    _handle_artifacts(core, args)
            finally:
                os.chdir(cwd)

            called = run_step_mock.call_args.kwargs
            self.assertEqual(called["language"], "python")
            self.assertIn("sys.argv", called["code"])

            manifest_path.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "updated_at": "",
                        "files": {
                            "workspace/app.py": {
                                "status": "invalid",
                                "checks": [{"message": "SyntaxError"}],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            cwd = Path.cwd()
            try:
                os.chdir(project_path)
                with self.assertRaises(ValueError):
                    _handle_artifacts(core, args)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
