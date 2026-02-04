import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class BudgetTests(unittest.TestCase):
    def test_budget_blocks_team_and_self_critique(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("需要設定 OPENAI_API_KEY 才能執行 LLM 測試")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                core.set_config_value("billing.daily_budget", 1, project_path=project_path)

                core.run_single("測試用量", project_path=project_path)
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    core.run_single("再次測試用量", project_path=project_path)
                self.assertIn("用量上限", buffer.getvalue())

                with self.assertRaises(RuntimeError):
                    core.run_self_critique("測試 self critique", project_path=project_path)
                with self.assertRaises(RuntimeError):
                    core.run_team("測試 team", project_path=project_path)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
