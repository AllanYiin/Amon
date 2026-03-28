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
from amon.taskgraph3.validate import graph_definition_from_payload, validate_v3_graph_json


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

    def test_validate_normalizes_planner_executor_alias_to_agent(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "task_concept_alignment",
                    "node_type": "TASK",
                    "title": "概念對齊",
                    "taskSpec": {
                        "executor": "planner",
                        "agent": {
                            "prompt": "先查關鍵概念",
                            "instructions": "整理背景與風險",
                        },
                        "display": {"label": "概念對齊"},
                        "runnable": True,
                    },
                }
            ],
            "edges": [],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)
        task_node = next(node for node in graph.nodes if isinstance(node, TaskNode))
        self.assertEqual(task_node.task_spec.executor, "agent")

    def test_validate_marks_empty_tool_list_non_runnable(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "task_concept_alignment",
                    "node_type": "TASK",
                    "title": "概念對齊",
                    "taskSpec": {
                        "executor": "tool",
                        "tool": {"tools": []},
                        "display": {"label": "概念對齊"},
                        "runnable": True,
                    },
                }
            ],
            "edges": [],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)
        task_node = next(node for node in graph.nodes if isinstance(node, TaskNode))
        self.assertEqual(task_node.task_spec.executor, "tool")
        self.assertEqual(task_node.task_spec.tool.tools, [])
        self.assertFalse(task_node.task_spec.runnable)
        self.assertIn("tool 缺少可執行工具定義", task_node.task_spec.non_runnable_reason)

    def test_validate_normalizes_empty_agent_prompt_from_title(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "task_concept_alignment",
                    "node_type": "TASK",
                    "title": "概念對齊",
                    "taskSpec": {
                        "executor": "agent",
                        "agent": {},
                        "display": {"label": ""},
                        "runnable": True,
                    },
                }
            ],
            "edges": [],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)
        task_node = next(node for node in graph.nodes if isinstance(node, TaskNode))
        self.assertEqual(task_node.task_spec.agent.prompt, "完成「概念對齊」")

    def test_validate_normalizes_empty_node_id_from_title(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "",
                    "node_type": "TASK",
                    "title": "概念對齊",
                    "taskSpec": {
                        "executor": "tool",
                        "tool": {"tools": [{"name": "web.search", "args": {}}]},
                        "display": {"label": "概念對齊"},
                        "runnable": True,
                    },
                },
                {
                    "id": "",
                    "node_type": "TASK",
                    "title": "概念對齊",
                    "taskSpec": {
                        "executor": "agent",
                        "agent": {"prompt": "完成"},
                        "display": {"label": "概念對齊"},
                        "runnable": True,
                    },
                },
            ],
            "edges": [],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)

        self.assertEqual([node.id for node in graph.nodes if isinstance(node, TaskNode)], ["概念對齊", "概念對齊_2"])

    def test_validate_normalizes_duplicate_ids_blank_titles_and_blank_edge_ids(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "task_dup",
                    "node_type": "TASK",
                    "title": " ",
                    "objective": "整理概念",
                    "taskSpec": {
                        "executor": "agent",
                        "agent": {"prompt": "完成"},
                        "display": {"label": ""},
                        "runnable": True,
                    },
                },
                {
                    "id": "task_dup",
                    "node_type": "TASK",
                    "title": "需求整理",
                    "taskSpec": {
                        "executor": "agent",
                        "agent": {"prompt": "完成"},
                        "display": {"label": "需求整理"},
                        "runnable": True,
                    },
                },
            ],
            "edges": [
                {"id": " ", "type": "CONTROL", "from": "task_dup", "to": "task_dup_2", "kind": "DEPENDS_ON"},
                {"id": " ", "type": "CONTROL", "from": "task_dup", "to": "task_dup_2", "kind": "DEPENDS_ON"},
            ],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)

        task_nodes = [node for node in graph.nodes if isinstance(node, TaskNode)]
        self.assertEqual([node.id for node in task_nodes], ["task_dup", "task_dup_2"])
        self.assertEqual(task_nodes[0].title, "整理概念")
        self.assertEqual([edge.id for edge in graph.edges], ["task_dup->task_dup_2:control", "task_dup->task_dup_2:control_2"])

    def test_validate_normalizes_task_spec_alias_keys_and_whitespace(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "task_tool",
                    "node_type": "TASK",
                    "title": "工具查詢",
                    "taskSpec": {
                        "executor": "tool",
                        "tool": {
                            "tools": [
                                {
                                    "toolId": " web.search ",
                                    "arguments": {"query": "Amon"},
                                    "when_to_use": " 需要查證 ",
                                }
                            ],
                            "skillNames": [" concept-alignment "],
                        },
                        "input_bindings": [
                            {
                                "bindingSource": "upstream",
                                "targetPortKey": " subject ",
                                "from_node": " research ",
                                "sourcePort": " final_text ",
                            }
                        ],
                        "artifacts": [{"artifactId": " summary.md ", "media_type": " text/markdown "}],
                        "display": {"label": "  ", "todo_hint": " 先查證 "},
                        "runnable": True,
                    },
                }
            ],
            "edges": [],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)
        task_node = next(node for node in graph.nodes if isinstance(node, TaskNode))

        self.assertEqual(task_node.task_spec.tool.tools[0].name, "web.search")
        self.assertEqual(task_node.task_spec.tool.tools[0].args, {"query": "Amon"})
        self.assertEqual(task_node.task_spec.tool.tools[0].when_to_use, "需要查證")
        self.assertEqual(task_node.task_spec.tool.skills, ["concept-alignment"])
        self.assertEqual(task_node.task_spec.input_bindings[0].key, "subject")
        self.assertEqual(task_node.task_spec.input_bindings[0].from_node, "research")
        self.assertEqual(task_node.task_spec.input_bindings[0].port, "final_text")
        self.assertEqual(task_node.task_spec.artifacts[0].name, "summary.md")
        self.assertEqual(task_node.task_spec.display.todo_hint, "先查證")
        self.assertEqual(task_node.task_spec.display.label, "工具查詢")

    def test_validate_marks_empty_sandbox_command_non_runnable(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "task_shell",
                    "node_type": "TASK",
                    "title": "執行命令",
                    "taskSpec": {
                        "executor": "sandbox_run",
                        "sandboxRun": {"command": ""},
                        "display": {"label": "執行命令"},
                        "runnable": True,
                    },
                }
            ],
            "edges": [],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)
        task_node = next(node for node in graph.nodes if isinstance(node, TaskNode))
        self.assertFalse(task_node.task_spec.runnable)
        self.assertIn("sandbox_run 缺少 command", task_node.task_spec.non_runnable_reason)

    def test_validate_tool_node_without_tool_calls_marks_non_runnable(self) -> None:
        payload = {
            "version": "taskgraph.v3",
            "nodes": [
                {
                    "id": "task_search",
                    "type": "tool",
                    "title": "查資料",
                    "config": {"toolCalls": []},
                }
            ],
            "edges": [],
        }

        validate_v3_graph_json(payload)
        graph = graph_definition_from_payload(payload)
        task_node = next(node for node in graph.nodes if isinstance(node, TaskNode))
        self.assertEqual(task_node.task_spec.tool.tools, [])
        self.assertFalse(task_node.task_spec.runnable)
        self.assertIn("tool 缺少 toolCalls 定義", task_node.task_spec.non_runnable_reason)


if __name__ == "__main__":
    unittest.main()
