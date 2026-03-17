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
from amon.taskgraph3.payloads import AgentTaskConfig, TaskDisplayMetadata, TaskSpec
from amon.taskgraph3.serialize import dumps_graph_definition
from amon.taskgraph3.schema import ArtifactNode, GraphDefinition, GraphEdge, TaskNode


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
                            title="任務骨架",
                            task_spec=TaskSpec(
                                executor="agent",
                                agent=AgentTaskConfig(prompt="請完成", instructions="執行"),
                                display=TaskDisplayMetadata(label="任務骨架", summary="切分待辦與依賴", todo_hint="done"),
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
                self.assertIn("- [ ] task-1 任務骨架", todo_text)
                self.assertIn("- [ ] concept_alignment 概念對齊", todo_text)
                self.assertIn("  - Skill: concept-alignment", todo_text)
                self.assertIn("  - Skill: problem-decomposer", todo_text)
                task_nodes = [node for node in plan.nodes if isinstance(node, TaskNode)]
                self.assertEqual(task_nodes[0].id, "concept_alignment")
                self.assertIn("web.search", task_nodes[0].task_spec.agent.allowed_tools)
                self.assertEqual(task_nodes[0].task_spec.agent.skills, ["concept-alignment"])
                self.assertEqual(task_nodes[1].task_spec.agent.skills, ["problem-decomposer"])
                self.assertTrue(emit_mock.called)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_build_quick_todo_markdown_includes_bound_skills(self) -> None:
        core = AmonCore(data_dir=Path(tempfile.mkdtemp()))
        try:
            todo = core._build_quick_todo_markdown("請幫我規劃上線流程", available_tools=[{"name": "web.search"}])
        finally:
            shutil.rmtree(core.data_dir, ignore_errors=True)
        self.assertIn("  - Skill: concept-alignment", todo)
        self.assertIn("  - Skill: problem-decomposer", todo)

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


if __name__ == "__main__":
    unittest.main()
