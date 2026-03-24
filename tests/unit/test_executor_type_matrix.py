import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AgentProfile, AmonManifest, ExecutorBinding, ManifestProject, TaskDefinition
from amon.planning.capability_registry import CapabilityRegistry


class ExecutorTypeMatrixTests(unittest.TestCase):
    def test_registry_prefers_compilable_llm_over_human_gate_and_ignores_subgraph(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.review": TaskDefinition.create(
                    task_id="task.review",
                    title="Review",
                    goal="Review the plan",
                    required_capabilities=["review"],
                    status="active",
                )
            },
            agent_profiles={
                "agent.reviewer": AgentProfile.create(
                    agent_id="agent.reviewer",
                    name="Reviewer",
                    purpose="review",
                    system_prompt="你是審查者",
                    status="active",
                )
            },
            executors={
                "exec.review.llm": ExecutorBinding.create(
                    executor_id="exec.review.llm",
                    executor_type="llm",
                    capabilities=["review"],
                    agent_profile_ref="agent.reviewer",
                    status="active",
                ),
                "exec.review.human": ExecutorBinding.create(
                    executor_id="exec.review.human",
                    executor_type="human_gate",
                    capabilities=["review"],
                    status="active",
                ),
                "exec.review.subgraph": ExecutorBinding.create(
                    executor_id="exec.review.subgraph",
                    executor_type="subgraph",
                    capabilities=["review"],
                    status="active",
                ),
            },
        )

        resolved = CapabilityRegistry.from_manifest(manifest).resolve_executor(manifest.tasks["task.review"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, "exec.review.llm")

    def test_registry_can_resolve_human_gate_when_it_is_only_supported_candidate(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.approval": TaskDefinition.create(
                    task_id="task.approval",
                    title="Approval",
                    goal="Wait for approval",
                    required_capabilities=["approval_gate"],
                    status="active",
                )
            },
            executors={
                "exec.approval.human": ExecutorBinding.create(
                    executor_id="exec.approval.human",
                    executor_type="human_gate",
                    capabilities=["approval_gate"],
                    status="active",
                ),
                "exec.approval.subgraph": ExecutorBinding.create(
                    executor_id="exec.approval.subgraph",
                    executor_type="subgraph",
                    capabilities=["approval_gate"],
                    status="active",
                ),
            },
        )

        resolved = CapabilityRegistry.from_manifest(manifest).resolve_executor(manifest.tasks["task.approval"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, "exec.approval.human")


if __name__ == "__main__":
    unittest.main()
