import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.planning.planner_llm import generate_plan_with_llm, semantic_plan_issues
from amon.taskgraph3.payloads import AgentTaskConfig, TaskDisplayMetadata, TaskSpec
from amon.taskgraph3.schema import GraphDefinition, TaskNode


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
    def test_semantic_plan_issues_requires_concept_dual_skill_and_frontend_stage(self) -> None:
        graph = GraphDefinition(
            version="taskgraph.v3",
            nodes=[
                TaskNode(
                    id="concept_alignment",
                    title="概念對齊",
                    task_spec=TaskSpec(
                        executor="agent",
                        agent=AgentTaskConfig(prompt="先查概念", skills=["concept-alignment"]),
                        display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                    ),
                ),
                TaskNode(
                    id="spec_organizer",
                    title="規格整理",
                    task_spec=TaskSpec(
                        executor="agent",
                        agent=AgentTaskConfig(prompt="整理規格", skills=["spec-organizer"]),
                        display=TaskDisplayMetadata(label="規格整理", summary="整理規格", todo_hint="完成規格"),
                    ),
                ),
                TaskNode(
                    id="development_implementation",
                    title="開發實作",
                    task_spec=TaskSpec(
                        executor="agent",
                        agent=AgentTaskConfig(prompt="完成實作", skills=["vibe-coding-guidelines"]),
                        display=TaskDisplayMetadata(label="開發實作", summary="完成實作", todo_hint="完成交付"),
                    ),
                ),
            ],
            edges=[],
        )

        issues = semantic_plan_issues(
            graph,
            message="請幫我開發一個內部工具，先修正 UI 與程式流程。",
        )

        self.assertIn("「概念對齊」TASK 必須同時綁定 concept-alignment 與 web-search-strategy。", issues)
        self.assertIn("程式開發任務缺少「前端設計」TASK，必須補上並綁定 frontend-design。", issues)

    def test_generate_plan_with_llm_success(self) -> None:
        llm = _MockLLM([
            "```json\n"
            '{"graphId":"graph-1","name":"規劃圖","version":"taskgraph.v3","createdAt":"2026-03-16T00:00:00Z","createdBy":"planner","nodes":[{"id":"task-1","type":"TASK","title":"概念對齊","objective":"查關鍵概念","definitionOfDone":["完成概念摘要","整理風險"],"skillBindings":[{"skillId":"concept-alignment","role":"PRIMARY","config":{"tools":["web.search"]}},{"skillId":"web-search-strategy","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}},{"id":"artifact-task-1-todo","type":"ARTIFACT","title":"docs/TODO.md","artifact":{"artifactId":"artifact-task-1-todo","name":"TODO","kind":"document"}}],"edges":[{"id":"edge-1","type":"DATA","from":"task-1","to":"artifact-task-1-todo","dataKind":"PRODUCES"}]}\n'
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
        self.assertEqual(task_node.task_spec.agent.skills, ["concept-alignment", "web-search-strategy"])
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
        self.assertTrue(all(isinstance(node, TaskNode) for node in plan.nodes))
        self.assertEqual(plan.nodes[0].task_spec.agent.skills, ["concept-alignment", "web-search-strategy"])

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
            '{"graphId":"graph-2","name":"規劃圖","version":"taskgraph.v3","createdAt":"2026-03-16T00:00:00Z","createdBy":"planner","nodes":[{"id":"concept_alignment","type":"TASK","title":"概念對齊","objective":"查關鍵概念","definitionOfDone":["完成概念摘要","整理風險"],"skillBindings":[{"skillId":"concept-alignment","role":"PRIMARY","config":{"tools":["web.search"]}},{"skillId":"web-search-strategy","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}},{"id":"requirements","type":"TASK","title":"需求規格","objective":"整理需求","definitionOfDone":["完成需求","完成規格"],"execution":{"mode":"SINGLE"}},{"id":"architecture","type":"TASK","title":"架構設計","objective":"整理架構","definitionOfDone":["完成架構","完成限制"],"execution":{"mode":"SINGLE"}},{"id":"visual","type":"TASK","title":"視覺規格","objective":"整理視覺","definitionOfDone":["完成視覺","完成風格"],"execution":{"mode":"SINGLE"}},{"id":"artifact-task-1-todo","type":"ARTIFACT","title":"docs/TODO.md","artifact":{"artifactId":"artifact-task-1-todo","name":"TODO","kind":"document"}}],"edges":[{"id":"edge-1","type":"DATA","from":"visual","to":"artifact-task-1-todo","dataKind":"PRODUCES"}]}\n'
            "```\n"
            "```mermaid\n"
            "flowchart TD\n"
            "  concept_alignment --> requirements --> architecture --> visual --> artifact_task_1_todo\n"
            "```",
        ])

        plan = generate_plan_with_llm("請規劃創意遊戲", llm_client=llm)

        self.assertEqual(plan.id, "graph-2")
        self.assertEqual([node.id for node in plan.nodes if isinstance(node, TaskNode)][0], "concept_alignment")

    def test_generate_plan_with_llm_repairs_repairable_semantic_issues(self) -> None:
        llm = _MockLLM([
            "```json\n"
            '{"graphId":"graph-2","name":"規劃圖","version":"taskgraph.v3","createdAt":"2026-03-16T00:00:00Z","createdBy":"planner","nodes":[{"id":"concept_alignment","type":"TASK","title":"概念對齊","objective":"查關鍵概念","definitionOfDone":["完成概念摘要","整理風險"],"skillBindings":[{"skillId":"concept-alignment","role":"PRIMARY","config":{"tools":["web.search"]}},{"skillId":"web-search-strategy","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}},{"id":"requirements","type":"TASK","title":"需求規格","objective":"整理需求","definitionOfDone":["完成需求","完成規格"],"execution":{"mode":"SINGLE"}},{"id":"architecture","type":"TASK","title":"架構設計","objective":"整理架構","definitionOfDone":["完成架構","完成限制"],"execution":{"mode":"SINGLE"}},{"id":"visual","type":"TASK","title":"視覺規格","objective":"整理視覺","definitionOfDone":["完成視覺","完成風格"],"execution":{"mode":"SINGLE"}}],"edges":[{"id":"edge-1","type":"CONTROL","from":"concept_alignment","to":"requirements","kind":"DEPENDS_ON"},{"id":"edge-2","type":"CONTROL","from":"requirements","to":"architecture","kind":"DEPENDS_ON"},{"id":"edge-3","type":"CONTROL","from":"architecture","to":"visual","kind":"DEPENDS_ON"}]}\n'
            "```\n",
            "```json\n"
            '{"graphId":"graph-2-repaired","name":"規劃圖","version":"taskgraph.v3","createdAt":"2026-03-16T00:00:00Z","createdBy":"planner","nodes":[{"id":"concept_alignment","type":"TASK","title":"概念對齊","objective":"查關鍵概念","definitionOfDone":["完成概念摘要","整理風險"],"skillBindings":[{"skillId":"concept-alignment","role":"PRIMARY","config":{"tools":["web.search"]}},{"skillId":"web-search-strategy","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}},{"id":"spec_organizer","type":"TASK","title":"規格整理","objective":"整理需求與架構規格","definitionOfDone":["完成需求規格","完成架構說明"],"skillBindings":[{"skillId":"spec-organizer","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}},{"id":"frontend_design","type":"TASK","title":"前端設計","objective":"整理 UI 與視覺方向","definitionOfDone":["完成流程","完成視覺規則"],"skillBindings":[{"skillId":"frontend-design","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}},{"id":"development_implementation","type":"TASK","title":"開發實作","objective":"完成程式實作","definitionOfDone":["完成開發","完成測試重點"],"skillBindings":[{"skillId":"vibe-coding-guidelines","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}}],"edges":[{"id":"edge-1","type":"CONTROL","from":"concept_alignment","to":"spec_organizer","kind":"DEPENDS_ON"},{"id":"edge-2","type":"CONTROL","from":"spec_organizer","to":"frontend_design","kind":"DEPENDS_ON"},{"id":"edge-3","type":"CONTROL","from":"frontend_design","to":"development_implementation","kind":"DEPENDS_ON"}]}\n'
            "```\n",
        ])

        plan = generate_plan_with_llm("請規劃創意遊戲", llm_client=llm)

        self.assertEqual(plan.id, "graph-2-repaired")
        self.assertEqual(
            [node.id for node in plan.nodes if isinstance(node, TaskNode)],
            ["concept_alignment", "spec_organizer", "frontend_design", "development_implementation"],
        )
        self.assertEqual(len(llm.calls), 2)

    def test_generate_plan_with_llm_preserves_last_valid_graph_when_repair_response_is_invalid(self) -> None:
        llm = _MockLLM([
            "```json\n"
            '{"graphId":"graph-2","name":"規劃圖","version":"taskgraph.v3","createdAt":"2026-03-16T00:00:00Z","createdBy":"planner","nodes":[{"id":"concept_alignment","type":"TASK","title":"概念對齊","objective":"查關鍵概念","definitionOfDone":["完成概念摘要","整理風險"],"skillBindings":[{"skillId":"concept-alignment","role":"PRIMARY","config":{"tools":["web.search"]}},{"skillId":"web-search-strategy","role":"PRIMARY"}],"execution":{"mode":"SINGLE"}},{"id":"requirements","type":"TASK","title":"需求規格","objective":"整理需求","definitionOfDone":["完成需求","完成規格"],"execution":{"mode":"SINGLE"}},{"id":"architecture","type":"TASK","title":"架構設計","objective":"整理架構","definitionOfDone":["完成架構","完成限制"],"execution":{"mode":"SINGLE"}},{"id":"visual","type":"TASK","title":"視覺規格","objective":"整理視覺","definitionOfDone":["完成視覺","完成風格"],"execution":{"mode":"SINGLE"}}],"edges":[{"id":"edge-1","type":"CONTROL","from":"concept_alignment","to":"requirements","kind":"DEPENDS_ON"},{"id":"edge-2","type":"CONTROL","from":"requirements","to":"architecture","kind":"DEPENDS_ON"},{"id":"edge-3","type":"CONTROL","from":"architecture","to":"visual","kind":"DEPENDS_ON"}]}\n'
            "```\n",
            "not-json",
        ])

        plan = generate_plan_with_llm("請規劃創意遊戲", llm_client=llm)

        self.assertEqual(plan.id, "graph-2")
        self.assertEqual(
            [node.id for node in plan.nodes if isinstance(node, TaskNode)],
            ["concept_alignment", "requirements", "architecture", "visual"],
        )
        self.assertEqual(len(llm.calls), 3)

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
        self.assertIn("輸出結構：", payload)
        self.assertIn("請只輸出一段 json code block", payload)
        self.assertNotIn("可用 Skills", payload)
        self.assertNotIn("可用 Tools", payload)
        system_prompt = llm.calls[0][0]["content"]
        self.assertIn("可用 Skills 定義：", system_prompt)
        self.assertIn("可用 Tools 定義：", system_prompt)
        self.assertIn('"toolId": "web.search"', system_prompt)
        self.assertIn('"skillId": "frontend-design"', system_prompt)
        self.assertNotIn('"skillId": "problem-decomposer"', system_prompt)
        self.assertIn("concept-alignment", system_prompt)
        self.assertIn("web-search-strategy", system_prompt)
        self.assertIn("嚴禁輸出任何 agent/persona/assignment", system_prompt)
        self.assertIn("CONTROL/DEPENDS_ON 的方向固定是前置節點 -> 依賴它的節點", system_prompt)
        self.assertIn("不得建立 ARTIFACT node", system_prompt)
        self.assertIn("planner 已在圖外完成拆題；graph 內不得再出現 TODO / 任務拆解 / task outline / WBS 類 TASK", system_prompt)
        self.assertIn("TASK 節點總數不得超過 8", system_prompt)
        self.assertIn("好例子：概念對齊 -> 規格整理 -> 前端設計 -> 開發實作", system_prompt)
        self.assertIn("spec-organizer", system_prompt)
        self.assertIn("vibe-coding-guidelines", system_prompt)
        self.assertIn("根據上下文構成以及執行角色相似程度來切分", system_prompt)
        self.assertIn("執行角色是任務的天然分界", system_prompt)
        self.assertIn("Task 是可由單一主執行者直接完成", system_prompt)
        self.assertIn("Artifact 是被 TASK 產出、引用、審查或交付的資訊", system_prompt)
        self.assertIn("Milestone 是時點或狀態檢查，不是 TaskGraph v3 NodeType", system_prompt)
        self.assertIn("問題拆解 / WBS / issue tree 類 skill 屬於 planner 內部能力", system_prompt)
        self.assertIn("內容必須是可執行的 GraphDefinition JSON", payload)
        self.assertIn("不要輸出 Mermaid，也不要輸出任何 JSON 之外的補充文字", payload)
        self.assertIn("taskSpec.executor 只能是 agent、tool、sandbox_run", system_prompt)
        self.assertIn("每個 node.id 都必須是非空且唯一的字串", system_prompt)

    def test_generate_plan_with_llm_marks_empty_tool_list_non_runnable(self) -> None:
        llm = _MockLLM([
            '{"version":"taskgraph.v3","nodes":[{"id":"task_concept_alignment","node_type":"TASK","title":"概念對齊","taskSpec":{"executor":"tool","tool":{"tools":[]},"display":{"label":"概念對齊"},"runnable":true}}],"edges":[]}',
        ])

        plan = generate_plan_with_llm("請規劃", llm_client=llm)

        task_node = next(node for node in plan.nodes if isinstance(node, TaskNode))
        self.assertEqual(task_node.task_spec.executor, "tool")
        self.assertEqual(task_node.task_spec.tool.tools, [])
        self.assertFalse(task_node.task_spec.runnable)
        self.assertIn("tool 缺少可執行工具定義", task_node.task_spec.non_runnable_reason)


if __name__ == "__main__":
    unittest.main()
