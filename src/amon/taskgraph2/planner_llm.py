"""Planner2 LLM pipeline for generating TaskGraph 2.0."""

from __future__ import annotations

import json
import logging
from typing import Any

from .llm import TaskGraphLLMClient, build_default_llm_client
from .schema import TaskEdge, TaskGraph, TaskNode, TaskNodeOutput, validate_task_graph
from .serialize import loads_task_graph

logger = logging.getLogger(__name__)


def generate_taskgraph2_with_llm(
    user_message: str,
    *,
    llm_client: TaskGraphLLMClient | None = None,
    model: str | None = None,
    available_tools: list[dict[str, Any]] | None = None,
    available_skills: list[dict[str, Any]] | None = None,
) -> TaskGraph:
    normalized_message = " ".join((user_message or "").split())
    if not normalized_message:
        raise ValueError("user_message 不可為空")

    tools = _normalize_available_tools(available_tools)
    skills = _normalize_available_skills(available_skills)
    client = llm_client or build_default_llm_client(model=model)

    draft_raw = _planner_pass(
        client,
        model,
        message=normalized_message,
        available_tools=tools,
        available_skills=skills,
    )
    advisor_raw = _tool_advisor_pass(client, model, draft_raw=draft_raw, available_tools=tools)
    final_raw = _tool_librarian_pass(client, model, advisor_raw=advisor_raw, available_tools=tools)

    try:
        graph = _parse_and_validate(final_raw)
    except ValueError as exc:
        repaired_raw = _repair_pass(
            client,
            model,
            repair_error=str(exc),
            previous_raw=final_raw,
            available_tools=tools,
            available_skills=skills,
        )
        graph = _parse_and_validate(repaired_raw)

    return _ensure_todo_bootstrap_contract(graph)


def _ensure_todo_bootstrap_contract(graph: TaskGraph) -> TaskGraph:
    """Ensure TaskGraph2 starts from TODO generation and downstream nodes can depend on it."""
    todo_node = next((node for node in graph.nodes if "todo_markdown" in node.writes), None)
    if todo_node is None:
        existing_ids = {node.id for node in graph.nodes}
        todo_id = "N_TODO"
        suffix = 1
        while todo_id in existing_ids:
            suffix += 1
            todo_id = f"N_TODO_{suffix}"
        todo_node = TaskNode(
            id=todo_id,
            title="產生 TODO 清單",
            kind="task",
            description=(
                "你是專案經理。請先輸出 TODO list，拆解任務並標記初始狀態都為 [ ]。"
                "請使用繁體中文 markdown，第一行必須是『專案經理：』。"
            ),
            role="專案經理",
            writes={"todo_markdown": "docs/TODO.md"},
            output=TaskNodeOutput(type="md", extract="best_effort"),
        )
        graph.nodes.insert(0, todo_node)

    review_node = _ensure_todo_review_node(graph, todo_node.id)
    outgoing = {edge.to_node for edge in graph.edges if edge.from_node == review_node.id}
    incoming_count = {node.id: 0 for node in graph.nodes}
    for edge in graph.edges:
        incoming_count[edge.to_node] = incoming_count.get(edge.to_node, 0) + 1

    for node in graph.nodes:
        if node.id == todo_node.id:
            continue
        if incoming_count.get(node.id, 0) == 0 and node.id not in outgoing:
            graph.edges.append(TaskEdge(from_node=review_node.id, to_node=node.id))
        if node.id not in {todo_node.id, review_node.id} and "todo_task_nodes_review" not in node.reads:
            if incoming_count.get(node.id, 0) == 0 or any(
                edge.from_node == review_node.id and edge.to_node == node.id for edge in graph.edges
            ):
                node.reads.append("todo_task_nodes_review")

    validate_task_graph(graph)
    return graph


