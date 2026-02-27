import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.core import AmonCore
from amon.ui_server import AmonUIHandler


class BillingSchemaContractTests(unittest.TestCase):
    def test_billing_summary_and_series_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("billing-schema")
                project_path = Path(project.path)

                usage_path = project_path / ".amon" / "billing" / "usage.jsonl"
                usage_path.parent.mkdir(parents=True, exist_ok=True)
                fixture = {
                    "ts": "2026-01-03T00:00:00+00:00",
                    "project_id": project.project_id,
                    "run_id": "run-1",
                    "provider": "openai",
                    "model": "gpt-5.2",
                    "cost": 0.25,
                    "usage": 128,
                    "total_tokens": 128,
                }
                usage_path.write_text(json.dumps(fixture, ensure_ascii=False) + "\n", encoding="utf-8")

                handler = object.__new__(AmonUIHandler)
                handler.core = core

                summary = handler._build_billing_summary(project_id=project.project_id)
                self.assertIn("project_total", summary)
                self.assertIn("mode_breakdown", summary)
                self.assertIn("breakdown", summary)
                self.assertIn("run_trend", summary)
                self.assertIn("current_run", summary)

                series = handler._build_billing_series(project_id=project.project_id)
                self.assertIsInstance(series, list)
                self.assertGreaterEqual(len(series), 1)
                first = series[0]
                for key in ["date", "cost", "tokens", "usage", "calls"]:
                    self.assertIn(key, first)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
