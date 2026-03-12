import json
import shutil
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class LegacyGraphRuntimeTests(unittest.TestCase):
    def test_run_single_legacy_graph_writes_primary_output(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="amon-legacy-single-"))
        try:
            project_path = root / "project"
            project_path.mkdir(parents=True, exist_ok=True)
            core = AmonCore(data_dir=root / "amon-home")
            core.run_agent_task = lambda prompt, **kwargs: "單節點輸出"  # type: ignore[method-assign]

            result = core.run_single("測試 single", project_path=project_path)

            self.assertEqual(result, "單節點輸出")
            docs_dir = project_path / "docs"
            outputs = list(docs_dir.glob("single_*.md"))
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0].read_text(encoding="utf-8"), "單節點輸出")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_run_team_legacy_map_graph_completes(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="amon-legacy-team-"))
        try:
            core = AmonCore(data_dir=root / "amon-home")
            core.initialize()
            project = core.create_project("測試專案")
            project_path = Path(project.path)

            def fake_run_agent_task(prompt, **kwargs):
                node_id = kwargs.get("node_id")
                outputs = {
                    "pm_todo": "專案經理：\n- [ ] Step0：檢查 docs",
                    "pm_log_bootstrap": "專案經理：啟動紀錄",
                    "pm_plan": json.dumps(
                        {
                            "tasks": [
                                {
                                    "task_id": "T1",
                                    "title": "任務一",
                                    "role": "分析師",
                                    "description": "完成分析",
                                    "role_assignment_reason": "需要分析能力",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    "role_factory_request": "角色工廠：人設為...\n{\"name\":\"Alice\",\"role\":\"分析師\"}",
                    "member_plan": "專案成員（分析師）：\n觀察：...\n判斷理由：...\n資料來源引述：...\n成果與評估指標：...",
                    "member_execute": "結果：已完成分析並提供可驗證成果。",
                    "audit": "APPROVED",
                    "audit_committee_role_factory": "角色工廠：人設為...\n{\"committee\":[{\"name\":\"Q\",\"role\":\"品質\"}]}",
                    "audit_committee_gate": "{\"status\":\"APPROVED_ALL\",\"reason\":\"ok\",\"actions\":[]}",
                    "synthesis": (
                        "# TeamworksGPT\n"
                        "## 我務必依照以下的【角色定義】 以及【工作流程】來完成任務\n"
                        "已遵守 Step0~Step6，且稽核會全員通過。"
                    ),
                    "final_rework_notice": "專案經理：任務分派為補強",
                }
                if node_id not in outputs:
                    raise AssertionError(f"unexpected node_id={node_id}\nprompt={prompt}")
                return outputs[node_id]

            core.run_agent_task = fake_run_agent_task  # type: ignore[method-assign]

            final_text = core.run_team("請完成測試流程", project_path=project_path)

            self.assertIn("# TeamworksGPT", final_text)
            self.assertTrue((project_path / "docs" / "tasks" / "T1" / "persona.json").exists())
            self.assertTrue((project_path / "docs" / "tasks" / "T1" / "result.md").exists())
            self.assertTrue((project_path / "docs" / "audits" / "T1.json").exists())
            tasks_payload = json.loads((project_path / "tasks" / "tasks.json").read_text(encoding="utf-8"))
            self.assertEqual(tasks_payload["tasks"][0]["task_id"], "T1")
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
