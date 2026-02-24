import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.planning.planner_llm import generate_plan_with_llm


class _MockLLM:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[list[dict[str, str]]] = []

    def generate_stream(self, messages, model=None):  # noqa: ANN001
        _ = model
        self.calls.append(messages)
        if self.outputs:
            return [self.outputs.pop(0)]
        return ["not-json"]


class PlannerLLMTests(unittest.TestCase):
    def test_generate_plan_with_llm_success(self) -> None:
        llm = _MockLLM([
            '{"schema_version":"1.0","objective":"測試","nodes":[{"id":"T1","title":"做事","goal":"完成","definition_of_done":["done"],"depends_on":[],"requires_llm":false,"llm":null,"tools":[],"skills":[],"expected_artifacts":[]}],"edges":[],"context":{"assumptions":[],"constraints":[],"glossary":{}}}',
        ])
        plan = generate_plan_with_llm("請規劃", llm_client=llm)
        self.assertEqual(plan.schema_version, "1.0")
        self.assertEqual(len(plan.nodes), 1)

    def test_generate_plan_with_llm_retry_once(self) -> None:
        llm = _MockLLM([
            "not-json",
            '{"schema_version":"1.0","objective":"測試","nodes":[{"id":"T1","title":"做事","goal":"完成","definition_of_done":["done"],"depends_on":[],"requires_llm":false,"llm":null,"tools":[],"skills":[],"expected_artifacts":[]}],"edges":[],"context":{"assumptions":[],"constraints":[],"glossary":{}}}',
        ])
        plan = generate_plan_with_llm("請規劃", llm_client=llm)
        self.assertEqual(plan.objective, "測試")

    def test_generate_plan_with_llm_fallback_minimal(self) -> None:
        llm = _MockLLM(["not-json", "still-not-json"])
        plan = generate_plan_with_llm("請規劃", llm_client=llm)
        self.assertEqual(plan.schema_version, "1.0")
        self.assertEqual(plan.nodes[0].id, "T1")

    def test_generate_plan_with_llm_payload_contains_simplified_tools_skills(self) -> None:
        llm = _MockLLM([
            '{"schema_version":"1.0","objective":"測試","nodes":[{"id":"T1","title":"做事","goal":"完成","definition_of_done":["done"],"depends_on":[],"requires_llm":false,"llm":null,"tools":[],"skills":[],"expected_artifacts":[]}],"edges":[],"context":{"assumptions":[],"constraints":[],"glossary":{}}}',
        ])
        generate_plan_with_llm(
            "請規劃",
            llm_client=llm,
            available_tools=[{"tool_name": "web.search", "when_to_use": "查詢", "args_schema_hint": {"query": "x"}}],
            available_skills=[{"name": "spec-to-tasks", "description": "拆解規格", "targets": ["planning"]}],
        )
        payload = llm.calls[0][1]["content"]
        self.assertIn('"available_tools"', payload)
        self.assertIn('"input_schema"', payload)
        self.assertIn('"available_skills"', payload)
        self.assertIn('"inject_to"', payload)


if __name__ == "__main__":
    unittest.main()
