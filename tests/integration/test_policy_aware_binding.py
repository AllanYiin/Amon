from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AgentProfile, AmonManifest, ExecutorBinding, ManifestProject, TaskDefinition, ToolPolicy, WorkflowDefinition, WorkflowNode
from amon.planning.binder import BindingError, bind_workflow


class PolicyAwareBindingIntegrationTests(unittest.TestCase):
    def test_binding_prefers_network_enabled_executor(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.web": TaskDefinition.create(
                    task_id="task.web",
                    title="Web task",
                    goal="Search network sources",
                    required_capabilities=["web_research"],
                    side_effect_class="external_network",
                    status="active",
                )
            },
            executors={
                "exec.web.offline": ExecutorBinding.create(
                    executor_id="exec.web.offline",
                    executor_type="tool",
                    capabilities=["web_research"],
                    tool_plan={"tools": [{"name": "web.search", "args": {"q": "x"}}]},
                    tool_policy_ref="policy.offline",
                    status="active",
                ),
                "exec.web.online": ExecutorBinding.create(
                    executor_id="exec.web.online",
                    executor_type="tool",
                    capabilities=["web_research"],
                    tool_plan={"tools": [{"name": "web.search", "args": {"q": "x"}}]},
                    tool_policy_ref="policy.online",
                    status="active",
                ),
            },
            workflows={
                "workflow.demo": WorkflowDefinition.create(
                    workflow_id="workflow.demo",
                    name="Demo",
                    nodes=[WorkflowNode(id="web", task_ref="task.web", executor_ref="", status="draft")],
                    status="draft",
                )
            },
            tool_policies={
                "policy.offline": ToolPolicy.create(
                    policy_id="policy.offline",
                    allowed_tools=["web.search"],
                    allow_network=False,
                    side_effect_ceiling="external_network",
                    status="active",
                ),
                "policy.online": ToolPolicy.create(
                    policy_id="policy.online",
                    allowed_tools=["web.search"],
                    allow_network=True,
                    side_effect_ceiling="external_network",
                    status="active",
                ),
            },
        )

        bound = bind_workflow(manifest, "workflow.demo")

        self.assertEqual(bound.nodes[0].executor_ref, "exec.web.online")

    def test_binding_rejects_explicit_executor_when_policy_is_incompatible(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.research": TaskDefinition.create(
                    task_id="task.research",
                    title="Research",
                    goal="Research online",
                    required_capabilities=["web_research"],
                    side_effect_class="read_only",
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
                "exec.research.denied": ExecutorBinding.create(
                    executor_id="exec.research.denied",
                    executor_type="llm",
                    capabilities=["web_research"],
                    agent_profile_ref="agent.researcher",
                    tool_invocation_mode="delegated",
                    tool_policy_ref="policy.denied",
                    status="active",
                )
            },
            workflows={
                "workflow.demo": WorkflowDefinition.create(
                    workflow_id="workflow.demo",
                    name="Demo",
                    nodes=[WorkflowNode(id="research", task_ref="task.research", executor_ref="exec.research.denied", status="draft")],
                    status="draft",
                )
            },
            tool_policies={
                "policy.denied": ToolPolicy.create(
                    policy_id="policy.denied",
                    allowed_tools=["web.search"],
                    delegated_allowed=False,
                    allow_network=True,
                    side_effect_ceiling="read_only",
                    status="active",
                )
            },
        )

        with self.assertRaises(BindingError) as ctx:
            bind_workflow(manifest, "workflow.demo")

        self.assertEqual(ctx.exception.code, "AMON_BINDER_002")
        self.assertIn("delegated tool invocation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
