import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.domain import (
    AgentProfile,
    AmonManifest,
    ExecutorBinding,
    ManifestProject,
    Project,
    RunRecord,
    TaskDefinition,
    UploadAsset,
    WorkflowDefinition,
    WorkflowNode,
)


class ManifestEntityTests(unittest.TestCase):
    def test_project_soft_delete_and_restore(self) -> None:
        project = Project.create(project_id="project.demo", name="Demo", root_path="/tmp/demo")
        project.soft_delete()
        self.assertEqual(project.status, "trashed")
        project.restore()
        self.assertEqual(project.status, "active")

    def test_task_clone_bumps_version_and_resets_status(self) -> None:
        task = TaskDefinition.create(
            task_id="task.demo",
            title="概念對齊",
            goal="整理關鍵概念",
            required_capabilities=["concept_alignment"],
            status="active",
        )
        cloned = task.clone(new_id="task.demo.v2")
        self.assertEqual(cloned.id, "task.demo.v2")
        self.assertEqual(cloned.version, 2)
        self.assertEqual(cloned.status, "draft")

    def test_executor_binding_keeps_streaming_required(self) -> None:
        executor = ExecutorBinding.create(
            executor_id="exec.research",
            executor_type="llm",
            agent_profile_ref="agent.researcher",
            tool_policy_ref="policy.readonly",
            status="active",
        )
        self.assertTrue(executor.streaming_required)

    def test_manifest_roundtrip_and_reference_validation(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.concept_alignment": TaskDefinition.create(
                    task_id="task.concept_alignment",
                    title="概念對齊",
                    goal="整理關鍵概念",
                    required_capabilities=["concept_alignment"],
                    status="active",
                )
            },
            agent_profiles={
                "agent.researcher": AgentProfile.create(
                    agent_id="agent.researcher",
                    name="Researcher",
                    purpose="research",
                    system_prompt="你是研究員",
                    status="active",
                )
            },
            executors={
                "exec.researcher": ExecutorBinding.create(
                    executor_id="exec.researcher",
                    executor_type="llm",
                    agent_profile_ref="agent.researcher",
                    status="active",
                )
            },
            workflows={
                "workflow.demo": WorkflowDefinition.create(
                    workflow_id="workflow.demo",
                    name="Demo",
                    nodes=[
                        WorkflowNode(
                            id="concept_alignment",
                            task_ref="task.concept_alignment",
                            executor_ref="exec.researcher",
                            status="valid",
                        )
                    ],
                    status="active",
                )
            },
        )
        manifest.validate_references()
        restored = AmonManifest.from_dict(manifest.to_dict())
        self.assertEqual(restored.version, "amon.manifest.v1")
        self.assertIn("workflow.demo", restored.workflows)

    def test_run_record_and_upload_asset_roundtrip(self) -> None:
        run = RunRecord.create(
            run_id="run-001",
            workflow_ref="workflow.demo",
            snapshot_refs={"manifest": "snapshot.manifest.json"},
            status="queued",
        )
        upload = UploadAsset.create(
            asset_id="asset-001",
            source_path="/tmp/input.txt",
            media_type="text/plain",
            size_bytes=32,
        )
        self.assertEqual(RunRecord.from_dict(run.to_dict()).status, "queued")
        self.assertEqual(UploadAsset.from_dict(upload.to_dict()).status, "uploaded")


if __name__ == "__main__":
    unittest.main()
