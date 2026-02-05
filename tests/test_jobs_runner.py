import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from amon.jobs.runner import start_job, stop_job


class JobRunnerTests(unittest.TestCase):
    def test_heartbeat_updates_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            job_id = "heartbeat-job"
            jobs_dir = Path(temp_dir) / "jobs"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            config_path = jobs_dir / f"{job_id}.yaml"
            config_path.write_text(yaml.safe_dump({}), encoding="utf-8")

            try:
                start_job(job_id, heartbeat_interval_seconds=1)
                state_path = Path(temp_dir) / "jobs" / "state" / f"{job_id}.json"
                self._wait_for_file(state_path, timeout=3)
                first_state = json.loads(state_path.read_text(encoding="utf-8"))
                time.sleep(1.2)
                second_state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertNotEqual(first_state["last_heartbeat_ts"], second_state["last_heartbeat_ts"])
            finally:
                stop_job(job_id)
                os.environ.pop("AMON_HOME", None)

    def test_filesystem_watcher_emits_doc_updated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            job_id = "watch-job"
            watch_dir = Path(temp_dir) / "watched"
            watch_dir.mkdir(parents=True, exist_ok=True)
            jobs_dir = Path(temp_dir) / "jobs"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            config_path = jobs_dir / f"{job_id}.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "watch_paths": [str(watch_dir)],
                        "watch_interval_seconds": 1,
                        "debounce_seconds": 1,
                    }
                ),
                encoding="utf-8",
            )

            try:
                start_job(job_id, heartbeat_interval_seconds=1)
                target_file = watch_dir / "sample.txt"
                target_file.write_text("hello", encoding="utf-8")
                time.sleep(1.2)
                target_file.write_text("hello again", encoding="utf-8")
                events_path = Path(temp_dir) / "events" / "events.jsonl"
                self._wait_for_file(events_path, timeout=4)
                self._wait_for_event(events_path, "doc.updated", timeout=4)
            finally:
                stop_job(job_id)
                os.environ.pop("AMON_HOME", None)

    def _wait_for_file(self, path: Path, timeout: float) -> None:
        start = time.time()
        while time.time() - start < timeout:
            if path.exists():
                return
            time.sleep(0.1)
        raise AssertionError(f"檔案不存在：{path}")

    def _wait_for_event(self, path: Path, event_type: str, timeout: float) -> None:
        start = time.time()
        while time.time() - start < timeout:
            if path.exists():
                lines = path.read_text(encoding="utf-8").strip().splitlines()
                for line in lines:
                    if not line:
                        continue
                    payload = json.loads(line)
                    if payload.get("type") == event_type:
                        return
            time.sleep(0.2)
        raise AssertionError(f"找不到事件：{event_type}")


if __name__ == "__main__":
    unittest.main()
