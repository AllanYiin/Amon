import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.planning.schema import PlanContext, PlanGraph, PlanNode


class RunPlanExecuteTests(unittest.TestCase):
    def test_run_plan_execute_uses_planner_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                record = core.create_project("plan-exec-default")
                project_path = core.get_project_path(record.project_id)
                fake_plan = PlanGraph(
                    schema_version="1.0",
                    objective="測試",
                    nodes=[PlanNode(id="T1", title="任務", goal="完成", definition_of_done=["done"], depends_on=[], requires_llm=False)],
                    context=PlanContext(),
                )
                with patch("amon.core.generate_plan_with_llm", return_value=fake_plan), patch.object(core, "run_graph") as run_graph, patch.object(
                    core, "_load_graph_primary_output", return_value="plan-output"
                ), patch.object(core, "run_single", return_value="single-path") as run_single, patch("amon.core.emit_event"):
                    run_graph.return_value = type("R", (), {"run_dir": project_path / ".amon" / "runs" / "r1"})()
                    response = core.run_plan_execute("任務", project_path=project_path, project_id=record.project_id)
                self.assertEqual(response, "plan-output")
                self.assertTrue(run_graph.called)
                self.assertFalse(run_single.called)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_plan_execute_prefers_planner_when_flag_is_false_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                record = core.create_project("plan-exec-string-false")
                project_path = core.get_project_path(record.project_id)
                core.set_config_value("amon.planner.enabled", "false", project_path=project_path)
                fake_plan = PlanGraph(
                    schema_version="1.0",
                    objective="測試",
                    nodes=[PlanNode(id="T1", title="任務", goal="完成", definition_of_done=["done"], depends_on=[], requires_llm=False)],
                    context=PlanContext(),
                )
                with patch("amon.core.generate_plan_with_llm", return_value=fake_plan), patch.object(core, "run_graph") as run_graph, patch.object(
                    core, "_load_graph_primary_output", return_value="plan-output"
                ), patch.object(core, "run_single", return_value="single-path") as run_single, patch("amon.core.emit_event"):
                    run_graph.return_value = type("R", (), {"run_dir": project_path / ".amon" / "runs" / "r1"})()
                    response = core.run_plan_execute("任務", project_path=project_path, project_id=record.project_id)
                self.assertEqual(response, "plan-output")
                self.assertTrue(run_graph.called)
                self.assertFalse(run_single.called)
            finally:
                os.environ.pop("AMON_HOME", None)


    def test_run_plan_execute_falls_back_when_legacy_mode_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            os.environ["AMON_PLAN_EXECUTE_LEGACY_SINGLE_FALLBACK"] = "1"
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                record = core.create_project("plan-exec-legacy-fallback")
                project_path = core.get_project_path(record.project_id)
                core.set_config_value("amon.planner.enabled", False, project_path=project_path)
                with patch.object(core, "run_single", return_value="single-path") as run_single:
                    response = core.run_plan_execute("任務", project_path=project_path, project_id=record.project_id)
                self.assertEqual(response, "single-path")
                self.assertTrue(run_single.called)
            finally:
                os.environ.pop("AMON_PLAN_EXECUTE_LEGACY_SINGLE_FALLBACK", None)
                os.environ.pop("AMON_HOME", None)

    def test_run_plan_execute_compiles_and_runs_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                record = core.create_project("plan-exec-enabled")
                project_path = core.get_project_path(record.project_id)
                core.set_config_value("amon.planner.enabled", True, project_path=project_path)
                fake_plan = PlanGraph(
                    schema_version="1.0",
                    objective="測試",
                    nodes=[PlanNode(id="T1", title="任務", goal="完成", definition_of_done=["done"], depends_on=[], requires_llm=False)],
                    context=PlanContext(),
                )
                with patch("amon.core.generate_plan_with_llm", return_value=fake_plan), patch.object(core, "run_graph") as run_graph, patch.object(
                    core, "_load_graph_primary_output", return_value="plan-output"
                ), patch("amon.core.emit_event"):
                    run_graph.return_value = type("R", (), {"run_dir": project_path / ".amon" / "runs" / "r1"})()
                    response = core.run_plan_execute("任務", project_path=project_path, project_id=record.project_id)
                self.assertEqual(response, "plan-output")
                self.assertTrue(run_graph.called)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
