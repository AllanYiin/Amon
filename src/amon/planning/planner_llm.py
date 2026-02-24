"""LLM planner for generating PlanGraph TODO graphs."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Protocol

from amon.config import ConfigLoader
from amon.models import build_provider

from .schema import PlanContext, PlanGraph, PlanNode
from .serialize import loads_plan

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
) -> PlanGraph:
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
            return loads_plan(_strip_code_fences(raw))
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
            return loads_plan(_strip_code_fences(repaired))
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
        "plan_schema": _plan_schema_definition(),
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
            "你是 PlanGraph JSON 修復器。"
            "只輸出符合 PlanGraph schema 的 JSON，不得輸出 markdown 或解釋。"
            "請根據錯誤原因修正上一版輸出，使其可被嚴格 JSON parser 與 PlanGraph validator 接受。"
        )
    return (
        "你是 LLM Planner。"
        "你必須只輸出符合 PlanGraph schema 的 JSON，不得輸出 markdown、code fence、說明文字。"
        "先列 assumptions，再產生 TODO nodes（包含 depends_on），再為每個 node 補齊 tools/skills/llm prompt+instructions/DoD。"
        "所有欄位型別必須正確，schema_version 使用 1.0。"
    )


def _plan_schema_definition() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "objective": "string",
        "context": {
            "assumptions": ["string"],
            "constraints": ["string"],
            "glossary": {"term": "definition"},
        },
        "nodes": [
            {
                "id": "T1",
                "title": "string",
                "goal": "string",
                "definition_of_done": ["string"],
                "depends_on": ["T0"],
                "requires_llm": True,
                "llm": {"mode": "single|self_critique|team|plan_execute", "prompt": "string", "instructions": "string"},
                "tools": [{"tool_name": "string", "args_schema_hint": {}, "when_to_use": "string"}],
                "skills": ["string"],
                "expected_artifacts": [{"path": "docs/...", "type": "md|json|txt", "description": "string"}],
            }
        ],
        "edges": [{"from": "T1", "to": "T2"}],
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


def _minimal_plan(message: str) -> PlanGraph:
    return PlanGraph(
        schema_version="1.0",
        objective=message,
        nodes=[
            PlanNode(
                id="T1",
                title="釐清需求並產出初版",
                goal="先完成可執行的最小任務切分",
                definition_of_done=["產出初版 TODO", "標註後續需要資訊"],
                depends_on=[],
                requires_llm=True,
                llm={
                    "mode": "plan_execute",
                    "prompt": message,
                    "instructions": "先做最小可行拆解，再逐步細化。",
                },
                tools=[],
                skills=[],
                expected_artifacts=[{"path": "docs/TODO.md", "type": "md", "description": "最小任務清單"}],
            )
        ],
        edges=[],
        context=PlanContext(assumptions=["LLM planner fallback"], constraints=[], glossary={}),
    )
