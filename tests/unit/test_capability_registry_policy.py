import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AgentProfile, AmonManifest, ExecutorBinding, ManifestProject, TaskDefinition, ToolPolicy
from amon.planning.capability_registry import CapabilityRegistry


class CapabilityRegistryPolicyTests(unittest.TestCase):
    def test_external_network_task_selects_network_enabled_executor(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.web": TaskDefinition.create(
                    task_id="task.web",
                    title="Web search",
                    goal="Search the web",
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

        resolved = CapabilityRegistry.from_manifest(manifest).resolve_executor(manifest.tasks["task.web"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, "exec.web.online")

    def test_delegated_disallowed_executor_is_filtered_out(self) -> None:
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
                "exec.llm.denied": ExecutorBinding.create(
                    executor_id="exec.llm.denied",
                    executor_type="llm",
                    capabilities=["web_research"],
                    agent_profile_ref="agent.researcher",
                    tool_invocation_mode="delegated",
                    tool_policy_ref="policy.denied",
                    status="active",
                ),
                "exec.llm.allowed": ExecutorBinding.create(
                    executor_id="exec.llm.allowed",
                    executor_type="llm",
                    capabilities=["web_research"],
                    agent_profile_ref="agent.researcher",
                    tool_invocation_mode="delegated",
                    tool_policy_ref="policy.allowed",
                    status="active",
                ),
            },
            tool_policies={
                "policy.denied": ToolPolicy.create(
                    policy_id="policy.denied",
                    allowed_tools=["web.search"],
                    delegated_allowed=False,
                    allow_network=True,
                    side_effect_ceiling="read_only",
                    status="active",
                ),
                "policy.allowed": ToolPolicy.create(
                    policy_id="policy.allowed",
                    allowed_tools=["web.search"],
                    delegated_allowed=True,
                    allow_network=True,
                    side_effect_ceiling="read_only",
                    status="active",
                ),
            },
        )

        resolved = CapabilityRegistry.from_manifest(manifest).resolve_executor(manifest.tasks["task.research"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, "exec.llm.allowed")

    def test_read_only_task_still_prefers_llm_when_policy_is_compatible(self) -> None:
        manifest = AmonManifest(
            project=ManifestProject(id="project.demo", name="Demo"),
            tasks={
                "task.summary": TaskDefinition.create(
                    task_id="task.summary",
                    title="Summary",
                    goal="Summarize findings",
                    required_capabilities=["summarization"],
                    side_effect_class="read_only",
                    status="active",
                )
            },
            agent_profiles={
                "agent.summarizer": AgentProfile.create(
                    agent_id="agent.summarizer",
                    name="Summarizer",
                    purpose="summary",
                    system_prompt="你是摘要專家",
                    status="active",
                )
            },
            executors={
                "exec.summary.llm": ExecutorBinding.create(
                    executor_id="exec.summary.llm",
                    executor_type="llm",
                    capabilities=["summarization"],
                    agent_profile_ref="agent.summarizer",
                    status="active",
                ),
                "exec.summary.tool": ExecutorBinding.create(
                    executor_id="exec.summary.tool",
                    executor_type="tool",
                    capabilities=["summarization"],
                    tool_plan={"tools": [{"name": "memory.search", "args": {"query": "x"}}]},
                    tool_policy_ref="policy.tool",
                    status="active",
                ),
            },
            tool_policies={
                "policy.tool": ToolPolicy.create(
                    policy_id="policy.tool",
                    allowed_tools=["memory.search"],
                    side_effect_ceiling="read_only",
                    status="active",
                )
            },
        )

        resolved = CapabilityRegistry.from_manifest(manifest).resolve_executor(manifest.tasks["task.summary"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, "exec.summary.llm")


if __name__ == "__main__":
    unittest.main()
