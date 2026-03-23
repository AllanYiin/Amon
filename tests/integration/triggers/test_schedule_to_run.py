import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.core import AmonCore
from amon.daemon.runner import run_daemon_once
from amon.scheduler.engine import write_schedules
from amon.storage import RunRepository


class ScheduleToRunIntegrationTests(unittest.TestCase):
    def test_schedule_fired_creates_queued_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Trigger Schedule")
                now = datetime.now(timezone.utc)
                write_schedules(
                    {
                        "schedules": [
                            {
                                "schedule_id": "schedule.demo",
                                "project_id": project.project_id,
                                "template_id": "single",
                                "type": "interval",
                                "interval_seconds": 60,
                                "created_at": (now - timedelta(seconds=120)).isoformat(timespec="seconds"),
                                "misfire_grace_seconds": 0,
                            }
                        ]
                    },
                    data_dir=Path(temp_dir),
                )

                run_daemon_once(data_dir=Path(temp_dir))

                run_repo = RunRepository(core.get_project_path(project.project_id))
                runs = run_repo.list()
                self.assertEqual(len(runs), 1)
                self.assertEqual(runs[0].status, "queued")
                self.assertEqual(runs[0].trigger["kind"], "schedule")
                self.assertEqual(runs[0].trigger["id"], "schedule.demo")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
