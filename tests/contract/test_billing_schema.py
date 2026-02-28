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
    def test_estimate_llm_tokens_uses_token_counter_without_name_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            core = AmonCore(data_dir=Path(temp_dir))
            prompt_tokens, completion_tokens = core._estimate_llm_tokens(
                "請整理本週待辦", "好的，已整理完成。", config={}
            )
            self.assertIsInstance(prompt_tokens, int)
            self.assertIsInstance(completion_tokens, int)
            self.assertGreaterEqual(prompt_tokens, 0)
            self.assertGreaterEqual(completion_tokens, 0)

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
                for key in ["run_id", "cost", "tokens", "usage", "calls", "records"]:
                    self.assertIn(key, first)
            finally:
                os.environ.pop("AMON_HOME", None)


    def test_billing_stats_filter_by_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project_a = core.create_project("billing-a")
                project_b = core.create_project("billing-b")

                usage_a = Path(project_a.path) / ".amon" / "billing" / "usage.jsonl"
                usage_a.parent.mkdir(parents=True, exist_ok=True)
                usage_a.write_text(
                    "\n".join(
                        [
                            json.dumps({"ts": "2026-01-03T00:00:00+00:00", "project_id": project_a.project_id, "run_id": "run-a1", "provider": "openai", "model": "gpt-5.2", "cost": 1.0, "total_tokens": 100}, ensure_ascii=False),
                            json.dumps({"ts": "2026-01-03T01:00:00+00:00", "project_id": project_a.project_id, "run_id": "run-a2", "provider": "openai", "model": "gpt-5.2", "cost": 2.0, "total_tokens": 200}, ensure_ascii=False),
                        ]
                    ) + "\n",
                    encoding="utf-8",
                )

                usage_b = Path(project_b.path) / ".amon" / "billing" / "usage.jsonl"
                usage_b.parent.mkdir(parents=True, exist_ok=True)
                usage_b.write_text(
                    json.dumps({"ts": "2026-01-03T02:00:00+00:00", "project_id": project_b.project_id, "run_id": "run-b1", "provider": "openai", "model": "gpt-5.2", "cost": 9.0, "total_tokens": 900}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                handler = object.__new__(AmonUIHandler)
                handler.core = core

                summary = handler._build_billing_summary(project_id=project_a.project_id)
                series = handler._build_billing_series(project_id=project_a.project_id)

                self.assertAlmostEqual(summary["project_total"]["cost"], 3.0)
                self.assertEqual(summary["project_total"]["tokens"], 300)
                self.assertEqual({item["run_id"] for item in series}, {"run-a1", "run-a2"})
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
