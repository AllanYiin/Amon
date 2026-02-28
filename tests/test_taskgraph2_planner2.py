import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.planner_llm import generate_taskgraph2_with_llm
from amon.taskgraph2.schema import validate_task_graph


class FakeLLMClient:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = iter(outputs)
        self.calls: list[list[dict[str, str]]] = []

    def generate_stream(self, messages: list[dict[str, str]], model=None):  # noqa: ANN001
        _ = model
        self.calls.append(messages)
        yield next(self._outputs)


class TaskGraph2Planner2Tests(unittest.TestCase):
    def test_planner2_three_pass_output_valid_taskgraph(self) -> None:
        tools = [
            {"name": "web.search", "description": "搜尋", "input_schema": {"type": "object"}},
            {"name": "file.write", "description": "寫檔", "input_schema": {"type": "object"}},
        ]
        skills = [{"name": "spec-to-tasks", "description": "拆解任務", "targets": ["planning"]}]

        pass1 = json.dumps(
            {
                "schema_version": "2.0",
                "objective": "研究並整理重點",
                "session_defaults": {},
                "nodes": [
                    {
                        "id": "N1",
                        "title": "查資料",
                        "kind": "task",
                        "description": "收集資料",
                        "tools": [{"name": "web.search"}],
                        "output": {"type": "text", "extract": "best_effort"},
                    }
                ],
                "edges": [],
            },
            ensure_ascii=False,
        )
        pass2 = json.dumps(
            {
                "graph": {
                    "schema_version": "2.0",
                    "objective": "研究並整理重點",
                    "session_defaults": {},
                    "nodes": [
                        {
                            "id": "N1",
                            "title": "查資料",
                            "kind": "task",
                            "description": "收集資料",
                            "tools": [{"name": "web.search"}],
                            "output": {"type": "text", "extract": "best_effort"},
                        },
                        {
                            "id": "N2",
                            "title": "整理輸出",
                            "kind": "task",
                            "description": "寫出摘要",
                            "tools": [{"name": "file.write"}],
                            "output": {"type": "md", "extract": "best_effort"},
                        },
                    ],
                    "edges": [{"from": "N1", "to": "N2"}],
                }
            },
            ensure_ascii=False,
        )
        pass3 = json.dumps(
            {
                "schema_version": "2.0",
                "objective": "研究並整理重點",
                "session_defaults": {"language": "zh-TW"},
                "nodes": [
                    {
                        "id": "N1",
                        "title": "查資料",
                        "kind": "task",
                        "description": "收集資料",
                        "tools": [{"name": "web.search"}],
                        "output": {"type": "text", "extract": "best_effort"},
                    },
                    {
                        "id": "N2",
                        "title": "整理輸出",
                        "kind": "task",
                        "description": "寫出摘要",
                        "tools": [{"name": "file.write"}, {"name": "unknown"}],
                        "output": {"type": "md", "extract": "best_effort"},
                    },
                ],
                "edges": [{"from": "N1", "to": "N2"}],
            },
            ensure_ascii=False,
        )

        llm = FakeLLMClient([pass1, pass2, pass3])
        graph = generate_taskgraph2_with_llm(
            "請幫我先找資料再整理成摘要",
            llm_client=llm,
            available_tools=tools,
            available_skills=skills,
        )

        self.assertEqual(graph.schema_version, "2.0")
        validate_task_graph(graph)

        tool_names = {tool["name"] for tool in tools}
        for node in graph.nodes:
            for tool in node.tools:
                self.assertTrue(tool.name in tool_names or tool.name == "unknown")

        self.assertEqual(len(llm.calls), 3)

    def test_planner2_repair_once_when_validation_fails(self) -> None:
        tools = [{"name": "web.search", "description": "搜尋", "input_schema": {"type": "object"}}]
        skills: list[dict[str, object]] = []
        invalid_final = json.dumps(
            {
                "schema_version": "2.0",
                "objective": "",
                "session_defaults": {},
                "nodes": [],
                "edges": [],
            },
            ensure_ascii=False,
        )
        repaired = json.dumps(
            {
                "schema_version": "2.0",
                "objective": "修復後",
                "session_defaults": {},
                "nodes": [
                    {
                        "id": "N1",
                        "title": "查資料",
                        "kind": "task",
                        "description": "收集資料",
                        "tools": [{"name": "web.search"}],
                        "output": {"type": "text", "extract": "best_effort"},
                    }
                ],
                "edges": [],
            },
            ensure_ascii=False,
        )

        llm = FakeLLMClient([repaired, repaired, invalid_final, repaired])
        graph = generate_taskgraph2_with_llm(
            "做規劃",
            llm_client=llm,
            available_tools=tools,
            available_skills=skills,
        )

        self.assertEqual(graph.schema_version, "2.0")
        validate_task_graph(graph)
        self.assertEqual(len(llm.calls), 4)
        self.assertIn("repair_error", llm.calls[-1][1]["content"])


if __name__ == "__main__":
    unittest.main()
