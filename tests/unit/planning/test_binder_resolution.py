import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.domain import AgentProfile, AmonManifest, ExecutorBinding, ManifestProject, TaskDefinition, WorkflowDefinition, WorkflowNode
from amon.planning.binder import BindingError, bind_workflow


class BinderResolutionTests(unittest.TestCase):
    def test_bind_workflow_resolves_executor_from_capabilities(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.research": TaskDefinition.create(
                    task_id="task.research",
                    title="研究",
                    goal="查資料",
                    required_capabilities=["web_research"],
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
                "exec.research": ExecutorBinding.create(
                    executor_id="exec.research",
                    executor_type="llm",
                    capabilities=["web_research", "concept_alignment"],
                    agent_profile_ref="agent.researcher",
                    status="active",
                )
            },
            workflows={
                "workflow.demo": WorkflowDefinition.create(
                    workflow_id="workflow.demo",
                    name="Demo",
                    nodes=[WorkflowNode(id="research", task_ref="task.research", executor_ref="", status="draft")],
                    status="draft",
                )
            },
        )

        bound = bind_workflow(manifest, "workflow.demo")

        self.assertEqual(bound.nodes[0].executor_ref, "exec.research")
        self.assertEqual(bound.nodes[0].status, "valid")

    def test_bind_workflow_fails_when_no_executor_matches(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.research": TaskDefinition.create(
                    task_id="task.research",
                    title="研究",
                    goal="查資料",
                    required_capabilities=["web_research"],
                    status="active",
                )
            },
            executors={
                "exec.writer": ExecutorBinding.create(
                    executor_id="exec.writer",
                    executor_type="llm",
                    capabilities=["spec_writing"],
                    status="active",
                )
            },
            workflows={
                "workflow.demo": WorkflowDefinition.create(
                    workflow_id="workflow.demo",
                    name="Demo",
                    nodes=[WorkflowNode(id="research", task_ref="task.research", executor_ref="", status="draft")],
                    status="draft",
                )
            },
        )

        with self.assertRaisesRegex(BindingError, "no eligible executor"):
            bind_workflow(manifest, "workflow.demo")


if __name__ == "__main__":
    unittest.main()
