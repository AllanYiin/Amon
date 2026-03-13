import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class TeamModeTests(unittest.TestCase):
    def test_team_mode_generates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            core = AmonCore(data_dir=Path(temp_dir))
            core.initialize()
            project = core.create_project("測試專案")
            project_path = Path(project.path)

            def fake_run_agent_task(_prompt: str, **kwargs):
                node_id = kwargs.get("node_id")
                outputs = {
                    "pm_todo": "專案經理：\n- [ ] Step0：檢查 docs\n- [ ] Step1：拆解子任務",
                    "pm_log_bootstrap": "專案經理：啟動紀錄與分派策略",
                    "pm_plan": json.dumps(
                        {
                            "tasks": [
                                {
                                    "task_id": "T1",
                                    "title": "任務一",
                                    "role": "分析師",
                                    "description": "完成分析",
                                    "requiredCapabilities": ["analysis"],
                                    "role_assignment_reason": "需要分析能力",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    "task_teamwork_map": json.dumps(
                        {
                            "task_id": "T1",
                            "title": "任務一",
                            "role": "分析師",
                            "description": "完成分析",
                            "persona": {"name": "Alice", "role": "分析師", "focus": "分析"},
                            "role_factory_markdown": "角色工廠：已指派分析師 Alice",
                            "result_markdown": "結果：已完成分析並提供可驗證成果。",
                            "audit": {"status": "APPROVED", "feedback": "ok"},
                            "status": "done",
                        },
                        ensure_ascii=False,
                    ),
                    "audit_committee_role_factory": json.dumps(
                        {"committee": [{"name": "Q", "role": "品質", "focus": "品質", "instructions": "嚴格審查"}]},
                        ensure_ascii=False,
                    ),
                    "audit_committee_gate": json.dumps(
                        {"status": "APPROVED_ALL", "reason": "ok", "actions": []},
                        ensure_ascii=False,
                    ),
                    "synthesis": (
                        "# TeamworksGPT\n"
                        "## 我務必依照以下的【角色定義】 以及【工作流程】來完成任務\n"
                        "已遵守 Step0~Step6，且稽核會全員通過。"
                    ),
                }
                if node_id not in outputs:
                    raise AssertionError(f"unexpected node_id={node_id}")
                return outputs[node_id]

            with patch.object(core, "run_agent_task", side_effect=fake_run_agent_task):
                core.run_team("請完成測試流程", project_path=project_path)

            tasks_path = project_path / "tasks" / "tasks.json"
            self.assertTrue(tasks_path.exists())
            tasks_payload = json.loads(tasks_path.read_text(encoding="utf-8"))
            tasks = tasks_payload.get("tasks") or []
            self.assertTrue(tasks)
            task_id = tasks[0].get("task_id")
            self.assertTrue(task_id)

            task_dir = project_path / "docs" / "tasks" / str(task_id)
            self.assertTrue((task_dir / "persona.json").exists())
            self.assertTrue((task_dir / "result.md").exists())
            audit_path = project_path / "docs" / "audits" / f"{task_id}.json"
            self.assertTrue(audit_path.exists())
            audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertIn(audit_payload.get("status"), {"APPROVED", "REJECTED"})
            self.assertTrue((project_path / "docs" / "final.md").exists())


if __name__ == "__main__":
    unittest.main()
