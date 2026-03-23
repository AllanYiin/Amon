import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from amon.cli import main
from amon.core import AmonCore
from amon.runtime_vnext import ConfirmationQueue


class VNextCliIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["AMON_HOME"] = str(Path(self.temp_dir.name) / "data")
        self.core = AmonCore()
        self.core.initialize()
        self.project = self.core.create_project("stage6-cli")

    def tearDown(self) -> None:
        os.environ.pop("AMON_HOME", None)
        self.temp_dir.cleanup()

    def test_workspace_project_summary_and_run_create(self) -> None:
        summary = self._run_cli(["workspace", "projects", "summary", "--project", self.project.project_id])
        summary_payload = json.loads(summary)
        self.assertEqual(summary_payload["project"]["id"], self.project.project_id)

        run_output = self._run_cli(
            ["workspace", "runs", "create", "--project", self.project.project_id, "--template", "single"]
        )
        run_payload = json.loads(run_output)
        self.assertEqual(run_payload["run"]["status"], "compiled")

    def test_workspace_upload_preview_and_confirmation_list(self) -> None:
        source_file = Path(self.temp_dir.name) / "cli-demo.md"
        source_file.write_text("# cli\npreview", encoding="utf-8")

        upload_output = self._run_cli(
            ["workspace", "uploads", "add", "--project", self.project.project_id, str(source_file)]
        )
        upload_payload = json.loads(upload_output)
        asset_id = upload_payload["id"]

        preview_output = self._run_cli(
            ["workspace", "uploads", "preview", "--project", self.project.project_id, asset_id]
        )
        preview_payload = json.loads(preview_output)
        self.assertIn("preview", preview_payload["preview"]["text"])

        run_output = self._run_cli(
            ["workspace", "runs", "create", "--project", self.project.project_id, "--template", "single"]
        )
        run_id = json.loads(run_output)["run"]["id"]
        queue = ConfirmationQueue(Path(self.project.path))
        queue.enqueue(run_id, tool_name="filesystem.write", reason="cli confirm")

        confirmations_output = self._run_cli(
            ["workspace", "confirmations", "list", "--project", self.project.project_id]
        )
        confirmations = json.loads(confirmations_output)
        self.assertEqual(len(confirmations), 1)

    def _run_cli(self, argv: list[str]) -> str:
        output = io.StringIO()
        with patch("sys.argv", ["amon", *argv]), redirect_stdout(output):
            main()
        return output.getvalue().strip()
