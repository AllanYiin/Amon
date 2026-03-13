"""LLM planner for generating TaskGraph v3 TODO graphs."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Protocol

from amon.config import ConfigLoader
from amon.models import build_provider

from amon.taskgraph3.payloads import AgentTaskConfig, ArtifactOutput, TaskDisplayMetadata, TaskSpec, task_spec_from_payload
from amon.taskgraph3.schema import ArtifactNode, GateNode, GateRoute, GraphDefinition, GraphEdge, GroupNode, TaskNode, validate_graph_definition
from amon.taskgraph3.validate import graph_definition_from_payload

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


def generate_plan_with_llm(
    message: str,
    *,
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
    available_tools: list[dict[str, Any]] | None = None,
    available_skills: list[dict[str, Any]] | None = None,
) -> GraphDefinition:
    normalized = " ".join((message or "").split())
    if not normalized:
        return _minimal_plan("未提供任務描述")

    try:
        client = llm_client
        selected_model = model
        if client is None:
            client, selected_model = _build_default_client(project_id=project_id, model=model)

        raw = _request_plan(
            client,
            selected_model,
            message=normalized,
            available_tools=available_tools,
            available_skills=available_skills,
            repair_error=None,
            previous_raw=None,
        )
        try:
            return _loads_graph_definition(_strip_code_fences(raw))
        except ValueError as exc:
            repaired = _request_plan(
                client,
                selected_model,
                message=normalized,
                available_tools=available_tools,
                available_skills=available_skills,
                repair_error=str(exc),
                previous_raw=raw,
            )
            return _loads_graph_definition(_strip_code_fences(repaired))
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM planner 失敗，改用最小計畫：%s", exc)
        return _minimal_plan(normalized)


def _request_plan(
    llm_client: LLMClient,
    model: str | None,
    *,
    message: str,
    available_tools: list[dict[str, Any]] | None,
    available_skills: list[dict[str, Any]] | None,
    repair_error: str | None,
    previous_raw: str | None,
) -> str:
    payload: dict[str, Any] = {
        "message": message,
        "graph_schema": _graph_schema_definition(),
        "available_tools": _normalize_available_tools(available_tools),
        "available_skills": _normalize_available_skills(available_skills),
    }
    if repair_error:
        payload["repair_error"] = repair_error
        payload["previous_raw"] = previous_raw or ""
    messages = [
        {"role": "system", "content": _planner_system_prompt(is_repair=bool(repair_error))},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return _collect_stream(llm_client, messages, model)


def _collect_stream(llm_client: LLMClient, messages: list[dict[str, str]], model: str | None) -> str:
    chunks: list[str] = []
    for token in llm_client.generate_stream(messages, model=model):
        chunks.append(token)
    return "".join(chunks).strip()


def _build_default_client(project_id: str | None, model: str | None) -> tuple[LLMClient, str | None]:
    config = ConfigLoader().resolve(project_id=project_id).effective
    provider_name = config.get("amon", {}).get("provider", "openai")
    provider_cfg = config.get("providers", {}).get(provider_name, {})
    selected_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
    provider = build_provider(provider_cfg, model=selected_model)
    return provider, selected_model


def _strip_code_fences(text: str) -> str:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def _planner_system_prompt(*, is_repair: bool) -> str:
    if is_repair:
        return (
            "你是 TaskGraph v3 JSON 修復器。"
            "只輸出符合 GraphDefinition schema 的 JSON，不得輸出 markdown 或解釋。"
            "請根據錯誤原因修正上一版輸出，使其可被嚴格 JSON parser 與 TaskGraph v3 validator 接受。"
        )
    return (
        "你是 LLM Planner。"
        "你必須只輸出符合 TaskGraph v3 GraphDefinition 的 JSON，不得輸出 markdown、code fence、說明文字。"
        "所有流程第一個 TASK 必須是概念對齊，先抽取關鍵概念並安排上網查證。"
        "每個 TASK 都要最小化可用工具；若 executor=agent，請在 agent.allowedTools 僅列出該節點真正需要的工具。"
        "每個高階 task 都應該是 TASK node 並含 taskSpec，executor 可用 agent/tool。"
        "expected_artifacts 要映射到 taskSpec.artifacts 並建立對應 ARTIFACT node + DATA/EMITS edge。"
        "所有欄位型別必須正確，version 固定使用 taskgraph.v3。"
    )


def _graph_schema_definition() -> dict[str, Any]:
    return {
        "version": "taskgraph.v3",
        "nodes": [
            {
                "id": "task-1",
                "node_type": "TASK",
                "title": "string",
                "taskSpec": {
                    "executor": "agent|tool",
                    "agent": {
                        "prompt": "string",
                        "instructions": "string",
                        "model": "string|null",
                        "allowedTools": ["string"],
                    },
                    "tool": {
                        "tools": [{"name": "string", "args": {}, "whenToUse": "string"}],
                        "skills": ["string"],
                    },
                    "artifacts": [{"name": "string", "mediaType": "string", "description": "string", "required": True}],
                    "display": {"label": "string", "summary": "string", "todoHint": "string", "tags": ["string"]},
                    "runnable": True,
                },
            }
        ],
        "edges": [{"from": "task-1", "to": "task-2", "edge_type": "CONTROL", "kind": "next"}],
    }


def _normalize_available_tools(available_tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in available_tools or []:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "name": str(item.get("name") or item.get("tool_name") or ""),
                "description": str(item.get("description") or item.get("when_to_use") or ""),
                "input_schema": item.get("input_schema") or item.get("args_schema_hint") or {},
            }
        )
    return result


def _normalize_available_skills(available_skills: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in available_skills or []:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "name": str(item.get("name") or ""),
                "description": str(item.get("description") or ""),
                "inject_to": item.get("inject_to") or item.get("targets") or [],
                "targets": item.get("targets") or item.get("inject_to") or [],
            }
        )
    return result


def _minimal_plan(message: str) -> GraphDefinition:
    return GraphDefinition(
        version="taskgraph.v3",
        nodes=[
            TaskNode(
                id="task-1",
                title="釐清需求並產出初版",
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(prompt=message, instructions="先做最小可行拆解，再逐步細化。"),
                    artifacts=[ArtifactOutput(name="todo", media_type="text/markdown", description="最小任務清單", required=True)],
                    display=TaskDisplayMetadata(label="釐清需求並產出初版", summary="先完成可執行的最小任務切分", todo_hint="產出初版 TODO；標註後續需要資訊"),
                    runnable=True,
                ),
            ),
            ArtifactNode(id="artifact-task-1-todo", title="docs/TODO.md"),
        ],
        edges=[GraphEdge(from_node="task-1", to_node="artifact-task-1-todo", edge_type="DATA", kind="EMITS")],
    )


def _loads_graph_definition(text: str) -> GraphDefinition:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TaskGraph JSON 格式錯誤：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("TaskGraph 必須是 object")
    graph = graph_definition_from_payload(payload)
    validate_graph_definition(graph)
    return graph


def _coerce_node(raw: Any):
    if not isinstance(raw, dict):
        raise ValueError("node 必須是 object")
    node_id = str(raw.get("id") or "")
    node_type = str(raw.get("node_type") or "").upper()
    title = str(raw.get("title") or "")
    if node_type == "TASK":
        spec_raw = raw.get("taskSpec")
        if not isinstance(spec_raw, dict):
            raise ValueError(f"TASK node 必須包含 taskSpec：{node_id}")
        return TaskNode(
            id=node_id,
            title=title,
            execution=str(raw.get("execution") or "SINGLE"),
            execution_config=raw.get("executionConfig") if isinstance(raw.get("executionConfig"), dict) else None,
            task_spec=task_spec_from_payload(spec_raw),
            task_boundaries=[str(item) for item in (raw.get("taskBoundaries") or [])] if isinstance(raw.get("taskBoundaries"), list) else None,
            guardrails=raw.get("guardrails") if isinstance(raw.get("guardrails"), dict) else None,
        )
    if node_type == "ARTIFACT":
        return ArtifactNode(id=node_id, title=title)
    if node_type == "GROUP":
        return GroupNode(id=node_id, title=title, children=[str(item) for item in (raw.get("children") or [])])
    if node_type == "GATE":
        routes = []
        for item in raw.get("routes") or []:
            if not isinstance(item, dict):
                raise ValueError(f"gate route 必須是 object：{node_id}")
            routes.append(GateRoute(on_outcome=str(item.get("onOutcome") or ""), to_node=str(item.get("toNode") or "")))
        return GateNode(id=node_id, title=title, routes=routes)
    raise ValueError(f"不支援的 node_type：{node_type or '<empty>'}")


def _coerce_edge(raw: Any) -> GraphEdge:
    if not isinstance(raw, dict):
        raise ValueError("edge 必須是 object")
    return GraphEdge(
        from_node=str(raw.get("from") or raw.get("from_node") or ""),
        to_node=str(raw.get("to") or raw.get("to_node") or ""),
        edge_type=str(raw.get("edge_type") or "CONTROL"),
        kind=str(raw.get("kind") or "next"),
    )
