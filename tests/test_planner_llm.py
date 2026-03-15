import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.planning.planner_llm import generate_plan_with_llm
from amon.taskgraph3.schema import ArtifactNode, TaskNode


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
            '{"version":"taskgraph.v3","nodes":[{"id":"task-1","node_type":"TASK","title":"做事","taskSpec":{"executor":"agent","agent":{"prompt":"完成","instructions":"執行"},"artifacts":[{"name":"todo","mediaType":"text/markdown","description":"待辦","required":true}],"display":{"label":"做事","summary":"完成","todoHint":"done","tags":[]},"runnable":true}},{"id":"artifact-task-1-todo","node_type":"ARTIFACT","title":"docs/TODO.md"}],"edges":[{"from":"task-1","to":"artifact-task-1-todo","edge_type":"DATA","kind":"EMITS"}]}',
        ])
        plan = generate_plan_with_llm("請規劃", llm_client=llm)
        self.assertEqual(plan.version, "taskgraph.v3")
        self.assertEqual(len(plan.nodes), 2)

    def test_generate_plan_with_llm_retry_once(self) -> None:
        llm = _MockLLM([
            "not-json",
            '{"version":"taskgraph.v3","nodes":[{"id":"task-1","node_type":"TASK","title":"做事","taskSpec":{"executor":"agent","agent":{"prompt":"完成","instructions":"執行"},"artifacts":[{"name":"todo","mediaType":"text/markdown","description":"待辦","required":true}],"display":{"label":"做事","summary":"測試","todoHint":"done","tags":[]},"runnable":true}},{"id":"artifact-task-1-todo","node_type":"ARTIFACT","title":"docs/TODO.md"}],"edges":[{"from":"task-1","to":"artifact-task-1-todo","edge_type":"DATA","kind":"EMITS"}]}',
        ])
        plan = generate_plan_with_llm("請規劃", llm_client=llm)
        task_node = next(node for node in plan.nodes if isinstance(node, TaskNode))
        self.assertEqual(task_node.task_spec.display.summary, "測試")

    def test_generate_plan_with_llm_fallback_minimal(self) -> None:
        llm = _MockLLM(["not-json", "still-not-json"])
        plan = generate_plan_with_llm("請規劃", llm_client=llm)
        self.assertEqual(plan.version, "taskgraph.v3")
        self.assertEqual(plan.nodes[0].id, "task-1")
        self.assertTrue(any(isinstance(node, ArtifactNode) for node in plan.nodes))

    def test_generate_plan_with_llm_payload_contains_simplified_tools_skills(self) -> None:
        llm = _MockLLM([
            '{"version":"taskgraph.v3","nodes":[{"id":"task-1","node_type":"TASK","title":"做事","taskSpec":{"executor":"agent","agent":{"prompt":"完成","instructions":"執行"},"artifacts":[{"name":"todo","mediaType":"text/markdown","description":"待辦","required":true}],"display":{"label":"做事","summary":"測試","todoHint":"done","tags":[]},"runnable":true}},{"id":"artifact-task-1-todo","node_type":"ARTIFACT","title":"docs/TODO.md"}],"edges":[{"from":"task-1","to":"artifact-task-1-todo","edge_type":"DATA","kind":"EMITS"}]}',
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
        system_prompt = llm.calls[0][0]["content"]
        self.assertIn("只能有一個概念對齊型 TASK", system_prompt)
        self.assertIn("後續 TASK 必須延續前置結果", system_prompt)


if __name__ == "__main__":
    unittest.main()