def _ensure_todo_review_node(graph: TaskGraph, todo_node_id: str) -> TaskNode:
    review_node = next((node for node in graph.nodes if "todo_task_nodes_review" in node.writes), None)
    if review_node is None:
        existing_ids = {node.id for node in graph.nodes}
        review_id = "N_TODO_REVIEW"
        suffix = 1
        while review_id in existing_ids:
            suffix += 1
            review_id = f"N_TODO_REVIEW_{suffix}"
        review_node = TaskNode(
            id=review_id,
            title="審核 TODO 並展開任務節點",
            kind="task",
            description=(
                "請先審核 docs/TODO.md 的每個待辦項目是否完整，再為每個項目產生可執行任務節點內容。"
                "每個項目請保留一段『中文短說明』，且輸出必須是 JSON array。"
            ),
            role="流程設計師",
            reads=["todo_markdown"],
            writes={"todo_task_nodes_review": "docs/TODO.nodes.review.json"},
            output=TaskNodeOutput(type="json", extract="best_effort"),
        )
        insert_index = next((idx + 1 for idx, node in enumerate(graph.nodes) if node.id == todo_node_id), 0)
        graph.nodes.insert(insert_index, review_node)

    if "todo_markdown" not in review_node.reads:
        review_node.reads.append("todo_markdown")

    if not any(edge.from_node == todo_node_id and edge.to_node == review_node.id for edge in graph.edges):
        graph.edges.append(TaskEdge(from_node=todo_node_id, to_node=review_node.id))

    return review_node


