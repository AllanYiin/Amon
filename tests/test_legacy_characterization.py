import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.graph_presets import (
    build_self_critique_graph_payload,
    build_single_graph_payload,
    build_team_graph_payload,
)
from amon.planning.planner_llm import _minimal_plan


class LegacyCharacterizationTests(unittest.TestCase):
    def test_planner_minimal_plan_fallback_shape_is_stable(self) -> None:
        graph = _minimal_plan("整理目前 repo 狀態")

        self.assertEqual(graph.id, "planner-fallback")
        self.assertEqual(graph.version, "taskgraph.v3")
        self.assertEqual(graph.name, "Fallback Planner Graph")
        self.assertEqual([node.id for node in graph.nodes], ["concept_alignment", "task-1"])
        self.assertEqual(len(graph.edges), 1)
        self.assertEqual(graph.edges[0].from_node, "concept_alignment")
        self.assertEqual(graph.edges[0].to_node, "task-1")
        self.assertEqual(graph.edges[0].edge_type, "CONTROL")
        self.assertEqual(graph.edges[0].kind, "DEPENDS_ON")

        concept_alignment = graph.nodes[0]
        self.assertEqual(concept_alignment.task_spec.executor, "agent")
        self.assertIn("任務：整理目前 repo 狀態", concept_alignment.task_spec.agent.prompt)
        self.assertEqual(concept_alignment.task_spec.agent.skills, ["concept-alignment"])
        self.assertEqual(concept_alignment.task_spec.artifacts[0].name, "concept_summary")
        self.assertIn("fallback", concept_alignment.task_spec.display.tags)

        execution = graph.nodes[1]
        self.assertEqual(execution.task_spec.executor, "agent")
        self.assertEqual(execution.task_spec.agent.prompt, "整理目前 repo 狀態")
        self.assertEqual(execution.task_spec.artifacts[0].name, "todo")
        self.assertIn("fallback", execution.task_spec.display.tags)

    def test_core_graph_builder_compatibility_adapters_remain_delegating(self) -> None:
        core = AmonCore()

        self.assertEqual(core._build_single_graph(), build_single_graph_payload())
        self.assertEqual(core._build_self_critique_graph(), build_self_critique_graph_payload())
        self.assertEqual(core._build_team_graph(), build_team_graph_payload())


if __name__ == "__main__":
    unittest.main()
