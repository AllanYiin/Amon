import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.daemon import run_daemon_once
from amon.core import AmonCore
from amon.domain import RunRecord
from amon.storage import RunRepository
from amon.taskgraph3.runtime import TaskGraph3RunResult


class DaemonAutomationTests(unittest.TestCase):
    def test_daemon_tick_schedule_hook_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                schedules_dir = Path(temp_dir) / "schedules"
                schedules_dir.mkdir(parents=True, exist_ok=True)
                schedule_path = schedules_dir / "schedules.json"
                schedule_payload = {
                    "schedules": [
                        {
                            "schedule_id": "schedule-1",
                            "type": "interval",
                            "interval_seconds": 60,
                            "next_fire_at": (datetime.now().astimezone() - timedelta(seconds=5)).isoformat(timespec="seconds"),
                            "enabled": True,
                        }
                    ]
                }
                schedule_path.write_text(json.dumps(schedule_payload, ensure_ascii=False, indent=2), encoding="utf-8")

                hooks_dir = Path(temp_dir) / "hooks"
                hooks_dir.mkdir(parents=True, exist_ok=True)
                (hooks_dir / "schedule_hook.yaml").write_text(
                    "\n".join(
                        [
                            "event_types:",
                            "  - schedule.fired",
                            "action:",
                            "  type: tool.call",
                            "  tool: echoer",
                            "  args:",
                            "    schedule_id: \"{{event.payload.schedule_id}}\"",
                        ]
                    ),
                    encoding="utf-8",
                )

                calls: list[tuple[str, dict[str, object], str | None]] = []

                def fake_executor(tool_name: str, args: dict[str, object], project_id: str | None) -> dict[str, object]:
                    calls.append((tool_name, args, project_id))
                    return {"ok": True}

                run_daemon_once(data_dir=Path(temp_dir), tool_executor=fake_executor)
                self.assertEqual(len(calls), 1)
                tool_name, args, project_id = calls[0]
                self.assertEqual(tool_name, "echoer")
                self.assertEqual(project_id, None)
                self.assertEqual(args["schedule_id"], "schedule-1")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_daemon_once_reconciles_queued_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("daemon-run-project")
                project_path = Path(project.path)
                run_repo = RunRepository(project_path)
                run_id = "run-daemon-001"
                graph_payload = {"version": "taskgraph.v3", "nodes": [], "edges": []}
                run = RunRecord.create(
                    run_id=run_id,
                    status="queued",
                    metadata={
                        "variables": {"source": "daemon"},
                        "control": {
                            "desired_status": "active",
                            "request_id": "req-daemon-001",
                            "request_status": "queued",
                            "graph_path": str(project_path / ".amon" / "runs" / run_id / "compiled.taskgraph.v3.json"),
                            "retry_budget": 1,
                            "repair_budget": 0,
                            "attempt_count": 0,
                            "next_wake_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                        },
                    },
                )
                run_repo.create(run, snapshot_manifest={}, compiled_graph=graph_payload)

                def fake_run_graph(self, *, project_path, graph_path, variables=None, run_id=None, request_id=None, stream_handler=None, **kwargs):
                    run_dir = Path(project_path) / ".amon" / "runs" / str(run_id)
                    run_dir.mkdir(parents=True, exist_ok=True)
                    state = {"run_id": run_id, "status": "succeeded", "nodes": {}, "variables": variables or {}}
                    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    (run_dir / "events.jsonl").write_text(json.dumps({"event": "run_end", "run_id": run_id}, ensure_ascii=False), encoding="utf-8")
                    return TaskGraph3RunResult(run_id=str(run_id), run_dir=run_dir, state=state)

                with patch.object(AmonCore, "run_graph", new=fake_run_graph):
                    run_daemon_once(data_dir=Path(temp_dir))

                updated = run_repo.get(run_id)
                self.assertEqual(updated.status, "succeeded")
                control = dict(updated.metadata.get("control") or {})
                self.assertEqual(control.get("request_status"), "completed")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
