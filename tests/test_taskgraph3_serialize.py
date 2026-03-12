from __future__ import annotations

import json
import unittest
from pathlib import Path

from amon.taskgraph3.migrate import validate_v3_graph_json
from amon.taskgraph3.payloads import (
    AgentTaskConfig,
    ArtifactOutput,
    InputBinding,
    TaskDisplayMetadata,
    TaskSpec,
    ToolCallSpec,
    ToolTaskConfig,
)
from amon.taskgraph3.schema import GraphDefinition, GraphEdge, TaskNode
from amon.taskgraph3.serialize import dumps_graph_definition


class TaskGraph3SerializeTests(unittest.TestCase):
    def test_round_trip_serialize_validate_load(self) -> None:
        graph = GraphDefinition(
            nodes=[
                TaskNode(
                    id="agent-1",
                    title="分析",
                    task_spec=TaskSpec(
                        executor="agent",
                        agent=AgentTaskConfig(prompt="summarize", instructions="zh-TW", model="gpt-4.1", allowed_tools=["web.search"]),
                        input_bindings=[InputBinding(source="variable", key="topic", value="taskgraph")],
                        artifacts=[ArtifactOutput(name="summary", media_type="text/markdown", required=True)],
                        display=TaskDisplayMetadata(label="分析任務", summary="產生摘要", todo_hint="先讀資料", tags=["demo"]),
                    ),
                ),
                TaskNode(
                    id="tool-1",
                    title="查詢",
                    task_spec=TaskSpec(
                        executor="tool",
                        tool=ToolTaskConfig(tools=[ToolCallSpec(name="search", args={"q": "taskgraph"}, when_to_use="needs facts")], skills=["skill-installer"]),
                    ),
                ),
            ],
            edges=[GraphEdge(from_node="agent-1", to_node="tool-1", edge_type="CONTROL", kind="DEPENDS_ON")],
        )

        payload = json.loads(dumps_graph_definition(graph))
        validate_v3_graph_json(payload)

        agent = next(item for item in payload["nodes"] if item["id"] == "agent-1")
        self.assertEqual(agent["taskSpec"]["agent"]["model"], "gpt-4.1")
        self.assertEqual(agent["taskSpec"]["agent"]["allowedTools"], ["web.search"])
        self.assertEqual(agent["taskSpec"]["inputBindings"][0]["source"], "variable")
        self.assertEqual(agent["taskSpec"]["display"]["todoHint"], "先讀資料")

    def test_fixture_with_agent_tool_artifact_is_valid(self) -> None:
        fixture = json.loads(Path("fixtures/graphs/task-spec-cases.v3.json").read_text(encoding="utf-8"))
        validate_v3_graph_json(fixture)
        self.assertTrue(any(node["node_type"] == "ARTIFACT" for node in fixture["nodes"]))


if __name__ == "__main__":
    unittest.main()
