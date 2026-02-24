import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.planning.schema import PlanContext, PlanGraph, PlanNode


class CorePlanGenerationTests(unittest.TestCase):
    def test_generate_plan_docs_writes_files_and_emits_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                record = core.create_project("plan-test")
                project_path = core.get_project_path(record.project_id)
                fake_plan = PlanGraph(
                    schema_version="1.0",
                    objective="測試任務",
                    nodes=[
                        PlanNode(
                            id="T1",
                            title="任務",
                            goal="完成",
                            definition_of_done=["done"],
                            depends_on=[],
                            requires_llm=False,
                        )
                    ],
                    context=PlanContext(),
                )
                with patch("amon.core.generate_plan_with_llm", return_value=fake_plan), patch("amon.core.emit_event") as emit_mock:
                    plan = core.generate_plan_docs("請規劃", project_path=project_path, project_id=record.project_id)
                self.assertEqual(plan.objective, "測試任務")
                self.assertTrue((project_path / "docs" / "plan.json").exists())
                self.assertTrue((project_path / "docs" / "TODO.md").exists())
                self.assertTrue(emit_mock.called)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
