import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.core import AmonCore
from amon.ui_server import AmonUIHandler


class ContextStatsSchemaContractTests(unittest.TestCase):
    def test_context_stats_schema_contains_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("context-schema")

                handler = object.__new__(AmonUIHandler)
                handler.core = core

                payload = handler._build_project_context_stats(project.project_id)

                self.assertIn("token_estimate", payload)
                token_estimate = payload["token_estimate"]
                self.assertIn("used", token_estimate)
                self.assertIn("capacity", token_estimate)
                self.assertIn("remaining", token_estimate)
                self.assertIn("estimated_cost_usd", token_estimate)
                self.assertIn("usage_ratio", token_estimate)
                self.assertIsInstance(token_estimate["used"], int)
                self.assertIsInstance(token_estimate["capacity"], int)
                self.assertIsInstance(token_estimate["remaining"], int)
                self.assertIsInstance(token_estimate["usage_ratio"], float)
                self.assertIsInstance(token_estimate["estimated_cost_usd"], float)

                self.assertIn("categories", payload)
                self.assertIsInstance(payload["categories"], list)
                self.assertGreater(len(payload["categories"]), 0)
                required_keys = {"project_context", "system_prompt", "tools_definition", "skills", "tool_use", "chat_history"}
                category_keys = {item.get("key") for item in payload["categories"]}
                self.assertTrue(required_keys.issubset(category_keys))
                for item in payload["categories"]:
                    self.assertIn("key", item)
                    self.assertIn("tokens", item)
                    self.assertIsInstance(item["tokens"], int)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
