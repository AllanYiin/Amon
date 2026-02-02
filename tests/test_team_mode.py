import json
import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class TeamModeTests(unittest.TestCase):
    def test_team_mode_generates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                core.set_config_value(
                    "providers.mock",
                    {
                        "type": "mock",
                        "default_model": "mock-model",
                        "stream_chunks": [
                            '{"tasks":[{"task_id":"t1","title":"測試任務","requiredCapabilities":["analysis"]}]}'
                        ],
                    },
                    project_path=project_path,
                )
                core.set_config_value("amon.provider", "mock", project_path=project_path)
                core.set_config_value("amon.team_max_retries", 1, project_path=project_path)

                core.run_team("請完成測試流程", project_path=project_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            tasks_path = project_path / "tasks" / "tasks.json"
            self.assertTrue(tasks_path.exists())
            tasks_payload = json.loads(tasks_path.read_text(encoding="utf-8"))
            self.assertEqual(tasks_payload["tasks"][0]["status"], "done")

            task_dir = project_path / "docs" / "tasks" / "t1"
            self.assertTrue((task_dir / "persona.json").exists())
            self.assertTrue((task_dir / "result.md").exists())
            audit_path = project_path / "docs" / "audits" / "t1.json"
            self.assertTrue(audit_path.exists())
            audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(audit_payload["status"], "APPROVED")
            self.assertTrue((project_path / "docs" / "final.md").exists())


if __name__ == "__main__":
    unittest.main()
