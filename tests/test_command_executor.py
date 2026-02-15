import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.session_store import create_chat_session
from amon.commands.executor import CommandPlan, execute
from amon.core import AmonCore


class CommandExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["AMON_HOME"] = self.temp_dir.name
        self.core = AmonCore()
        self.core.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        os.environ.pop("AMON_HOME", None)

    def test_projects_list_returns_result(self) -> None:
        record = self.core.create_project("測試專案")
        chat_id = create_chat_session(record.project_id)
        plan = CommandPlan(
            name="projects.list",
            args={},
            project_id=record.project_id,
            chat_id=chat_id,
        )

        result = execute(plan, confirmed=True)

        self.assertEqual(result["status"], "ok")
        self.assertIn("projects", result["result"])
        self.assertGreaterEqual(len(result["result"]["projects"]), 1)

    def test_projects_delete_requires_confirm(self) -> None:
        record = self.core.create_project("待刪除專案")
        chat_id = create_chat_session(record.project_id)
        plan = CommandPlan(
            name="projects.delete",
            args={"project_id": record.project_id},
            project_id=record.project_id,
            chat_id=chat_id,
        )

        result = execute(plan, confirmed=False)

        self.assertEqual(result["status"], "confirm_required")
        refreshed = self.core.get_project(record.project_id)
        self.assertEqual(refreshed.status, "active")

    def test_schedules_add_updates_schedule_file(self) -> None:
        record = self.core.create_project("排程專案")
        chat_id = create_chat_session(record.project_id)
        plan = CommandPlan(
            name="schedules.add",
            args={
                "template_id": "tpl_123",
                "cron": "*/5 * * * *",
                "vars": {"name": "測試"},
            },
            project_id=record.project_id,
            chat_id=chat_id,
        )

        result = execute(plan, confirmed=True)

        self.assertEqual(result["status"], "ok")
        schedules_path = self.core.data_dir / "schedules" / "schedules.json"
        payload = json.loads(schedules_path.read_text(encoding="utf-8"))
        schedule_ids = [item.get("schedule_id") for item in payload.get("schedules", [])]
        self.assertIn(result["result"]["schedule"]["schedule_id"], schedule_ids)

    def test_jobs_start_updates_state_file(self) -> None:
        record = self.core.create_project("任務專案")
        chat_id = create_chat_session(record.project_id)
        jobs_dir = self.core.data_dir / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        job_id = "sample-job"
        config_path = jobs_dir / f"{job_id}.yaml"
        config_path.write_text("{}", encoding="utf-8")
        plan = CommandPlan(
            name="jobs.start",
            args={"job_id": job_id},
            project_id=record.project_id,
            chat_id=chat_id,
        )

        try:
            result = execute(plan, confirmed=True)
            self.assertEqual(result["status"], "ok")
            state_path = self.core.data_dir / "jobs" / "state" / f"{job_id}.json"
            for _ in range(30):
                if state_path.exists():
                    break
                time.sleep(0.1)
            self.assertTrue(state_path.exists())
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "RUNNING")
        finally:
            execute(
                CommandPlan(
                    name="jobs.stop",
                    args={"job_id": job_id},
                    project_id=record.project_id,
                    chat_id=chat_id,
                ),
                confirmed=True,
            )

    def test_graph_patch_writes_audit_and_emits_event(self) -> None:
        record = self.core.create_project("圖補丁專案")
        chat_id = create_chat_session(record.project_id)
        plan = CommandPlan(
            name="graph.patch",
            args={"message": "請將節點 A 連到節點 B"},
            project_id=record.project_id,
            chat_id=chat_id,
        )

        result = execute(plan, confirmed=True)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["status"], "queued_for_review")
        audit_path = Path(result["result"]["audit_path"])
        self.assertTrue(audit_path.exists())
        audit_records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(audit_records), 1)
        self.assertEqual(audit_records[0]["project_id"], record.project_id)
        self.assertEqual(audit_records[0]["chat_id"], chat_id)
        self.assertEqual(audit_records[0]["message"], "請將節點 A 連到節點 B")

        events_path = self.core.data_dir / "events" / "events.jsonl"
        self.assertTrue(events_path.exists())
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        graph_patch_events = [event for event in events if event.get("type") == "graph.patch_requested"]
        self.assertEqual(len(graph_patch_events), 1)
        self.assertEqual(graph_patch_events[0]["project_id"], record.project_id)
        self.assertEqual(graph_patch_events[0]["payload"]["chat_id"], chat_id)


if __name__ == "__main__":
    unittest.main()
