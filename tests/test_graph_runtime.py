import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class GraphRuntimeTests(unittest.TestCase):
    def test_graph_run_creates_state_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Graph 專案")
                project_path = Path(project.path)
                core.set_config_value(
                    "providers.mock",
                    {
                        "type": "mock",
                        "default_model": "mock-model",
                        "stream_chunks": ["OK"],
                    },
                    project_path=project_path,
                )
                core.set_config_value("amon.provider", "mock", project_path=project_path)

                graph = {
                    "variables": {"name": "Amon"},
                    "nodes": [
                        {
                            "id": "write",
                            "type": "write_file",
                            "path": "docs/output.txt",
                            "content": "Hello ${name}",
                        },
                        {
                            "id": "agent",
                            "type": "agent_task",
                            "prompt": "Hi ${name}",
                        },
                    ],
                    "edges": [{"from": "write", "to": "agent"}],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                result = core.run_graph(project_path=project_path, graph_path=graph_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            run_dir = result.run_dir
            state_path = run_dir / "state.json"
            resolved_path = run_dir / "graph.resolved.json"
            events_path = run_dir / "events.jsonl"

            self.assertTrue(state_path.exists())
            self.assertTrue(resolved_path.exists())
            self.assertTrue(events_path.exists())

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "completed")
            self.assertIn("write", state["nodes"])
            self.assertIn("agent", state["nodes"])
            self.assertEqual(state["nodes"]["write"]["status"], "completed")
            self.assertEqual(state["nodes"]["agent"]["status"], "completed")

            output_path = project_path / "docs" / "output.txt"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "Hello Amon")

    def test_graph_template_parametrize_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Template 專案")
                project_path = Path(project.path)
                core.set_config_value(
                    "providers.mock",
                    {
                        "type": "mock",
                        "default_model": "mock-model",
                        "stream_chunks": ["OK"],
                    },
                    project_path=project_path,
                )
                core.set_config_value("amon.provider", "mock", project_path=project_path)

                graph = {
                    "variables": {},
                    "nodes": [
                        {
                            "id": "write",
                            "type": "write_file",
                            "path": "docs/output.txt",
                            "content": "Tesla",
                        }
                    ],
                    "edges": [],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                run_result = core.run_graph(project_path=project_path, graph_path=graph_path)
                template_result = core.create_graph_template(project.project_id, run_result.run_id)
                core.parametrize_graph_template(
                    template_result["template_id"],
                    "$.nodes[0].content",
                    "company",
                )
                template_path = Path(template_result["path"])
                template_payload = json.loads(template_path.read_text(encoding="utf-8"))
                schema_payload = json.loads(Path(template_result["schema_path"]).read_text(encoding="utf-8"))
                variables_schema = template_payload.get("variables_schema", {})
                self.assertIn("company", schema_payload.get("properties", {}))
                self.assertIn("company", variables_schema.get("properties", {}))
                self.assertIn("company", variables_schema.get("required", []))

                template_run = core.run_graph_template(
                    template_result["template_id"],
                    {"company": "Amon"},
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            output_path = project_path / "docs" / "output.txt"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "Amon")
            self.assertNotEqual(run_result.run_id, template_run.run_id)

    def test_graph_template_parametrize_prompt_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Prompt 範本專案")
                project_path = Path(project.path)
                core.set_config_value(
                    "providers.mock",
                    {
                        "type": "mock",
                        "default_model": "mock-model",
                        "stream_chunks": ["OK"],
                    },
                    project_path=project_path,
                )
                core.set_config_value("amon.provider", "mock", project_path=project_path)

                graph = {
                    "variables": {},
                    "nodes": [
                        {
                            "id": "agent",
                            "type": "agent_task",
                            "prompt": "原始訊息",
                        }
                    ],
                    "edges": [],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                run_result = core.run_graph(project_path=project_path, graph_path=graph_path)
                template_result = core.create_graph_template(project.project_id, run_result.run_id)
                core.parametrize_graph_template(
                    template_result["template_id"],
                    "$.nodes[0].prompt",
                    "user_prompt",
                )

                template_run = core.run_graph_template(
                    template_result["template_id"],
                    {"user_prompt": "替換訊息"},
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            resolved_path = template_run.run_dir / "graph.resolved.json"
            self.assertTrue(resolved_path.exists())
            resolved_payload = json.loads(resolved_path.read_text(encoding="utf-8"))
            self.assertEqual(resolved_payload["nodes"][0]["prompt"], "替換訊息")


if __name__ == "__main__":
    unittest.main()
