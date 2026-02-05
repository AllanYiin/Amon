import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.scheduler.engine import tick, write_schedules


class SchedulerEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["AMON_HOME"] = self.temp_dir.name
        self.core = AmonCore()
        self.core.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        os.environ.pop("AMON_HOME", None)

    def test_interval_schedule_fires_once(self) -> None:
        start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        schedule = {
            "schedule_id": "sc_interval",
            "template_id": "tpl_001",
            "type": "interval",
            "interval_seconds": 60,
            "created_at": start_time.isoformat(timespec="seconds"),
            "misfire_grace_seconds": 5,
            "jitter_seconds": 0,
        }
        write_schedules({"schedules": [schedule]}, data_dir=Path(self.temp_dir.name))

        tick(now=start_time + timedelta(seconds=60), data_dir=Path(self.temp_dir.name))

        events_path = Path(self.temp_dir.name) / "events" / "events.jsonl"
        self.assertTrue(events_path.exists())
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        fired = [event for event in events if event.get("type") == "schedule.fired"]
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["payload"]["schedule_id"], "sc_interval")


if __name__ == "__main__":
    unittest.main()
