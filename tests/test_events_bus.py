import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.events import emit_event


class EventBusTests(unittest.TestCase):
    def test_emit_event_appends_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                event_id = emit_event(
                    {
                        "type": "project.create",
                        "scope": "project",
                        "project_id": "proj-1",
                        "actor": "system",
                        "payload": {"project_name": "測試專案"},
                        "risk": "low",
                    }
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            events_path = Path(temp_dir) / "events" / "events.jsonl"
            lines = events_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            required_fields = {"event_id", "ts", "type", "scope", "actor", "payload", "risk", "project_id"}
            self.assertTrue(required_fields.issubset(payload.keys()))
            self.assertEqual(payload["event_id"], event_id)
            self.assertEqual(payload["type"], "project.create")
            self.assertEqual(payload["scope"], "project")
            self.assertEqual(payload["project_id"], "proj-1")
            self.assertEqual(payload["actor"], "system")
            self.assertEqual(payload["payload"], {"project_name": "測試專案"})
            self.assertEqual(payload["risk"], "low")
            parsed_ts = datetime.fromisoformat(payload["ts"])
            self.assertIsNotNone(parsed_ts.tzinfo)


if __name__ == "__main__":
    unittest.main()
