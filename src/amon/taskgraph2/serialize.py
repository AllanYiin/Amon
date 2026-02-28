"""TaskGraph 2.0 serialization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .schema import (
    TaskEdge,
    TaskGraph,
    TaskNode,
    TaskNodeGuardrails,
    TaskNodeLLM,
    TaskNodeOutput,
    TaskNodeRetry,
    TaskNodeTimeout,
    TaskNodeTool,
    validate_task_graph,
)


def dumps_task_graph(graph: TaskGraph) -> str:
    validate_task_graph(graph)
    payload = asdict(graph)
    payload["edges"] = [
        {"from": edge["from_node"], "to": edge["to_node"], "when": edge.get("when")}
        for edge in payload.get("edges", [])
    ]
    for edge in payload["edges"]:
        if edge.get("when") is None:
            edge.pop("when", None)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_task_graph(text: str) -> TaskGraph:
    candidate = _strip_code_fences(text)
    payload_obj = _extract_outer_json_object(candidate)
    if payload_obj is None:
        raise ValueError("TaskGraph JSON 格式錯誤：找不到合法 JSON object")

    try:
        payload = json.loads(payload_obj)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TaskGraph JSON 格式錯誤：{exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("TaskGraph 必須是 object")

    nodes_payload = payload.get("nodes")
    if not isinstance(nodes_payload, list):
        raise ValueError("nodes 必須是 list")
    nodes: list[TaskNode] = []
    for raw in nodes_payload:
        if not isinstance(raw, dict):
            raise ValueError("node 必須是 object")
        tools_raw = raw.get("tools")
        if tools_raw is None:
            tools_raw = []
        if not isinstance(tools_raw, list):
            raise ValueError("node.tools 必須是 list")
        tools = [_to_tool(item) for item in tools_raw]
        steps_raw = raw.get("steps")
        if steps_raw is None:
            steps_raw = []
        if not isinstance(steps_raw, list):
            raise ValueError("node.steps 必須是 list")
        steps = [_to_step(item) for item in steps_raw]
        output_raw = raw.get("output")
        if output_raw is None:
            output_raw = {}
        if not isinstance(output_raw, dict):
            raise ValueError("node.output 必須是 object")

        guardrails_raw = raw.get("guardrails")
        if guardrails_raw is None:
            guardrails_raw = {}
        if not isinstance(guardrails_raw, dict):
            raise ValueError("node.guardrails 必須是 object")

        retry_raw = raw.get("retry")
        if retry_raw is None:
            retry_raw = {}
        if not isinstance(retry_raw, dict):
            raise ValueError("node.retry 必須是 object")

        timeout_raw = raw.get("timeout")
        if timeout_raw is None:
            timeout_raw = {}
        if not isinstance(timeout_raw, dict):
            raise ValueError("node.timeout 必須是 object")

        llm_raw = raw.get("llm")
        if llm_raw is None:
            llm_raw = {}
        if not isinstance(llm_raw, dict):
            raise ValueError("node.llm 必須是 object")

        nodes.append(
            TaskNode(
                id=str(raw.get("id") or ""),
                title=str(raw.get("title") or ""),
                kind=str(raw.get("kind") or ""),
                description=str(raw.get("description") or ""),
                role=str(raw.get("role") or ""),
                reads=[str(item) for item in (raw.get("reads") or [])],
                writes={str(k): str(v) for k, v in dict(raw.get("writes") or {}).items()},
                llm=TaskNodeLLM(
                    model=_to_optional_str(llm_raw.get("model")),
                    mode=_to_optional_str(llm_raw.get("mode")),
                    temperature=_to_optional_float(llm_raw.get("temperature")),
                    max_tokens=_to_optional_int(llm_raw.get("max_tokens")),
                    tool_choice=_to_optional_str(llm_raw.get("tool_choice")),
                    enable_tools=bool(llm_raw.get("enable_tools", False)),
                ),
                tools=tools,
                steps=steps,
                output=TaskNodeOutput(
                    type=str(output_raw.get("type") or "text"),
                    extract=str(output_raw.get("extract") or "best_effort"),
                    schema=dict(output_raw.get("schema")) if isinstance(output_raw.get("schema"), dict) else None,
                ),
                guardrails=TaskNodeGuardrails(
                    allow_interrupt=bool(guardrails_raw.get("allow_interrupt", True)),
                    require_human_approval=bool(guardrails_raw.get("require_human_approval", False)),
                    boundaries=[str(item) for item in (guardrails_raw.get("boundaries") or [])],
                ),
                retry=TaskNodeRetry(
                    max_attempts=int(retry_raw.get("max_attempts", 1)),
                    backoff_s=float(retry_raw.get("backoff_s", 1.0)),
                    jitter_s=float(retry_raw.get("jitter_s", 0.0)),
                ),
                timeout=TaskNodeTimeout(
                    inactivity_s=int(timeout_raw.get("inactivity_s", 60)),
                    hard_s=int(timeout_raw.get("hard_s", 300)),
                ),
            )
        )

    edges_raw = payload.get("edges")
    if not isinstance(edges_raw, list):
        raise ValueError("edges 必須是 list")
    edges: list[TaskEdge] = []
    for item in edges_raw:
        if not isinstance(item, dict):
            raise ValueError("edge 必須是 object")
        edges.append(
            TaskEdge(
                from_node=str(item.get("from") or ""),
                to_node=str(item.get("to") or ""),
                when=_to_optional_str(item.get("when")),
            )
        )

    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("metadata 必須是 object")

    graph = TaskGraph(
        schema_version=str(payload.get("schema_version") or ""),
        objective=str(payload.get("objective") or ""),
        session_defaults=dict(payload.get("session_defaults") or {}),
        nodes=nodes,
        edges=edges,
        metadata=dict(metadata) if isinstance(metadata, dict) else None,
    )
    validate_task_graph(graph)
    return graph


def _to_tool(item: Any) -> TaskNodeTool:
    if not isinstance(item, dict):
        raise ValueError("node.tools 項目必須是 object")
    args_schema_hint = item.get("args_schema_hint")
    if args_schema_hint is not None and not isinstance(args_schema_hint, dict):
        raise ValueError("tool.args_schema_hint 必須是 object")
    return TaskNodeTool(
        name=str(item.get("name") or ""),
        when_to_use=_to_optional_str(item.get("when_to_use")),
        required=bool(item.get("required", False)),
        args_schema_hint=dict(args_schema_hint) if isinstance(args_schema_hint, dict) else None,
    )


def _to_step(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("node.steps 項目必須是 object")
    return dict(item)


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            body = lines[1:-1]
            if lines[0].strip().lower() in {"```json", "```jsonc", "```javascript", "```"}:
                return "\n".join(body).strip()
    return cleaned


def _extract_outer_json_object(text: str) -> str | None:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return text
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[start : idx + 1]
                    try:
                        parsed = json.loads(snippet)
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict):
                        return snippet
                    break
        start = text.find("{", start + 1)
    return None


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _to_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
