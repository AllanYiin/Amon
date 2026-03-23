import importlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.domain import Project, RunRecord, TaskDefinition, UploadAsset
from amon.storage import DefinitionRepository, ProjectRepository, RunRepository, UploadRepository


class RepositoryTests(unittest.TestCase):
    def test_migration_bootstrap_creates_manifest_layout(self) -> None:
        module = importlib.import_module("amon.storage.migrations.0001_manifest_v1")
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            project = Project.create(project_id="project.demo", name="Demo", root_path=str(project_root))
            layout = module.bootstrap_manifest_storage(project_root, project=project)
            self.assertTrue((project_root / ".amon" / "definitions" / "tasks").exists())
            self.assertTrue((project_root / ".amon" / "uploads" / "metadata").exists())
            self.assertTrue(layout["project_file"].exists())

    def test_project_repository_persists_project_and_ui_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            repo = ProjectRepository(project_root)
            project = Project.create(project_id="project.demo", name="Demo", root_path=str(project_root))
            repo.create(project)
            repo.update(name="Demo 2")
            repo.save_ui_state({"recent_project_id": "project.demo", "recent_run_id": "run-001"})
            loaded = repo.load()
            self.assertEqual(loaded.name, "Demo 2")
            self.assertEqual(repo.load_ui_state()["recent_run_id"], "run-001")
            repo.soft_delete()
            self.assertEqual(repo.load().status, "trashed")
            repo.restore()
            self.assertEqual(repo.load().status, "active")

    def test_definition_repository_handles_soft_delete_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            repo = DefinitionRepository(project_root)
            task = TaskDefinition.create(task_id="task.demo", title="Demo", goal="Goal", status="active")
            repo.save("tasks", task)
            repo.soft_delete("tasks", "task.demo", in_use=True)
            self.assertEqual(repo.get("tasks", "task.demo").status, "deprecated")
            repo.restore("tasks", "task.demo", target_status="active")
            self.assertEqual(repo.get("tasks", "task.demo").status, "active")

    def test_run_repository_persists_snapshot_checkpoint_and_confirmations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            repo = RunRepository(project_root)
            run = RunRecord.create(run_id="run-001", workflow_ref="workflow.demo", status="running")
            repo.create(run, snapshot_manifest={"version": "amon.manifest.v1"}, compiled_graph={"version": "taskgraph.v3"})
            repo.save_checkpoint_metadata("run-001", "cp-001", {"node_id": "n1", "status": "running"})
            repo.enqueue_confirmation("run-001", "confirm-001", {"id": "confirm-001", "action": "approve"})
            self.assertEqual(repo.load_snapshot_manifest("run-001")["version"], "amon.manifest.v1")
            self.assertEqual(repo.load_checkpoint_metadata("run-001")["node_id"], "n1")
            self.assertEqual(repo.load_pending_confirmations("run-001")[0]["id"], "confirm-001")
            self.assertEqual(repo.list_resumable_runs()[0].id, "run-001")

    def test_upload_repository_copies_source_and_preview_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            source_path = Path(tmp) / "input.txt"
            source_path.write_text("hello", encoding="utf-8")
            repo = UploadRepository(project_root)
            asset = UploadAsset.create(
                asset_id="asset-001",
                source_path=str(source_path),
                media_type="text/plain",
                size_bytes=source_path.stat().st_size,
            )
            repo.create(asset)
            stored = repo.save_preview("asset-001", "asset-001.txt", "preview")
            self.assertTrue(Path(stored.source_path).exists())
            self.assertTrue(Path(stored.preview_ref or "").exists())
            self.assertEqual(repo.get("asset-001").status, "preview_ready")


if __name__ == "__main__":
    unittest.main()
