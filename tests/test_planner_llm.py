import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_generate_plan_with_llm_fallback_emits_observability_event(self) -> None:
        llm = _MockLLM(["not-json", "still-not-json"])
        with patch("amon.planning.planner_llm.log_event") as mock_log_event, patch("amon.planning.planner_llm.emit_event") as mock_emit_event:
            generate_plan_with_llm(
                "請規劃",
                llm_client=llm,
                project_id="project-123",
                run_id="run-123",
                thread_id="thread-123",
            )

        self.assertTrue(any(call.args[0].get("event") == "planner_fallback_minimal_plan" for call in mock_log_event.call_args_list))
        self.assertTrue(any(call.args[0].get("type") == "planner_fallback_minimal_plan" for call in mock_emit_event.call_args_list))

    def test_generate_plan_with_llm_keeps_repairable_semantic_issues_for_postprocess(self) -> None:
        llm = _MockLLM([
            "```json\n"
            '{"graphId":"graph-2","name":"規劃圖","version":"taskgraph.v3","createdAt":"2026-03-16T00:00:00Z","createdBy":"planner","nodes":[{"id":"concept_alignment","type":"TASK","title":"概念對齊","objective":"查關鍵概念","definitionOfDone":["完成概念摘要","整理風險"],"skillBindings":[{"skillId":"concept-alignment","role":"PRIMARY","config":{"tools":["web.search"]}}],"execution":{"mode":"SINGLE"}},{"id":"requirements","type":"TASK","title":"需求規格","objective":"整理需求","definitionOfDone":["完成需求","完成規格"],"execution":{"mode":"SINGLE"}},{"id":"architecture","type":"TASK","title":"架構設計","objective":"整理架構","definitionOfDone":["完成架構","完成限制"],"execution":{"mode":"SINGLE"}},{"id":"visual","type":"TASK","title":"視覺規格","objective":"整理視覺","definitionOfDone":["完成視覺","完成風格"],"execution":{"mode":"SINGLE"}},{"id":"artifact-task-1-todo","type":"ARTIFACT","title":"docs/TODO.md","artifact":{"artifactId":"artifact-task-1-todo","name":"TODO","kind":"document"}}],"edges":[{"id":"edge-1","type":"DATA","from":"visual","to":"artifact-task-1-todo","dataKind":"PRODUCES"}]}\n'
            "```\n"
            "```mermaid\n"
            "flowchart TD\n"
            "  concept_alignment --> requirements --> architecture --> visual --> artifact_task_1_todo\n"
            "```",
        ])

        plan = generate_plan_with_llm("請規劃創意遊戲", llm_client=llm)

        self.assertEqual(plan.id, "graph-2")
        self.assertEqual([node.id for node in plan.nodes if isinstance(node, TaskNode)][0], "concept_alignment")

    def test_generate_plan_with_llm_payload_contains_simplified_tools_skills(self) -> None:
        llm = _MockLLM([
            '{"version":"taskgraph.v3","nodes":[{"id":"task-1","node_type":"TASK","title":"做事","taskSpec":{"executor":"agent","agent":{"prompt":"完成","instructions":"執行"},"artifacts":[{"name":"todo","mediaType":"text/markdown","description":"待辦","required":true}],"display":{"label":"做事","summary":"測試","todoHint":"done","tags":[]},"runnable":true}},{"id":"artifact-task-1-todo","node_type":"ARTIFACT","title":"docs/TODO.md"}],"edges":[{"from":"task-1","to":"artifact-task-1-todo","edge_type":"DATA","kind":"EMITS"}]}',
        ])
        generate_plan_with_llm(
            "請規劃",
            llm_client=llm,
            available_tools=[{"tool_name": "web.search", "when_to_use": "查詢", "args_schema_hint": {"query": "x"}}],
            available_skills=[
                {"name": "problem-decomposer", "description": "做問題拆解、issue tree、WBS", "targets": ["planning"]},
                {"name": "frontend-design", "description": "做介面設計", "targets": ["ui"]},
            ],
        )
        payload = llm.calls[0][1]["content"]
        self.assertIn("任務描述：", payload)
        self.assertIn("可用 Skills", payload)
        self.assertIn('"toolId": "web.search"', payload)
        self.assertIn('"skillId": "frontend-design"', payload)
        self.assertNotIn('"skillId": "problem-decomposer"', payload)
        self.assertIn("concept-alignment", payload)
        system_prompt = llm.calls[0][0]["content"]
        self.assertIn("嚴禁輸出任何 agent/persona/assignment", system_prompt)
        self.assertIn("只輸出一段 code block", system_prompt)
        self.assertIn("CONTROL 邊方向固定是「前置節點 -> 依賴它的節點」", system_prompt)
        self.assertIn("DATA/PRODUCES 方向固定是「產生者 -> artifact」", system_prompt)
        self.assertIn("planner 已在圖外完成拆題；graph 內不可再放 TODO / 任務拆解 / task outline / WBS 類節點", system_prompt)
        self.assertIn("TASK 節點總數不得超過 8", system_prompt)
        self.assertIn("好例子：概念對齊 -> 設計定義", system_prompt)
        self.assertIn("根據上下文構成以及執行角色相似程度來切分", system_prompt)
        self.assertIn("執行角色是任務的天然分界", system_prompt)
        self.assertIn("Task 是可由單一主執行者直接完成", system_prompt)
        self.assertIn("Artifact 是被 TASK 產出、引用、審查或交付的資訊", system_prompt)
        self.assertIn("Milestone 是時點或狀態檢查，不是 TaskGraph v3 NodeType", system_prompt)
        self.assertIn("問題拆解 / WBS / issue tree 類 skill 屬於 planner 內部能力", system_prompt)
        self.assertIn("同一設計階段的需求/PRD/系統架構/架構設計/視覺規格/預設參數要合併", payload)
        self.assertIn("僅輸出一段 json code block；不要輸出 Mermaid。", payload)


if __name__ == "__main__":
    unittest.main()
