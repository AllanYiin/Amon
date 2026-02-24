import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.planning.planner_llm import generate_plan_with_llm


class _MockLLM:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)

    def generate_stream(self, messages, model=None):  # noqa: ANN001
        _ = (messages, model)
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


if __name__ == "__main__":
    unittest.main()
