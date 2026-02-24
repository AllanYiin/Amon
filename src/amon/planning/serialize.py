"""PlanGraph serialization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .schema import PlanContext, PlanGraph, PlanNode, infer_edges_from_depends_on, validate_plan_graph


def dumps_plan(plan: PlanGraph) -> str:
    validate_plan_graph(plan)
    payload = asdict(plan)
    if not payload.get("edges"):
        payload["edges"] = infer_edges_from_depends_on(plan.nodes)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_plan(text: str) -> PlanGraph:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"PlanGraph JSON 格式錯誤：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("PlanGraph 必須是 object")

    context_payload = payload.get("context")
    context = None
    if isinstance(context_payload, dict):
        context = PlanContext(
            assumptions=list(context_payload.get("assumptions") or []),
            constraints=list(context_payload.get("constraints") or []),
            glossary=dict(context_payload.get("glossary") or {}),
        )

    nodes_payload = payload.get("nodes")
    if not isinstance(nodes_payload, list):
        raise ValueError("nodes 必須是 list")
    nodes: list[PlanNode] = []
    for raw in nodes_payload:
        if not isinstance(raw, dict):
            raise ValueError("node 必須是 object")
        node = PlanNode(
            id=str(raw.get("id") or ""),
            title=str(raw.get("title") or ""),
            goal=str(raw.get("goal") or ""),
            definition_of_done=[str(item) for item in (raw.get("definition_of_done") or [])],
            depends_on=[str(item) for item in (raw.get("depends_on") or [])],
            requires_llm=bool(raw.get("requires_llm") or False),
            llm=dict(raw.get("llm")) if isinstance(raw.get("llm"), dict) else None,
            tools=_coerce_list_of_dict(raw.get("tools")),
            skills=[str(item) for item in (raw.get("skills") or [])],
            expected_artifacts=_coerce_list_of_dict(raw.get("expected_artifacts")),
        )
        nodes.append(node)

    edges = _coerce_edges(payload.get("edges"))
    if not edges:
        edges = infer_edges_from_depends_on(nodes)

    plan = PlanGraph(
        schema_version=str(payload.get("schema_version") or ""),
        objective=str(payload.get("objective") or ""),
        nodes=nodes,
        edges=edges,
        context=context,
    )
    validate_plan_graph(plan)
    return plan


def _coerce_list_of_dict(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("欄位必須是 list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("list 項目必須是 object")
        result.append(dict(item))
    return result


def _coerce_edges(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("edges 必須是 list")
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("edge 必須是 object")
        result.append({"from": str(item.get("from") or ""), "to": str(item.get("to") or "")})
    return result
