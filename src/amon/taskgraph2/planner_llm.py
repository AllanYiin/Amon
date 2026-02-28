"""Planner2 LLM pipeline for generating TaskGraph 2.0."""

from __future__ import annotations

import json
import logging
from typing import Any

from .llm import TaskGraphLLMClient, build_default_llm_client
from .schema import TaskGraph, validate_task_graph
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
        return _parse_and_validate(final_raw)
    except ValueError as exc:
        repaired_raw = _repair_pass(
            client,
            model,
            repair_error=str(exc),
            previous_raw=final_raw,
            available_tools=tools,
            available_skills=skills,
        )
        return _parse_and_validate(repaired_raw)


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
