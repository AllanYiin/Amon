import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.planning.compiler import compile_plan_to_exec_graph
from amon.planning.schema import PlanContext, PlanGraph, PlanNode


class PlanCompilerTests(unittest.TestCase):
    def test_compile_plan_to_exec_graph_builds_nodes_and_edges(self) -> None:
        plan = PlanGraph(
            schema_version="1.0",
            objective="測試",
            nodes=[
                PlanNode(
                    id="T1",
                    title="準備",
                    goal="完成準備",
                    definition_of_done=["done"],
                    depends_on=[],
                    requires_llm=True,
                    llm={"mode": "plan_execute", "prompt": "做", "instructions": "完成"},
                    tools=[{"tool_name": "web.search", "args_schema_hint": {"query": "x"}, "when_to_use": "查詢"}],
                ),
                PlanNode(
                    id="T2",
                    title="執行",
                    goal="完成執行",
                    definition_of_done=["done"],
                    depends_on=["T1"],
                    requires_llm=True,
                    llm={"mode": "plan_execute", "prompt": "做2", "instructions": "完成2"},
                ),
            ],
            context=PlanContext(),
        )
        graph = compile_plan_to_exec_graph(plan)
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertIn("plan_T1_tool_1", node_ids)
        self.assertIn("plan_T1_llm", node_ids)
        self.assertIn("plan_T2_llm", node_ids)

    def test_compile_plan_detects_cycle(self) -> None:
        plan = PlanGraph(
            schema_version="1.0",
            objective="測試",
            nodes=[
                PlanNode(id="T1", title="A", goal="A", definition_of_done=["a"], depends_on=["T2"], requires_llm=False),
                PlanNode(id="T2", title="B", goal="B", definition_of_done=["b"], depends_on=["T1"], requires_llm=False),
            ],
            context=PlanContext(),
        )
        with self.assertRaises(ValueError):
            compile_plan_to_exec_graph(plan)


if __name__ == "__main__":
    unittest.main()
