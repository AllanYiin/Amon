import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.application import UIStateService
from amon.domain import Project, RunRecord
from amon.runtime_vnext import CheckpointStore, ConfirmationQueue, ResumeService
from amon.storage import ProjectRepository, RunRepository


class RunResumeIntegrationTests(unittest.TestCase):
    def test_resume_service_restores_checkpoint_confirmations_and_ui_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            project_repo = ProjectRepository(project_root)
            project_repo.create(Project.create(project_id="project.demo", name="Demo", root_path=str(project_root)))
            run_repo = RunRepository(project_root)
            run_repo.create(
                RunRecord.create(run_id="run-001", workflow_ref="workflow.demo", status="waiting_confirmation"),
                snapshot_manifest={"version": "amon.manifest.v1"},
                compiled_graph={"version": "taskgraph.v3", "id": "workflow.demo"},
            )

            CheckpointStore(project_root).write("run-001", phase="running", node_id="n1", status="running", payload={"offset": 3})
            ConfirmationQueue(project_root).enqueue(
                "run-001",
                tool_name="filesystem.write",
                reason="需要確認",
                preview={"path": "workspace/out.txt"},
                confirmation_id="confirm-001",
            )
            ui_state = UIStateService(project_root)
            ui_state.update_recent_run("run-001")
            ui_state.update_recent_preview("asset-001")
            ui_state.update_pending_confirmations(["confirm-001"])

            resume_service = ResumeService(project_root)
            project_resume = resume_service.load_project_resume()
            run_resume = resume_service.restore_run("run-001")

            self.assertEqual(project_resume.ui_state["recent_run_id"], "run-001")
            self.assertEqual(project_resume.ui_state["recent_preview_id"], "asset-001")
            self.assertEqual(project_resume.ui_state["pending_confirmation_ids"], ["confirm-001"])
            self.assertEqual(len(project_resume.resumable_runs), 1)
            self.assertEqual(run_resume.checkpoint["node_id"], "n1")
            self.assertEqual(run_resume.confirmations[0]["id"], "confirm-001")
            self.assertEqual(run_resume.snapshot_manifest["version"], "amon.manifest.v1")
            self.assertEqual(run_resume.compiled_graph["version"], "taskgraph.v3")


if __name__ == "__main__":
    unittest.main()
