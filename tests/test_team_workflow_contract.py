import shutil
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class TeamWorkflowContractTests(unittest.TestCase):
    def test_team_graph_contains_required_contract_nodes(self) -> None:
        core = AmonCore()
        graph = core._build_team_graph()
        nodes = {node["id"]: node for node in graph.get("nodes", [])}

        self.assertIn("pm_todo", nodes)
        self.assertEqual(nodes["pm_todo"]["output_path"], "docs/TODO.md")
        self.assertIn("專案經理：", nodes["pm_todo"]["prompt"])
        self.assertIn("pm_log_bootstrap", nodes)
        self.assertEqual(nodes["pm_log_bootstrap"]["output_path"], "docs/ProjectManager.md")
        task_map = nodes["tasks_map"]
        sub_nodes = {node["id"]: node for node in task_map["subgraph"]["nodes"]}
        self.assertIn("role_factory_request", sub_nodes)
        self.assertEqual(sub_nodes["role_factory_request"]["output_path"], "docs/tasks/${task_task_id}/role_factory.md")
        self.assertIn("角色工廠：人設為", sub_nodes["role_factory_request"]["prompt"])
        self.assertIn("專案成員（${task_role}）：", sub_nodes["member_plan"]["prompt"])

        self.assertIn("audit_committee_role_factory", nodes)
        self.assertEqual(nodes["audit_committee_role_factory"]["output_path"], "docs/audits/committee_roles.md")
        self.assertIn("audit_committee_gate", nodes)
        self.assertEqual(nodes["audit_committee_gate"]["output_path"], "docs/audits/committee_decision.md")
        self.assertIn("稽核會：", nodes["audit_committee_gate"]["prompt"])
        self.assertIn("final_rework_notice", nodes)
        self.assertIn("專案經理：任務分派為補強", nodes["final_rework_notice"]["prompt"])

        synthesis_prompt = nodes["synthesis"]["prompt"]
        self.assertIn("# TeamworksGPT", synthesis_prompt)
        self.assertIn("Step0~Step6", synthesis_prompt)
        self.assertIn("稽核會全員通過", synthesis_prompt)

    def test_collect_mnt_data_handover_context_reads_project_docs_files(self) -> None:
        core = AmonCore()
        project_dir = Path(tempfile.mkdtemp(prefix="amon-teamwork-contract-test-"))
        docs_dir = project_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "TODO.md").write_text("- [ ] 任務A", encoding="utf-8")
        (docs_dir / "ProjectManager.md").write_text("決策：先做驗證", encoding="utf-8")
        (docs_dir / "final.md").write_text("最終總結", encoding="utf-8")

        try:
            context = core._collect_mnt_data_handover_context(project_dir)
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)

        self.assertIn(project_dir.name, context)
        self.assertIn("TODO.md", context)
        self.assertIn("ProjectManager.md", context)


if __name__ == "__main__":
    unittest.main()
