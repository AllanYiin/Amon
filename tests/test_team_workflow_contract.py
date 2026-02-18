import shutil
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
        self.assertIn("pm_log_bootstrap", nodes)
        self.assertEqual(nodes["pm_log_bootstrap"]["output_path"], "docs/ProjectManager.md")

        synthesis_prompt = nodes["synthesis"]["prompt"]
        self.assertIn("# TeamworksGPT", synthesis_prompt)
        self.assertIn("Step0~Step6", synthesis_prompt)

    def test_collect_mnt_data_handover_context_reads_existing_files(self) -> None:
        core = AmonCore()
        project_id = "amon-teamwork-contract-test"
        base = Path("/mnt/data")
        base.mkdir(parents=True, exist_ok=True)
        project_dir = base / project_id
        docs_dir = project_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "TODO.md").write_text("- [ ] 任務A", encoding="utf-8")
        (project_dir / "ProjectManager.md").write_text("決策：先做驗證", encoding="utf-8")
        (docs_dir / "final.md").write_text("最終總結", encoding="utf-8")

        try:
            context = core._collect_mnt_data_handover_context(project_id)
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)

        self.assertIn(project_id, context)
        self.assertIn("TODO.md", context)
        self.assertIn("ProjectManager.md", context)


if __name__ == "__main__":
    unittest.main()
