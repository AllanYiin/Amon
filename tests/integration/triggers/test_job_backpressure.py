import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import yaml

from amon.core import AmonCore
from amon.storage import RunRepository
from amon.triggers.job_service import submit_job_run_request


class JobBackpressureIntegrationTests(unittest.TestCase):
    def test_job_trigger_blocks_when_active_queue_depth_reaches_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Trigger Job")
                jobs_dir = Path(temp_dir) / "jobs"
                jobs_dir.mkdir(parents=True, exist_ok=True)
                (jobs_dir / "watcher.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "run_request": {
                                "project_id": project.project_id,
                                "template_ref": "single",
                                "max_queue_depth": 1,
                            }
                        }
                    ),
                    encoding="utf-8",
                )

                first = submit_job_run_request(
                    {
                        "event_id": "evt-job-1",
                        "type": "doc.updated",
                        "scope": "job",
                        "actor": "job:watcher",
                        "payload": {"job_id": "watcher", "path": "docs/a.md"},
                        "risk": "low",
                    },
                    data_dir=Path(temp_dir),
                )
                second = submit_job_run_request(
                    {
                        "event_id": "evt-job-2",
                        "type": "doc.updated",
                        "scope": "job",
                        "actor": "job:watcher",
                        "payload": {"job_id": "watcher", "path": "docs/b.md"},
                        "risk": "low",
                    },
                    data_dir=Path(temp_dir),
                )

                self.assertEqual(first["status"], "queued")
                self.assertEqual(second["status"], "blocked")
                self.assertEqual(second["reason"], "max_queue_depth")
                run_repo = RunRepository(core.get_project_path(project.project_id))
                runs = run_repo.list()
                self.assertEqual(len(runs), 1)
                self.assertEqual(runs[0].trigger["kind"], "job")
                self.assertEqual(runs[0].trigger["id"], "watcher")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
