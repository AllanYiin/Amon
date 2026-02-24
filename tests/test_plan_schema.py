import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.planning.render import render_todo_markdown
from amon.planning.schema import PlanContext, PlanGraph, PlanNode
from amon.planning.serialize import dumps_plan, loads_plan


class PlanSchemaTests(unittest.TestCase):
    def _sample_plan(self) -> PlanGraph:
        return PlanGraph(
            schema_version="1.0",
            objective="重構兩層圖",
            nodes=[
                PlanNode(
                    id="T1",
                    title="定義 schema",
                    goal="完成資料模型",
                    definition_of_done=["schema 可序列化", "可 roundtrip"],
                    depends_on=[],
                    requires_llm=False,
                    tools=[{"tool_name": "python", "args_schema_hint": {}, "when_to_use": "測試"}],
                    skills=["spec-to-tasks"],
                    expected_artifacts=[{"path": "docs/T1.md", "type": "md", "description": "說明"}],
                ),
                PlanNode(
                    id="T2",
                    title="串接流程",
                    goal="落地執行",
                    definition_of_done=["串接入口"],
                    depends_on=["T1"],
                    requires_llm=True,
                    llm={"mode": "plan_execute", "prompt": "請拆解", "instructions": "輸出 JSON"},
                ),
            ],
            context=PlanContext(
                assumptions=["Phase 1"],
                constraints=["不破壞相容"],
                glossary={"DoD": "Definition of Done"},
            ),
        )

    def test_dumps_plan_is_stable(self) -> None:
        plan = self._sample_plan()
        text1 = dumps_plan(plan)
        text2 = dumps_plan(plan)
        self.assertEqual(text1, text2)

    def test_roundtrip_load_dump_load(self) -> None:
        plan = self._sample_plan()
        first = loads_plan(dumps_plan(plan))
        second = loads_plan(dumps_plan(first))
        self.assertEqual(dumps_plan(first), dumps_plan(second))

    def test_render_todo_markdown_contains_id_and_dod(self) -> None:
        markdown = render_todo_markdown(self._sample_plan())
        self.assertIn("- [ ] T1 定義 schema", markdown)
        self.assertIn("DoD:", markdown)


if __name__ == "__main__":
    unittest.main()
