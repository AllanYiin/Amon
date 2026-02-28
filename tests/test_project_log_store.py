import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.logging import log_event
from amon.project_log_store import ProjectLogStore
from amon.project_registry import ProjectRegistry


class ProjectLogStoreTests(unittest.TestCase):
    def test_append_event_writes_project_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            project_id = "proj-a"
            project_path = data_dir / "projects" / project_id
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "amon.project.yaml").write_text(
                "amon:\n  project_id: proj-a\n  project_name: Project A\n",
                encoding="utf-8",
            )
            registry = ProjectRegistry(data_dir / "projects")
            registry.scan()
            store = ProjectLogStore(data_dir=data_dir, registry=registry)

            self.assertTrue(store.append_event({"event": "run.start", "project_id": project_id, "run_id": "run-01"}))
            payload = json.loads((project_path / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(payload["project_id"], project_id)
            self.assertEqual(payload["run_id"], "run-01")

    def test_append_warns_and_degrades_when_project_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            registry = ProjectRegistry(data_dir / "projects")
            registry.scan()
            logger = logging.getLogger("test.project-log-store")
            store = ProjectLogStore(data_dir=data_dir, registry=registry, logger=logger)
            with self.assertLogs("test.project-log-store", level="WARNING") as captured:
                self.assertFalse(store.append_event({"event": "run.start", "project_id": "missing", "run_id": "run-01"}))
            self.assertIn("unknown project_id=missing", "\n".join(captured.output))

    def test_contract_run_events_contain_project_and_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-contract"
                project_path = Path(temp_dir) / "projects" / project_id
                project_path.mkdir(parents=True, exist_ok=True)
                (project_path / "amon.project.yaml").write_text(
                    "amon:\n  project_id: proj-contract\n  project_name: Project Contract\n",
                    encoding="utf-8",
                )
                log_event({"event": "run.start", "project_id": project_id, "run_id": "run-c1"})
                log_event({"event": "run.done", "project_id": project_id, "run_id": "run-c1"})
            finally:
                os.environ.pop("AMON_HOME", None)

            records = [json.loads(line) for line in (project_path / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            by_event = {record.get("event"): record for record in records}
            self.assertEqual(by_event["run.start"]["project_id"], project_id)
            self.assertEqual(by_event["run.start"]["run_id"], "run-c1")
            self.assertEqual(by_event["run.done"]["project_id"], project_id)
            self.assertEqual(by_event["run.done"]["run_id"], "run-c1")


if __name__ == "__main__":
    unittest.main()
