import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.planning import semantic_plan_issues
from amon.taskgraph3.payloads import AgentTaskConfig, InputBinding, TaskDisplayMetadata, TaskSpec, ToolTaskConfig
from amon.taskgraph3.serialize import dumps_graph_definition
from amon.taskgraph3.schema import ArtifactNode, GraphDefinition, GraphEdge, TaskNode, validate_graph_definition


class CorePlanGenerationTests(unittest.TestCase):
    def test_to_taskgraph3_definition_accepts_agent_allowed_tools_payload(self) -> None:
        temp_dir = tempfile.mkdtemp()
        try:
            core = AmonCore(data_dir=Path(temp_dir))
            graph = core._to_taskgraph3_definition(
                {
                    "version": "taskgraph.v3",
                    "nodes": [
                        {
                            "id": "task-1",
                            "node_type": "TASK",
                            "title": "概念對齊",
                            "taskSpec": {
                                "executor": "agent",
                                "agent": {
                                    "prompt": "先查概念",
                                    "allowedTools": ["web.search"],
                                    "skills": ["concept-alignment"],
                                },
                            },
                        }
                    ],
                    "edges": [],
                }
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        node = next(node for node in graph.nodes if isinstance(node, TaskNode))
        self.assertEqual(node.task_spec.agent.allowed_tools, ["web.search"])
        self.assertEqual(node.task_spec.agent.skills, ["concept-alignment"])

    def test_generate_plan_docs_writes_v3_plan_and_todo_and_emits_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                record = core.create_project("plan-test")
                project_path = core.get_project_path(record.project_id)
                fake_plan = GraphDefinition(
                    version="taskgraph.v3",
                    nodes=[
                        TaskNode(
                            id="task-1",
                            title="需求規格",
                            task_spec=TaskSpec(
                                executor="agent",
                                agent=AgentTaskConfig(prompt="請完成", instructions="執行"),
                                display=TaskDisplayMetadata(label="需求規格", summary="完成需求規格", todo_hint="done"),
                            ),
                        ),
                        ArtifactNode(id="artifact-task-1-todo", title="docs/TODO.md"),
                    ],
                    edges=[GraphEdge(from_node="task-1", to_node="artifact-task-1-todo", edge_type="DATA", kind="EMITS")],
                )
                with patch("amon.core.generate_plan_with_llm", return_value=fake_plan), patch("amon.core.emit_event") as emit_mock:
                    plan = core.generate_plan_docs("請規劃", project_path=project_path, project_id=record.project_id)
                self.assertEqual(plan.version, "taskgraph.v3")
                plan_payload = json.loads((project_path / "docs" / "plan.json").read_text(encoding="utf-8"))
                self.assertEqual(plan_payload.get("version"), "taskgraph.v3")
                todo_text = (project_path / "docs" / "TODO.md").read_text(encoding="utf-8")
                self.assertIn("- [ ] task-1 需求規格", todo_text)
                self.assertIn("- [ ] concept_alignment 概念對齊", todo_text)
                self.assertIn("  - Skill: concept-alignment、web-search-strategy", todo_text)
                self.assertIn("  - Skill: （未綁定 skill）", todo_text)
                task_nodes = [node for node in plan.nodes if isinstance(node, TaskNode)]
                self.assertFalse(any(isinstance(node, ArtifactNode) for node in plan.nodes))
                self.assertEqual(task_nodes[0].id, "concept_alignment")
                self.assertIn("web.search", task_nodes[0].task_spec.agent.allowed_tools)
                self.assertEqual(task_nodes[0].task_spec.agent.skills, ["concept-alignment", "web-search-strategy"])
                self.assertEqual(task_nodes[1].task_spec.agent.skills, [])
                self.assertEqual(task_nodes[1].task_spec.artifacts[0].name, "TODO")
                self.assertEqual(task_nodes[1].task_spec.artifacts[0].media_type, "text/markdown")
                self.assertIn("[AMON_NODE_MODE=EXECUTION]", task_nodes[1].task_spec.agent.system_prompt or "")
                self.assertTrue(emit_mock.called)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_generate_plan_docs_rejects_development_plan_missing_frontend_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            core = AmonCore(data_dir=Path(temp_dir))
            record = core.create_project("plan-semantic-guard")
            project_path = core.get_project_path(record.project_id)
            incomplete_plan = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(
                                prompt="先做概念對齊",
                                skills=["concept-alignment", "web-search-strategy"],
                            ),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="requirements",
                        title="需求規格",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理需求"),
                            display=TaskDisplayMetadata(label="需求規格", summary="完成需求規格", todo_hint="完成規格"),
                        ),
                    ),
                ],
                edges=[GraphEdge(from_node="concept_alignment", to_node="requirements", edge_type="CONTROL", kind="DEPENDS_ON")],
            )

            with patch("amon.core.generate_plan_with_llm", return_value=incomplete_plan), patch.object(
                core,
                "_postprocess_planner_graph",
                return_value=incomplete_plan,
            ):
                with self.assertRaisesRegex(ValueError, "程式開發任務缺少「前端設計」TASK"):
                    core.generate_plan_docs(
                        "請幫我開發一個內部工具",
                        project_path=project_path,
                        project_id=record.project_id,
                    )

    def test_generate_plan_docs_repairs_cycle_before_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            core = AmonCore(data_dir=Path(temp_dir))
            record = core.create_project("plan-cycle-fallback")
            project_path = core.get_project_path(record.project_id)
            cyclic_plan = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="design",
                        title="設計定義",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成設計"),
                            display=TaskDisplayMetadata(label="設計定義", summary="完成設計", todo_hint="完成設計"),
                        ),
                    ),
                    TaskNode(
                        id="implement",
                        title="核心實作",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成實作"),
                            display=TaskDisplayMetadata(label="核心實作", summary="完成實作", todo_hint="完成實作"),
                        ),
                    ),
                ],
                edges=[
                    GraphEdge(from_node="concept_alignment", to_node="design", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="design", to_node="implement", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="implement", to_node="design", edge_type="CONTROL", kind="DEPENDS_ON"),
                ],
            )

            with patch("amon.core.generate_plan_with_llm", return_value=cyclic_plan):
                plan = core.generate_plan_docs("請為我開發一個3d煙火模擬器", project_path=project_path, project_id=record.project_id)

            validate_graph_definition(plan)
            control_pairs = [
                (edge.from_node, edge.to_node)
                for edge in plan.edges
                if edge.edge_type == "CONTROL" and edge.kind == "DEPENDS_ON"
            ]
            self.assertEqual(
                control_pairs,
                [
                    ("concept_alignment", "spec_organizer"),
                    ("spec_organizer", "frontend_design"),
                    ("frontend_design", "development_implementation"),
                ],
            )

    def test_generate_plan_docs_writes_planner_repair_trace_for_semantic_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            core = AmonCore(data_dir=Path(temp_dir))
            record = core.create_project("plan-repair-trace")
            project_path = core.get_project_path(record.project_id)
            repairable_plan = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="requirements",
                        title="需求規格",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理需求"),
                            display=TaskDisplayMetadata(label="需求規格", summary="需求", todo_hint="完成規格"),
                        ),
                    ),
                    TaskNode(
                        id="architecture",
                        title="架構設計",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理架構"),
                            display=TaskDisplayMetadata(label="架構設計", summary="架構", todo_hint="完成架構"),
                        ),
                    ),
                    TaskNode(
                        id="implementation",
                        title="程式實作",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成程式"),
                            display=TaskDisplayMetadata(label="程式實作", summary="實作", todo_hint="完成開發"),
                        ),
                    ),
                ],
                edges=[],
            )

            with patch("amon.core.generate_plan_with_llm", return_value=repairable_plan):
                plan = core.generate_plan_docs(
                    "請規劃交付流程",
                    project_path=project_path,
                    project_id=record.project_id,
                    run_id="run-plan-repair",
                )

            self.assertEqual(
                [node.id for node in plan.nodes if isinstance(node, TaskNode)],
                ["concept_alignment", "spec_organizer", "frontend_design", "development_implementation"],
            )
            trace_dir = project_path / ".amon" / "runs" / "run-plan-repair" / "planner_repair"
            self.assertTrue((trace_dir / "pre_repair_graph.json").exists())
            self.assertTrue((trace_dir / "post_repair_graph.json").exists())
            self.assertTrue((trace_dir / "repair_patch.json").exists())
            self.assertTrue((trace_dir / "repair_report.json").exists())
            pre_payload = json.loads((trace_dir / "pre_repair_graph.json").read_text(encoding="utf-8"))
            post_payload = json.loads((trace_dir / "post_repair_graph.json").read_text(encoding="utf-8"))
            patch_payload = json.loads((trace_dir / "repair_patch.json").read_text(encoding="utf-8"))
            self.assertEqual([node["id"] for node in pre_payload["nodes"]], ["concept_alignment", "requirements", "architecture", "implementation"])
            self.assertEqual(
                [node["id"] for node in post_payload["nodes"]],
                ["concept_alignment", "spec_organizer", "frontend_design", "development_implementation"],
            )
            self.assertEqual(patch_payload["operations"][0]["kind"], "ensure_development_task_stages")

    def test_build_quick_todo_markdown_marks_planner_stage_as_internal(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            todo = core._build_quick_todo_markdown("請幫我規劃上線流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)
        self.assertIn("  - Skill: concept-alignment、web-search-strategy", todo)
        self.assertIn("  - Skill: planner-internal", todo)

    def test_build_quick_todo_markdown_uses_fixed_development_stages(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            todo = core._build_quick_todo_markdown("請幫我開發一個內部工具", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)
        self.assertIn("spec_organizer 規格整理", todo)
        self.assertIn("frontend_design 前端視覺化設計", todo)
        self.assertIn("development_implementation 開發實作", todo)
        self.assertIn("  - Skill: spec-organizer", todo)
        self.assertIn("  - Skill: frontend-design", todo)
        self.assertIn("  - Skill: vibe-coding-guidelines", todo)

    def test_write_graph_resolved_preserves_graph_id_for_taskgraph_v3(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            core = AmonCore(data_dir=Path(temp_dir))
            project_path = Path(temp_dir) / "project"
            project_path.mkdir(parents=True, exist_ok=True)
            plan = GraphDefinition(
                id="planner-fallback",
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先做概念對齊"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="summary", todo_hint="dod"),
                        ),
                    )
                ],
                edges=[],
            )
            payload = json.loads(dumps_graph_definition(plan))

            graph_path = core._write_graph_resolved(project_path, payload, {}, mode="taskgraph.v3")

            resolved_payload = json.loads(graph_path.read_text(encoding="utf-8"))
            self.assertEqual(resolved_payload.get("id"), "planner-fallback")
            resolved_graph = core._to_taskgraph3_definition(resolved_payload)
            self.assertEqual(resolved_graph.id, "planner-fallback")
            self.assertEqual(resolved_graph.nodes[0].graph_id, "planner-fallback")

    def test_postprocess_planner_graph_deduplicates_concept_tasks_and_serializes_roots(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="t1_concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="再次做概念對齊"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="重複概念", todo_hint="不應保留"),
                        ),
                    ),
                    TaskNode(
                        id="requirements",
                        title="需求規格",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理需求"),
                            display=TaskDisplayMetadata(label="需求規格", summary="需求", todo_hint="完成規格"),
                        ),
                    ),
                    TaskNode(
                        id="packaging",
                        title="打包交付",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成打包"),
                            display=TaskDisplayMetadata(label="打包交付", summary="打包", todo_hint="完成交付包"),
                        ),
                    ),
                ],
                edges=[],
            )

            processed = core._postprocess_planner_graph(graph, message="請規劃交付流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        task_ids = [node.id for node in processed.nodes if isinstance(node, TaskNode)]
        self.assertEqual(task_ids.count("concept_alignment"), 1)
        self.assertNotIn("t1_concept_alignment", task_ids)
        control_pairs = {
            (edge.from_node, edge.to_node)
            for edge in processed.edges
            if edge.edge_type == "CONTROL"
        }
        self.assertIn(("concept_alignment", "requirements"), control_pairs)
        self.assertIn(("requirements", "packaging"), control_pairs)

    def test_postprocess_planner_graph_repairs_non_runnable_concept_alignment_tool_node(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="tool",
                            tool=ToolTaskConfig(tools=[]),
                            display=TaskDisplayMetadata(label="概念對齊"),
                            runnable=False,
                            non_runnable_reason="tool 缺少可執行工具定義，已降級為不可執行：概念對齊",
                        ),
                    ),
                    TaskNode(
                        id="design_definition",
                        title="設計定義",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成設計"),
                            display=TaskDisplayMetadata(label="設計定義", summary="完成設計", todo_hint="完成設計"),
                        ),
                    ),
                ],
                edges=[GraphEdge(from_node="concept_alignment", to_node="design_definition", edge_type="CONTROL", kind="DEPENDS_ON")],
            )

            processed = core._postprocess_planner_graph(
                graph,
                message="請協助我開發一個3d煙火模擬器，裡面要有屬性面板可以調整煙火外觀以及物理模擬",
                available_tools=[{"name": "web.better_search"}, {"name": "web.search"}, {"name": "web.fetch"}],
            )
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        concept_node = next(node for node in processed.nodes if isinstance(node, TaskNode) and node.id == "concept_alignment")
        self.assertEqual(concept_node.task_spec.executor, "agent")
        self.assertIsNotNone(concept_node.task_spec.agent)
        self.assertTrue(concept_node.task_spec.runnable)
        self.assertEqual(concept_node.task_spec.non_runnable_reason, None)
        self.assertIn("concept-alignment", concept_node.task_spec.agent.skills)
        self.assertIn("web-search-strategy", concept_node.task_spec.agent.skills)
        self.assertIn("web.search", concept_node.task_spec.agent.allowed_tools)

    def test_postprocess_planner_graph_enforces_fixed_development_stages(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="requirements",
                        title="需求規格",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理需求"),
                            display=TaskDisplayMetadata(label="需求規格", summary="需求", todo_hint="完成規格"),
                        ),
                    ),
                    TaskNode(
                        id="architecture",
                        title="架構設計",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理架構"),
                            display=TaskDisplayMetadata(label="架構設計", summary="架構", todo_hint="完成架構"),
                        ),
                    ),
                    TaskNode(
                        id="visual",
                        title="視覺規格",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理視覺"),
                            display=TaskDisplayMetadata(label="視覺規格", summary="視覺", todo_hint="完成視覺"),
                        ),
                    ),
                    TaskNode(
                        id="packaging",
                        title="打包交付",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成打包"),
                            display=TaskDisplayMetadata(label="打包交付", summary="打包", todo_hint="完成交付包"),
                        ),
                    ),
                ],
                edges=[],
            )

            processed = core._postprocess_planner_graph(graph, message="請規劃創意遊戲交付流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        task_nodes = [node for node in processed.nodes if isinstance(node, TaskNode)]
        task_ids = [node.id for node in task_nodes]
        self.assertEqual(
            task_ids,
            ["concept_alignment", "spec_organizer", "frontend_design", "development_implementation", "packaging"],
        )
        self.assertEqual(task_nodes[1].title, "規格整理")
        self.assertEqual(task_nodes[2].title, "前端設計")
        self.assertEqual(task_nodes[3].title, "開發實作")
        self.assertIn("spec-organizer", task_nodes[1].task_spec.agent.skills)
        self.assertIn("frontend-design", task_nodes[2].task_spec.agent.skills)
        self.assertIn("vibe-coding-guidelines", task_nodes[3].task_spec.agent.skills)
        control_pairs = {
            (edge.from_node, edge.to_node)
            for edge in processed.edges
            if edge.edge_type == "CONTROL"
        }
        self.assertIn(("concept_alignment", "spec_organizer"), control_pairs)
        self.assertIn(("spec_organizer", "frontend_design"), control_pairs)
        self.assertIn(("frontend_design", "development_implementation"), control_pairs)

    def test_postprocess_planner_graph_repairs_development_shape_when_message_is_not_obviously_dev(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="requirements",
                        title="需求規格",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理需求"),
                            display=TaskDisplayMetadata(label="需求規格", summary="需求", todo_hint="完成規格"),
                        ),
                    ),
                    TaskNode(
                        id="architecture",
                        title="架構設計",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理架構"),
                            display=TaskDisplayMetadata(label="架構設計", summary="架構", todo_hint="完成架構"),
                        ),
                    ),
                    TaskNode(
                        id="implementation",
                        title="程式實作",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成程式"),
                            display=TaskDisplayMetadata(label="程式實作", summary="實作", todo_hint="完成開發"),
                        ),
                    ),
                ],
                edges=[],
            )

            processed = core._postprocess_planner_graph(graph, message="請規劃交付流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        task_ids = [node.id for node in processed.nodes if isinstance(node, TaskNode)]
        self.assertEqual(
            task_ids,
            ["concept_alignment", "spec_organizer", "frontend_design", "development_implementation"],
        )
        self.assertEqual(semantic_plan_issues(processed, message="請規劃交付流程"), [])

    def test_postprocess_planner_graph_promotes_existing_background_research_task(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="background_research",
                        title="背景調研",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先整理背景知識"),
                            display=TaskDisplayMetadata(label="背景調研", summary="先查背景", todo_hint="完成背景摘要"),
                        ),
                    ),
                    TaskNode(
                        id="writer",
                        title="內容產出",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="開始產出"),
                            display=TaskDisplayMetadata(label="內容產出", summary="輸出內容", todo_hint="完成產出"),
                        ),
                    ),
                ],
                edges=[GraphEdge(from_node="background_research", to_node="writer", edge_type="CONTROL", kind="DEPENDS_ON")],
            )

            processed = core._postprocess_planner_graph(graph, message="請規劃交付流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        task_ids = [node.id for node in processed.nodes if isinstance(node, TaskNode)]
        self.assertEqual(task_ids, ["concept_alignment", "writer"])
        control_pairs = {
            (edge.from_node, edge.to_node)
            for edge in processed.edges
            if edge.edge_type == "CONTROL"
        }
        self.assertIn(("concept_alignment", "writer"), control_pairs)

    def test_postprocess_planner_graph_refreshes_stale_edge_relationship_ids_after_concept_rename(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="background_research",
                        title="背景調研",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先整理背景知識"),
                            display=TaskDisplayMetadata(label="背景調研", summary="先查背景", todo_hint="完成背景摘要"),
                        ),
                    ),
                    TaskNode(
                        id="writer",
                        title="內容產出",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="開始產出"),
                            display=TaskDisplayMetadata(label="內容產出", summary="輸出內容", todo_hint="完成產出"),
                        ),
                    ),
                ],
                edges=[GraphEdge(from_node="background_research", to_node="writer", edge_type="CONTROL", kind="DEPENDS_ON")],
            )
            dumps_graph_definition(graph)

            processed = core._postprocess_planner_graph(graph, message="請規劃交付流程", available_tools=[{"name": "web.search"}])
            payload = json.loads(dumps_graph_definition(processed))
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        writer_payload = next(node for node in payload["nodes"] if node["id"] == "writer")
        self.assertEqual(writer_payload["upstreamEdgeIds"], ["concept_alignment->writer:0"])

    def test_postprocess_planner_graph_promotes_concept_alignment_to_entry_without_cycle(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="background_research",
                        title="背景調研",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先整理背景知識"),
                            input_bindings=[
                                InputBinding(
                                    source="upstream",
                                    key="stale_context",
                                    from_node="writer",
                                    port="raw",
                                )
                            ],
                            display=TaskDisplayMetadata(label="背景調研", summary="先查背景", todo_hint="完成背景摘要"),
                        ),
                    ),
                    TaskNode(
                        id="writer",
                        title="內容產出",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="開始產出"),
                            display=TaskDisplayMetadata(label="內容產出", summary="輸出內容", todo_hint="完成產出"),
                        ),
                    ),
                ],
                edges=[GraphEdge(from_node="writer", to_node="background_research", edge_type="CONTROL", kind="DEPENDS_ON")],
            )

            processed = core._postprocess_planner_graph(graph, message="請規劃交付流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        validate_graph_definition(processed)
        concept = next(node for node in processed.nodes if isinstance(node, TaskNode) and node.id == "concept_alignment")
        control_pairs = {
            (edge.from_node, edge.to_node)
            for edge in processed.edges
            if edge.edge_type == "CONTROL"
        }

        self.assertIn(("concept_alignment", "writer"), control_pairs)
        self.assertNotIn(("writer", "concept_alignment"), control_pairs)
        self.assertFalse(concept.task_spec.input_bindings)

    def test_postprocess_planner_graph_normalizes_reversed_dependency_edge_directions(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="design",
                        title="設計定義",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="整理設計"),
                            display=TaskDisplayMetadata(label="設計定義", summary="整理設計", todo_hint="完成設計"),
                        ),
                    ),
                    TaskNode(
                        id="implement",
                        title="核心實作",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成實作"),
                            display=TaskDisplayMetadata(label="核心實作", summary="完成實作", todo_hint="完成實作"),
                        ),
                    ),
                    ArtifactNode(id="artifact-research", title="調研對齊文"),
                    ArtifactNode(id="artifact-spec", title="產品技術規格"),
                ],
                edges=[
                    GraphEdge(from_node="design", to_node="concept_alignment", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="implement", to_node="design", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="concept_alignment", to_node="artifact-research", edge_type="DATA", kind="PRODUCES"),
                    GraphEdge(from_node="design", to_node="artifact-research", edge_type="DATA", kind="CONSUMES"),
                    GraphEdge(from_node="design", to_node="artifact-spec", edge_type="DATA", kind="PRODUCES"),
                    GraphEdge(from_node="implement", to_node="artifact-spec", edge_type="DATA", kind="CONSUMES"),
                ],
            )

            processed = core._postprocess_planner_graph(
                graph,
                message="請為我開發一個3d煙火模擬器",
                available_tools=[{"name": "web.search"}],
            )
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        validate_graph_definition(processed)
        edges = {(edge.from_node, edge.to_node, edge.edge_type, edge.kind) for edge in processed.edges}
        self.assertFalse(any(isinstance(node, ArtifactNode) for node in processed.nodes))
        self.assertIn(("concept_alignment", "spec_organizer", "CONTROL", "DEPENDS_ON"), edges)
        self.assertIn(("spec_organizer", "frontend_design", "CONTROL", "DEPENDS_ON"), edges)
        self.assertIn(("frontend_design", "development_implementation", "CONTROL", "DEPENDS_ON"), edges)
        concept_node = next(node for node in processed.nodes if isinstance(node, TaskNode) and node.id == "concept_alignment")
        spec_node = next(node for node in processed.nodes if isinstance(node, TaskNode) and node.id == "spec_organizer")
        self.assertTrue(any(artifact.name == "調研對齊文" for artifact in concept_node.task_spec.artifacts))
        self.assertTrue(any(artifact.name == "產品技術規格" for artifact in spec_node.task_spec.artifacts))
        self.assertNotIn(("design", "concept_alignment", "CONTROL", "DEPENDS_ON"), edges)
        self.assertNotIn(("implement", "design", "CONTROL", "DEPENDS_ON"), edges)

    def test_postprocess_planner_graph_does_not_merge_execution_tasks_into_spec_cluster(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="task_design_definition",
                        title="設計定義",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成設計"),
                            display=TaskDisplayMetadata(
                                label="設計定義",
                                summary="產出設計文件與預設參數",
                                todo_hint="完成設計稿",
                            ),
                        ),
                    ),
                    TaskNode(
                        id="task_core_implementation",
                        title="核心實作",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成實作"),
                            display=TaskDisplayMetadata(
                                label="核心實作",
                                summary="完成可運行版本並支援參數調整",
                                todo_hint="完成實作與調參",
                            ),
                        ),
                    ),
                    TaskNode(
                        id="task_interaction_tuning",
                        title="互動調參",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成互動"),
                            display=TaskDisplayMetadata(
                                label="互動調參",
                                summary="讓使用者能調整視覺與物理參數",
                                todo_hint="完成互動與調參",
                            ),
                        ),
                    ),
                    TaskNode(
                        id="task_quality_packaging",
                        title="測試交付",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成測試交付"),
                            display=TaskDisplayMetadata(
                                label="測試交付",
                                summary="完成效能測試報告與交付包",
                                todo_hint="完成測試與交付",
                            ),
                        ),
                    ),
                ],
                edges=[
                    GraphEdge(from_node="concept_alignment", to_node="task_design_definition", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="task_design_definition", to_node="task_core_implementation", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="task_core_implementation", to_node="task_interaction_tuning", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="task_interaction_tuning", to_node="task_quality_packaging", edge_type="CONTROL", kind="DEPENDS_ON"),
                ],
            )

            processed = core._postprocess_planner_graph(
                graph,
                message="請為我開發一個3d煙火模擬器",
                available_tools=[{"name": "web.search"}],
            )
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        validate_graph_definition(processed)
        task_ids = [node.id for node in processed.nodes if isinstance(node, TaskNode)]
        self.assertEqual(task_ids[:4], ["concept_alignment", "spec_organizer", "frontend_design", "development_implementation"])
        self.assertIn("task_interaction_tuning", task_ids)
        self.assertIn("task_quality_packaging", task_ids)

    def test_postprocess_planner_graph_assigns_code_tools_to_game_execution_node(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="task_execute",
                        title="任務執行",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(
                                prompt="請幫我開發一個俄羅斯方塊遊戲，並直接完成可玩的單頁網頁版本。",
                                instructions="延續前置摘要直接完成交付。",
                            ),
                            display=TaskDisplayMetadata(
                                label="任務執行",
                                summary="直接完成最小可行交付。",
                                todo_hint="完成可玩的俄羅斯方塊與必要資產。",
                            ),
                        ),
                    ),
                ],
                edges=[GraphEdge(from_node="concept_alignment", to_node="task_execute", edge_type="CONTROL", kind="DEPENDS_ON")],
            )

            processed = core._postprocess_planner_graph(
                graph,
                message="請幫我開發一個俄羅斯方塊遊戲，並直接完成可玩的單頁網頁版本。",
                available_tools=[
                    {"name": "web.search"},
                    {"name": "filesystem.read"},
                    {"name": "filesystem.patch"},
                    {"name": "terminal.exec"},
                ],
            )
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        execution_node = next(
            node for node in processed.nodes if isinstance(node, TaskNode) and node.id == "development_implementation"
        )
        self.assertIn("filesystem.read", execution_node.task_spec.agent.allowed_tools)
        self.assertIn("filesystem.patch", execution_node.task_spec.agent.allowed_tools)
        self.assertIn("terminal.exec", execution_node.task_spec.agent.allowed_tools)

    def test_postprocess_planner_graph_linearizes_control_edges_when_cycle_remains(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            graph = GraphDefinition(
                version="taskgraph.v3",
                nodes=[
                    TaskNode(
                        id="concept_alignment",
                        title="概念對齊",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="先查概念"),
                            display=TaskDisplayMetadata(label="概念對齊", summary="查概念", todo_hint="完成概念摘要"),
                        ),
                    ),
                    TaskNode(
                        id="design",
                        title="設計定義",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成設計"),
                            display=TaskDisplayMetadata(label="設計定義", summary="完成設計", todo_hint="完成設計"),
                        ),
                    ),
                    TaskNode(
                        id="implement",
                        title="核心實作",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成實作"),
                            display=TaskDisplayMetadata(label="核心實作", summary="完成實作", todo_hint="完成實作"),
                        ),
                    ),
                    TaskNode(
                        id="optimize",
                        title="效能優化",
                        task_spec=TaskSpec(
                            executor="agent",
                            agent=AgentTaskConfig(prompt="完成優化"),
                            display=TaskDisplayMetadata(label="效能優化", summary="完成優化", todo_hint="完成優化"),
                        ),
                    ),
                ],
                edges=[
                    GraphEdge(from_node="concept_alignment", to_node="design", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="design", to_node="implement", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="implement", to_node="optimize", edge_type="CONTROL", kind="DEPENDS_ON"),
                    GraphEdge(from_node="optimize", to_node="design", edge_type="CONTROL", kind="DEPENDS_ON"),
                ],
            )

            processed = core._postprocess_planner_graph(
                graph,
                message="請為我開發一個3d煙火模擬器",
                available_tools=[{"name": "web.search"}],
            )
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)

        validate_graph_definition(processed)
        control_pairs = [
            (edge.from_node, edge.to_node)
            for edge in processed.edges
            if edge.edge_type == "CONTROL" and edge.kind == "DEPENDS_ON"
        ]
        self.assertEqual(
            control_pairs,
            [
                ("concept_alignment", "spec_organizer"),
                ("spec_organizer", "frontend_design"),
                ("frontend_design", "development_implementation"),
                ("development_implementation", "optimize"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
