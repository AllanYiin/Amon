import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class RunSingleTests(unittest.TestCase):
    def test_run_single_streams_and_writes_logs(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("需要設定 OPENAI_API_KEY 才能執行 LLM 測試")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)

                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    response = core.run_single("測試輸出", project_path=project_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            self.assertTrue(response)
            session_files = list((project_path / "sessions").glob("*.jsonl"))
            self.assertEqual(len(session_files), 1)
            events = [json.loads(line) for line in session_files[0].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events[0]["event"], "prompt")
            self.assertEqual(events[0]["content"], "測試輸出")
            chunk_events = [event for event in events if event["event"] == "chunk"]
            self.assertTrue(chunk_events)
            self.assertEqual(events[-1]["event"], "final")
            self.assertEqual(events[-1]["content"], response)
            self.assertTrue(events[0]["session_id"])
            self.assertTrue(all(event["session_id"] == events[0]["session_id"] for event in events))

            billing_log = Path(temp_dir) / "logs" / "billing.log"
            billing_payload = json.loads(billing_log.read_text(encoding="utf-8").strip())
            self.assertEqual(billing_payload["provider"], "openai")
            self.assertEqual(billing_payload["model"], "gpt-4o-mini")
            self.assertEqual(billing_payload["token"], 0)


if __name__ == "__main__":
    unittest.main()
