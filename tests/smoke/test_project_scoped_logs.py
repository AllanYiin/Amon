import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.logging import log_billing, log_event


class ProjectScopedLogsSmokeTests(unittest.TestCase):
    def test_log_event_and_billing_write_project_scoped_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "smoke-project"
                project_path = Path(temp_dir) / "projects" / project_id
                project_path.mkdir(parents=True, exist_ok=True)
                (project_path / "amon.project.yaml").write_text(
                    "amon:\n  project_id: smoke-project\n  project_name: Smoke Project\n",
                    encoding="utf-8",
                )

                log_event({"event": "smoke_event", "project_id": project_id})
                log_billing({"event": "billing_record", "project_id": project_id, "cost": 0.1, "usage": 12})

                events_log = project_path / ".amon" / "logs" / "events.jsonl"
                billing_log = project_path / ".amon" / "logs" / "billing.jsonl"
                self.assertTrue(events_log.exists())
                self.assertTrue(billing_log.exists())

                event_payload = json.loads(events_log.read_text(encoding="utf-8").splitlines()[-1])
                billing_payload = json.loads(billing_log.read_text(encoding="utf-8").splitlines()[-1])
                self.assertEqual(event_payload.get("project_id"), project_id)
                self.assertEqual(billing_payload.get("project_id"), project_id)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
