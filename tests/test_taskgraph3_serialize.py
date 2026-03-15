from __future__ import annotations

import json
import unittest
from pathlib import Path

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
from amon.taskgraph3.validate import validate_v3_graph_json


class TaskGraph3SerializeTests(unittest.TestCase):
    def test_round_trip_serialize_validate_load(self) -> None:
        graph = GraphDefinition(
            nodes=[
                TaskNode(
                    id="agent-1",
                    title="分析",
                    config={"customFlag": True, "legacyExecution": "SINGLE"},
                    guardrails={"mode": "warn"},
                    task_boundaries=["design"],
                    task_spec=TaskSpec(
                        executor="agent",
                        agent=AgentTaskConfig(
                            system_prompt="你是分析師",
                            prompt="summarize",
                            instructions="zh-TW",
                            model="gpt-4.1",
                            allowed_tools=["web.search"],
                        ),
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
        self.assertEqual(agent["taskSpec"]["agent"]["systemPrompt"], "你是分析師")
        self.assertEqual(agent["taskSpec"]["agent"]["model"], "gpt-4.1")
        self.assertEqual(agent["taskSpec"]["agent"]["allowedTools"], ["web.search"])
        self.assertEqual(agent["taskSpec"]["inputBindings"][0]["source"], "variable")
        self.assertEqual(agent["taskSpec"]["display"]["todoHint"], "先讀資料")
        self.assertEqual(agent["config"], {"customFlag": True})
        self.assertEqual(agent["guardrails"], {"mode": "warn"})
        self.assertEqual(agent["taskBoundaries"], ["design"])
        self.assertNotIn("legacy", json.dumps(payload, ensure_ascii=False))

    def test_fixture_with_agent_tool_artifact_is_valid(self) -> None:
        fixture = json.loads(Path("fixtures/graphs/task-spec-cases.v3.json").read_text(encoding="utf-8"))
        validate_v3_graph_json(fixture)
        self.assertTrue(any(node["node_type"] == "ARTIFACT" for node in fixture["nodes"]))

    def test_validate_rejects_legacy_payload_keys(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "agent-1",
                    "node_type": "TASK",
                    "title": "分析",
                    "config": {"legacyExecution": "SINGLE"},
                    "taskSpec": {
                        "executor": "agent",
                        "agent": {"prompt": "整理重點"},
                        "display": {"label": "分析任務"},
                        "runnable": True,
                    },
                }
            ],
            "edges": [],
        }

        with self.assertRaisesRegex(ValueError, "禁止 legacy 欄位"):
            validate_v3_graph_json(payload)


if __name__ == "__main__":
    unittest.main()
