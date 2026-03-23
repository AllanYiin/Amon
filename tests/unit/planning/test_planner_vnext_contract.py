import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.planning.planner_vnext import (
    PlannerContractError,
    build_planning_stream_events,
    logical_workflow_from_payload,
    validate_planner_payload,
)


class PlannerVNextContractTests(unittest.TestCase):
    def test_forbidden_assignment_fields_fail_fast(self) -> None:
        payload = {
            "id": "workflow.demo",
            "tasks": [
                {
                    "id": "task-1",
                    "goal": "整理概念",
                    "required_capabilities": ["concept_alignment"],
                    "agent": {"id": "agent.researcher"},
                }
            ],
        }

        with self.assertRaisesRegex(PlannerContractError, "forbidden field"):
            validate_planner_payload(payload)

    def test_logical_workflow_roundtrip(self) -> None:
        workflow = logical_workflow_from_payload(
            {
                "id": "workflow.demo",
                "name": "Demo",
                "tasks": [
                    {
                        "id": "concept_alignment",
                        "title": "概念對齊",
                        "goal": "整理關鍵名詞",
                        "required_capabilities": ["concept_alignment", "web_research"],
                        "acceptance_criteria": ["列出定義", "標示風險"],
                        "depends_on": [],
                    },
                    {
                        "id": "spec_write",
                        "goal": "整理技術規格",
                        "required_capabilities": ["spec_writing"],
                        "acceptance_criteria": ["輸出 markdown"],
                        "depends_on": ["concept_alignment"],
                    },
                ],
            }
        )

        self.assertEqual(workflow.id, "workflow.demo")
        self.assertEqual(workflow.tasks[1].depends_on, ["concept_alignment"])
        self.assertEqual(workflow.tasks[0].required_capabilities, ["concept_alignment", "web_research"])

    def test_planning_stream_events_emit_incremental_chunks(self) -> None:
        events = build_planning_stream_events(["規劃", "中"], run_id="run-001")
        self.assertEqual(events[0].event, "node.chunk")
        self.assertEqual(events[0].payload["chunk_index"], 0)
        self.assertEqual(events[-1].event, "plan_generated")
        self.assertEqual(events[-1].payload["chunk_count"], 2)


if __name__ == "__main__":
    unittest.main()
