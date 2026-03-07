import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.taskgraph3.payloads import AgentTaskConfig, TaskDisplayMetadata, TaskSpec
from amon.taskgraph3.schema import ArtifactNode, GraphDefinition, GraphEdge, TaskNode


class CorePlanGenerationTests(unittest.TestCase):
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
                            title="任務",
                            task_spec=TaskSpec(
                                executor="agent",
                                agent=AgentTaskConfig(prompt="請完成", instructions="執行"),
                                display=TaskDisplayMetadata(label="任務", summary="完成", todo_hint="done"),
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
                self.assertIn("- [ ] task-1 任務", todo_text)
                self.assertTrue(emit_mock.called)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