def _planner_pass(
    llm_client: TaskGraphLLMClient,
    model: str | None,
    *,
    message: str,
    available_tools: list[dict[str, Any]],
    available_skills: list[dict[str, Any]],
) -> str:
    payload = {
        "message": message,
        "schema_definition": _taskgraph2_schema_definition(),
        "available_tools": available_tools,
        "available_skills": available_skills,
    }
    messages = [
        {"role": "system", "content": _planner_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return _collect_stream(llm_client, messages, model)


def _tool_advisor_pass(
    llm_client: TaskGraphLLMClient,
    model: str | None,
    *,
    draft_raw: str,
    available_tools: list[dict[str, Any]],
) -> str:
    payload = {
        "draft_graph": draft_raw,
        "available_tools": available_tools,
        "output_requirement": "優先輸出修正版完整 graph JSON；若無法，輸出 JSON object 並包含 graph 欄位",
    }
    messages = [
        {"role": "system", "content": _tool_advisor_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return _collect_stream(llm_client, messages, model)


def _tool_librarian_pass(
    llm_client: TaskGraphLLMClient,
    model: str | None,
    *,
    advisor_raw: str,
    available_tools: list[dict[str, Any]],
) -> str:
    payload = {
        "candidate_graph": advisor_raw,
        "available_tools": available_tools,
        "tool_contract": "node.tools[].name 必須存在於 available_tools.name；未知工具必須命名為 unknown",
    }
    messages = [
        {"role": "system", "content": _tool_librarian_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return _collect_stream(llm_client, messages, model)


def _repair_pass(
    llm_client: TaskGraphLLMClient,
    model: str | None,
    *,
    repair_error: str,
    previous_raw: str,
    available_tools: list[dict[str, Any]],
    available_skills: list[dict[str, Any]],
) -> str:
    payload = {
        "repair_error": repair_error,
        "previous_raw": previous_raw,
        "schema_definition": _taskgraph2_schema_definition(),
        "available_tools": available_tools,
        "available_skills": available_skills,
    }
    messages = [
        {"role": "system", "content": _repair_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return _collect_stream(llm_client, messages, model)


def _parse_and_validate(raw: str) -> TaskGraph:
    graph = loads_task_graph(_extract_graph_json(raw))
    validate_task_graph(graph)
    return graph


def _extract_graph_json(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Planner2 回傳為空")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    if not isinstance(payload, dict):
        return text
    if "graph" in payload and isinstance(payload["graph"], dict):
        return json.dumps(payload["graph"], ensure_ascii=False)
    return text


def _collect_stream(
    llm_client: TaskGraphLLMClient,
    messages: list[dict[str, str]],
    model: str | None,
) -> str:
    chunks: list[str] = []
    for token in llm_client.generate_stream(messages, model=model):
        chunks.append(token)
    return "".join(chunks).strip()


def _normalize_available_tools(available_tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in available_tools or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("tool_name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "description": str(item.get("description") or item.get("when_to_use") or ""),
                "input_schema": item.get("input_schema") or item.get("args_schema_hint") or {},
            }
        )
    return normalized


def _normalize_available_skills(available_skills: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in available_skills or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "description": str(item.get("description") or ""),
                "targets": item.get("targets") or item.get("inject_to") or [],
            }
        )
    return normalized


def _planner_system_prompt() -> str:
    return (
        "你是 Planner2。"
        "你只能輸出符合 TaskGraph 2.0 schema 的單一 JSON object，不得輸出 markdown/code fence/說明。"
        "務必使用 schema_version=2.0，並讓圖為 DAG。"
        "必須先有一個 TODO bootstrap 節點，寫入 writes.todo_markdown='docs/TODO.md'。"
        "TODO 清單內每個項目的短說明必須使用繁體中文。"
        "在 TODO 節點後必須有一個 review 節點，讀取 todo_markdown 並產生 writes.todo_task_nodes_review。"
        "其餘執行節點必須依賴 review 節點，且可透過 reads 讀取 todo_task_nodes_review。"
    )


def _tool_advisor_system_prompt() -> str:
    return (
        "你是工具顧問（tool_advisor）。"
        "你只能輸出 JSON。請審查 draft graph 的工具選擇與參數是否合理。"
        "優先直接輸出修正版完整 TaskGraph 2.0 JSON。"
    )


def _tool_librarian_system_prompt() -> str:
    return (
        "你是工具庫管家（tool_librarian）。"
        "你只能輸出最終 TaskGraph 2.0 JSON。"
        "graph 內的 node.tools[].name 必須存在於 available_tools.name；否則改為 unknown。"
    )


def _repair_system_prompt() -> str:
    return (
        "你是 TaskGraph2 JSON 修復器。"
        "你只能輸出修復後的單一 JSON object，不得輸出任何額外文字。"
        "請依據 repair_error 修正 previous_raw，讓其可被 TaskGraph2 loads/validate 接受。"
    )


def _taskgraph2_schema_definition() -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "objective": "string",
        "session_defaults": {
            "language": "string",
            "timezone": "string",
            "budget_tokens": 0,
        },
        "nodes": [
            {
                "id": "N1",
                "title": "string",
                "kind": "task|decision|io",
                "description": "string",
                "role": "string",
                "reads": ["string"],
                "writes": {"artifact_key": "string"},
                "llm": {
                    "model": "string|null",
                    "mode": "single|self_critique|team|plan_execute|null",
                    "temperature": 0.2,
                    "max_tokens": 1000,
                    "tool_choice": "auto|required|none|null",
                },
                "tools": [
                    {
                        "name": "string",
                        "when_to_use": "string|null",
                        "required": False,
                        "args_schema_hint": {},
                    }
                ],
                "steps": [
                    {
                        "type": "tool|llm",
                        "tool_name": "string",
                        "args": {},
                        "store_as": "string",
                    }
                ],
                "output": {
                    "type": "json|md|text|artifact",
                    "extract": "strict|best_effort",
                    "schema": {},
                },
                "guardrails": {
                    "allow_interrupt": True,
                    "require_human_approval": False,
                    "boundaries": ["string"],
                },
                "retry": {"max_attempts": 1, "backoff_s": 1.0, "jitter_s": 0.0},
                "timeout": {"inactivity_s": 60, "hard_s": 300},
            }
        ],
        "edges": [{"from": "N1", "to": "N2", "when": "string|null"}],
        "metadata": {"planner": "planner2", "notes": "string"},
    }
