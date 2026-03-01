import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class CoreStreamHandlerTests(unittest.TestCase):
    def test_run_single_stream_forwards_conversation_history_to_graph_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("單輪對話測試")
                project_path = Path(project.path)
                run_dir = project_path / ".amon" / "runs" / "run-test"
                output_path = run_dir / "docs" / "single_run-test.md"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("ok", encoding="utf-8")
                history = [
                    {"role": "user", "content": "前一輪需求"},
                    {"role": "assistant", "content": "好的，請補充細節"},
                ]

                with patch.object(
                    core,
                    "run_graph",
                    return_value=SimpleNamespace(run_dir=run_dir, run_id="run-test"),
                ) as mock_run_graph:
                    core.run_single_stream(
                        "請直接開始",
                        project_path=project_path,
                        conversation_history=history,
                    )

                self.assertEqual(
                    mock_run_graph.call_args.kwargs.get("variables"),
                    {"conversation_history": history},
                )
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_self_critique_forwards_stream_handler_to_run_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                docs_dir = project_path / "docs"
                docs_dir.mkdir(parents=True, exist_ok=True)
                draft_path = docs_dir / "draft_v1.md"
                reviews_dir = docs_dir / "reviews_v1"
                final_path = docs_dir / "final_v1.md"
                final_path.write_text("done", encoding="utf-8")
                handler = object()

                with patch.object(
                    core,
                    "_resolve_doc_paths",
                    return_value=(draft_path, reviews_dir, final_path, 1),
                ), patch.object(core, "run_graph", return_value=SimpleNamespace()) as mock_run_graph:
                    core.run_self_critique("測試", project_path=project_path, stream_handler=handler)

                self.assertIs(mock_run_graph.call_args.kwargs.get("stream_handler"), handler)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_team_forwards_stream_handler_to_run_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                final_path = project_path / "docs" / "final.md"
                final_path.parent.mkdir(parents=True, exist_ok=True)
                final_path.write_text("done", encoding="utf-8")
                handler = object()

                with patch.object(core, "run_graph", return_value=SimpleNamespace()) as mock_run_graph, patch.object(
                    core, "_sync_team_tasks"
                ):
                    core.run_team("測試", project_path=project_path, stream_handler=handler)

                self.assertIs(mock_run_graph.call_args.kwargs.get("stream_handler"), handler)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_plan_execute_stream_uses_planner_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("plan-exec-planner")
                project_path = Path(project.path)
                core.set_config_value("amon.planner.enabled", True, project_path=project_path)
                fake_result = SimpleNamespace(run_id="run-plan", run_dir=project_path / ".amon" / "runs" / "run-plan")

                with patch.object(core, "generate_plan_docs") as mock_generate, patch("amon.core.compile_plan_to_exec_graph", return_value={"nodes": [], "edges": [], "variables": {}}) as mock_compile, patch.object(core, "run_graph", return_value=fake_result), patch.object(core, "_load_graph_primary_output", return_value="plan-ok"):
                    core.run_plan_execute_stream(
                        "請完成任務",
                        project_path=project_path,
                        project_id=project.project_id,
                        run_id="run-from-ui",
                    )

                self.assertTrue(mock_generate.called)
                self.assertTrue(mock_compile.called)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_plan_execute_stream_ignores_disabled_and_keeps_planner_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("plan-exec-fallback")
                project_path = Path(project.path)
                core.set_config_value("amon.planner.enabled", False, project_path=project_path)
                fake_result = SimpleNamespace(run_id="run-plan", run_dir=project_path / ".amon" / "runs" / "run-plan")

                with patch.object(core, "generate_plan_docs") as mock_generate, patch(
                    "amon.core.compile_plan_to_exec_graph", return_value={"nodes": [], "edges": [], "variables": {}}
                ) as mock_compile, patch.object(core, "run_graph", return_value=fake_result), patch.object(
                    core, "_load_graph_primary_output", return_value="plan response"
                ):
                    result, response = core.run_plan_execute_stream(
                        "請完成任務",
                        project_path=project_path,
                        project_id=project.project_id,
                        stream_handler=object(),
                        run_id="run-from-ui",
                        conversation_history=[{"role": "user", "content": "歷史"}],
                    )

                self.assertEqual(result.run_id, "run-plan")
                self.assertEqual(response, "plan response")
                self.assertTrue(mock_generate.called)
                self.assertTrue(mock_compile.called)
                self.assertEqual(getattr(result, "execution_route", ""), "planner")
                self.assertTrue(getattr(result, "planner_enabled", False))
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
