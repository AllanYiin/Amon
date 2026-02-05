import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.daemon import run_daemon_once


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


if __name__ == "__main__":
    unittest.main()
