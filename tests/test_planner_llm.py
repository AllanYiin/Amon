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
            "```json\n"
            '{"graphId":"graph-1","name":"規劃圖","version":"taskgraph.v3","createdAt":"2026-03-16T00:00:00Z","createdBy":"planner","nodes":[{"id":"task-1","type":"TASK","title":"概念對齊","objective":"查關鍵概念","definitionOfDone":["完成概念摘要","整理風險"],"skillBindings":[{"skillId":"concept-alignment","role":"PRIMARY","config":{"tools":["web.search"]}}],"execution":{"mode":"SINGLE"}},{"id":"artifact-task-1-todo","type":"ARTIFACT","title":"docs/TODO.md","artifact":{"artifactId":"artifact-task-1-todo","name":"TODO","kind":"document"}}],"edges":[{"id":"edge-1","type":"DATA","from":"task-1","to":"artifact-task-1-todo","dataKind":"PRODUCES"}]}\n'
            "```\n"
            "```mermaid\n"
            "flowchart TD\n"
            "  task_1[概念對齊] --> artifact_task_1_todo[TODO]\n"
            "```",
        ])
        plan = generate_plan_with_llm("請規劃", llm_client=llm)
        self.assertEqual(plan.version, "taskgraph.v3")
        self.assertEqual(plan.id, "graph-1")
        self.assertEqual(len(plan.nodes), 2)
        task_node = next(node for node in plan.nodes if isinstance(node, TaskNode))
        self.assertEqual(task_node.task_spec.agent.allowed_tools, ["web.search"])
        self.assertEqual(task_node.task_spec.agent.skills, ["concept-alignment"])
        self.assertIn("planner_mermaid", plan.metadata)

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
        self.assertEqual(plan.nodes[0].id, "concept_alignment")
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
        self.assertIn("任務描述：", payload)
        self.assertIn("可用 Skills", payload)
        self.assertIn('"toolId": "web.search"', payload)
        self.assertIn('"skillId": "spec-to-tasks"', payload)
        self.assertIn("concept-alignment", payload)
        system_prompt = llm.calls[0][0]["content"]
        self.assertIn("嚴禁輸出任何 agent/persona/assignment", system_prompt)
        self.assertIn("只輸出兩段 code block", system_prompt)
        self.assertIn("planner 已在圖外完成拆題；graph 內不可再放 TODO / 任務拆解 / task outline / WBS 類節點", system_prompt)
        self.assertIn("TASK 節點總數不得超過 8", system_prompt)
        self.assertIn("同一設計階段的需求/PRD/系統架構/架構設計/視覺規格/預設參數要合併", payload)


if __name__ == "__main__":
    unittest.main()
