import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import Project, RunRecord
from amon.storage import ProjectRepository, RunRepository


class ProjectResumeStorageIntegrationTests(unittest.TestCase):
    def test_project_reopen_restores_ui_state_and_unfinished_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            project_repo = ProjectRepository(project_root)
            project_repo.create(Project.create(project_id="project.demo", name="Demo", root_path=str(project_root)))
            project_repo.save_ui_state(
                {
                    "recent_project_id": "project.demo",
                    "recent_run_id": "run-001",
                    "recent_preview_id": "asset-001",
                    "pending_confirmation_ids": ["confirm-001"],
                }
            )
            run_repo = RunRepository(project_root)
            run_repo.create(
                RunRecord.create(
                    run_id="run-001",
                    workflow_ref="workflow.demo",
                    status="waiting_confirmation",
                    confirmation_queue=["confirm-001"],
                ),
                snapshot_manifest={"version": "amon.manifest.v1"},
            )
            run_repo.save_checkpoint_metadata("run-001", "cp-001", {"phase": "running", "node_id": "n1"})
            run_repo.enqueue_confirmation("run-001", "confirm-001", {"id": "confirm-001", "action": "write_file"})
            reopened = ProjectRepository(project_root).load_resume_snapshot()
            reopened_run_repo = RunRepository(project_root)
            self.assertEqual(reopened.project.id, "project.demo")
            self.assertEqual(reopened.ui_state["recent_run_id"], "run-001")
            self.assertEqual(len(reopened.resumable_runs), 1)
            self.assertEqual(reopened.resumable_runs[0]["status"], "waiting_confirmation")
            self.assertEqual(reopened_run_repo.load_checkpoint_metadata("run-001")["node_id"], "n1")
            self.assertEqual(reopened_run_repo.load_pending_confirmations("run-001")[0]["id"], "confirm-001")


if __name__ == "__main__":
    unittest.main()
