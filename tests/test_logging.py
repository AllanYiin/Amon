import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon import cli
from amon.logging import log_billing, log_event


class LoggingTests(unittest.TestCase):
    def test_log_event_appends_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                log_event({"event": "test_event", "project_id": "proj-1", "session_id": "sess-1"})
            finally:
                os.environ.pop("AMON_HOME", None)

            log_path = Path(temp_dir) / "logs" / "amon.log"
            payload = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["event"], "test_event")
            self.assertEqual(payload["project_id"], "proj-1")
            self.assertEqual(payload["session_id"], "sess-1")
            self.assertEqual(payload["level"], "INFO")
            parsed_ts = datetime.fromisoformat(payload["ts"])
            self.assertIsNotNone(parsed_ts.tzinfo)

    def test_log_billing_appends_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                log_billing({"event": "billing_test", "project_id": "proj-2", "session_id": "sess-2"})
            finally:
                os.environ.pop("AMON_HOME", None)

            log_path = Path(temp_dir) / "logs" / "billing.log"
            payload = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["event"], "billing_test")
            self.assertEqual(payload["project_id"], "proj-2")
            self.assertEqual(payload["session_id"], "sess-2")
            self.assertEqual(payload["token"], 0)
            parsed_ts = datetime.fromisoformat(payload["ts"])
            self.assertIsNotNone(parsed_ts.tzinfo)

    def test_cli_project_commands_write_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = self._run_project_flow()
            finally:
                os.environ.pop("AMON_HOME", None)

            self.assertTrue(project_id)

    def _run_project_flow(self) -> str:
        log_path = Path(os.environ["AMON_HOME"]) / "logs" / "amon.log"

        output = self._run_cli(["project", "create", "測試專案"])
        project_id = self._extract_project_id(output)
        self._assert_log_written(log_path)

        self._run_cli(["project", "list"])
        self._assert_log_written(log_path)

        self._run_cli(["project", "update", project_id, "--name", "更新專案"])
        self._assert_log_written(log_path)

        self._run_cli(["project", "delete", project_id])
        self._assert_log_written(log_path)

        self._run_cli(["project", "restore", project_id])
        self._assert_log_written(log_path)

        return project_id

    def _run_cli(self, args: list[str]) -> str:
        original_argv = sys.argv
        sys.argv = ["amon", *args]
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                cli.main()
        finally:
            sys.argv = original_argv
        return buffer.getvalue()

    def _extract_project_id(self, output: str) -> str:
        match = re.search(r"專案 ID：(.+)", output)
        self.assertIsNotNone(match, "project id not found in CLI output")
        return match.group(1).strip() if match else ""

    def _assert_log_written(self, log_path: Path) -> None:
        self.assertTrue(log_path.exists())
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
