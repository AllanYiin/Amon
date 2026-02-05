import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from amon import cli
from amon.jobs.runner import stop_job


class AutomationCliTests(unittest.TestCase):
    def test_add_schedule_updates_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                schedule_payload = {
                    "schedule_id": "schedule-cli",
                    "type": "interval",
                    "interval_seconds": 60,
                    "enabled": True,
                }
                self._run_cli(["schedules", "add", "--payload", json.dumps(schedule_payload)])
                schedules_path = Path(temp_dir) / "schedules" / "schedules.json"
                self.assertTrue(schedules_path.exists())
                data = json.loads(schedules_path.read_text(encoding="utf-8"))
                schedule_ids = [entry.get("schedule_id") for entry in data.get("schedules", [])]
                self.assertIn("schedule-cli", schedule_ids)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_start_job_updates_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            job_id = "cli-job"
            jobs_dir = Path(temp_dir) / "jobs"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            (jobs_dir / f"{job_id}.yaml").write_text(yaml.safe_dump({}), encoding="utf-8")
            try:
                self._run_cli(["jobs", "start", job_id, "--heartbeat-interval", "1"])
                state_path = Path(temp_dir) / "jobs" / "state" / f"{job_id}.json"
                self._wait_for_file(state_path, timeout=3)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(state.get("status"), "RUNNING")
            finally:
                stop_job(job_id, data_dir=Path(temp_dir))
                os.environ.pop("AMON_HOME", None)

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

    def _wait_for_file(self, path: Path, timeout: float) -> None:
        start = time.time()
        while time.time() - start < timeout:
            if path.exists():
                return
            time.sleep(0.1)
        raise AssertionError(f"檔案不存在：{path}")


if __name__ == "__main__":
    unittest.main()
