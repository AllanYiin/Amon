import shutil
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.graph_presets import TEAM_ROLE_PROTOTYPES


class TeamWorkflowContractTests(unittest.TestCase):
    def test_team_graph_contains_required_v3_nodes_and_prompts(self) -> None:
        core = AmonCore()
        graph = core._build_team_graph()
        nodes = {node["id"]: node for node in graph.get("nodes", [])}

        self.assertIn("write_role_prototypes", nodes)
        tool_call = nodes["write_role_prototypes"]["taskSpec"]["tool"]["tools"][0]
        self.assertEqual(tool_call["name"], "artifacts.write_text")
        self.assertEqual(tool_call["args"]["path"], "docs/roles/team_role_prototypes.json")

        self.assertIn("pm_todo", nodes)
        self.assertEqual(nodes["pm_todo"]["node_type"], "TASK")
        self.assertIn("專案經理：", nodes["pm_todo"]["taskSpec"]["agent"]["prompt"])
        self.assertIn("systemPrompt", nodes["pm_todo"]["taskSpec"]["agent"])
        self.assertIn("pm_log_bootstrap", nodes)
        self.assertEqual(nodes["write_pm_log"]["taskSpec"]["tool"]["tools"][0]["args"]["path"], "docs/ProjectManager.md")

        task_map = nodes["task_teamwork_map"]
        self.assertEqual(task_map["execution"], "PARALLEL_MAP")
        self.assertEqual(
            task_map["executionConfig"]["itemsFrom"]["fromNode"],
            "pm_plan",
        )
        self.assertEqual(task_map["executionConfig"]["itemsFrom"]["port"], "raw")
        self.assertEqual(task_map["executionConfig"]["itemsFrom"]["jsonPath"], "tasks")
        self.assertIn("Role Factory", task_map["taskSpec"]["agent"]["prompt"])
        self.assertIn("systemPrompt", task_map["taskSpec"]["agent"])
        self.assertEqual(
            nodes["materialize_task_artifacts"]["taskSpec"]["tool"]["tools"][0]["args"]["path"],
            "docs/tasks/${map_item_task_id}/persona.json",
        )

        self.assertIn("audit_committee_role_factory", nodes)
        self.assertEqual(
            nodes["write_committee_roles"]["taskSpec"]["tool"]["tools"][0]["args"]["path"],
            "docs/audits/committee_roles.json",
        )
        self.assertIn("audit_committee_gate", nodes)
        self.assertEqual(
            nodes["write_committee_decision"]["taskSpec"]["tool"]["tools"][0]["args"]["path"],
            "docs/audits/committee_decision.json",
        )
        self.assertIn("稽核會", nodes["audit_committee_gate"]["taskSpec"]["agent"]["prompt"])

        synthesis_prompt = nodes["synthesis"]["taskSpec"]["agent"]["prompt"]
        self.assertIn("# TeamworksGPT", synthesis_prompt)
        self.assertIn("Step0~Step6", synthesis_prompt)
        self.assertIn("專案經理：任務分派為補強", synthesis_prompt)
        self.assertEqual(nodes["write_final"]["taskSpec"]["tool"]["tools"][0]["args"]["path"], "docs/final.md")

    def test_team_role_prototypes_cover_key_roles(self) -> None:
        roles = {entry["role"] for entry in TEAM_ROLE_PROTOTYPES}
        self.assertIn("首席產品策略師", roles)
        self.assertIn("系統架構師", roles)
        self.assertIn("研究分析師", roles)
        self.assertIn("全端實作工程師", roles)
        self.assertIn("風險與品質稽核師", roles)

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
