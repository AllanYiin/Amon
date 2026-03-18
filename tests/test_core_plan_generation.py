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
from amon.taskgraph3.payloads import AgentTaskConfig, InputBinding, TaskDisplayMetadata, TaskSpec
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
                self.assertIn("  - Skill: concept-alignment", todo_text)
                self.assertIn("  - Skill: （未綁定 skill）", todo_text)
                task_nodes = [node for node in plan.nodes if isinstance(node, TaskNode)]
                self.assertEqual(task_nodes[0].id, "concept_alignment")
                self.assertIn("web.search", task_nodes[0].task_spec.agent.allowed_tools)
                self.assertEqual(task_nodes[0].task_spec.agent.skills, ["concept-alignment"])
                self.assertEqual(task_nodes[1].task_spec.agent.skills, [])
                self.assertIn("[AMON_NODE_MODE=EXECUTION]", task_nodes[1].task_spec.agent.system_prompt or "")
                self.assertTrue(emit_mock.called)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_build_quick_todo_markdown_marks_planner_stage_as_internal(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            todo = core._build_quick_todo_markdown("請幫我規劃上線流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)
        self.assertIn("  - Skill: concept-alignment", todo)
        self.assertIn("  - Skill: planner-internal", todo)

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

    def test_postprocess_planner_graph_merges_spec_cluster_tasks(self) -> None:
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
        self.assertEqual(task_ids, ["concept_alignment", "requirements", "packaging"])
        self.assertEqual(task_nodes[1].title, "設計定義")
        self.assertIn("請把需求、PRD、系統架構、視覺方向與預設參數整合成同一設計階段", task_nodes[1].task_spec.agent.prompt or "")
        control_pairs = {
            (edge.from_node, edge.to_node)
            for edge in processed.edges
            if edge.edge_type == "CONTROL"
        }
        self.assertIn(("concept_alignment", "requirements"), control_pairs)
        self.assertIn(("requirements", "packaging"), control_pairs)

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


if __name__ == "__main__":
    unittest.main()
