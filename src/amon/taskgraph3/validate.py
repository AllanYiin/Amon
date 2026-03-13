"""Validation helpers for TaskGraph v3 JSON payloads."""

from __future__ import annotations

from typing import Any

from .payloads import task_spec_from_payload
from .schema import GraphDefinition, GraphEdge, OutputContract, OutputPort, RuntimeCapabilities, TaskNode, validate_graph_definition


def validate_v3_graph_json(graph_json: dict[str, Any]) -> None:
    _ensure_dict(graph_json, name="v3 graph")
    nodes_payload = graph_json.get("nodes")
    edges_payload = graph_json.get("edges")
    runtime_caps = graph_json.get("runtimeCapabilities")
    if not isinstance(nodes_payload, list) or not isinstance(edges_payload, list):
        raise ValueError("v3 graph 驗證失敗：nodes/edges 必須是 list")

    runtime_dict = runtime_caps if isinstance(runtime_caps, dict) else _default_runtime_capabilities()
    nodes = [_to_task_node(raw) for raw in nodes_payload]
    edges = [_to_edge(raw) for raw in edges_payload]
    graph = GraphDefinition(
        version=str(graph_json.get("version") or ""),
        nodes=nodes,
        edges=edges,
        runtime_capabilities=RuntimeCapabilities(**runtime_dict),
    )
    validate_graph_definition(graph)


def _to_task_node(raw: Any) -> TaskNode:
    _ensure_dict(raw, name="v3 node")
    node_type = str(raw.get("node_type") or "")
    if node_type != "TASK":
        return TaskNode(id=str(raw.get("id") or ""), node_type=node_type, title=str(raw.get("title") or ""))

    output_contract = raw.get("outputContract") if isinstance(raw.get("outputContract"), dict) else {}
    ports_payload = output_contract.get("ports") if isinstance(output_contract.get("ports"), list) else []
    ports = [
        OutputPort(
            name=str(port.get("name") or ""),
            extractor=_optional_str(port.get("extractor")),
            parser=_optional_str(port.get("parser")),
            json_schema=port.get("jsonSchema") if isinstance(port.get("jsonSchema"), dict) else None,
            type_ref=_optional_str(port.get("typeRef")),
        )
        for port in ports_payload
        if isinstance(port, dict)
    ]

    task_spec_raw = raw.get("taskSpec")
    if not isinstance(task_spec_raw, dict):
        task_spec_raw = {
            "executor": "agent",
            "agent": {"prompt": None, "instructions": None, "model": None},
            "inputBindings": [],
            "artifacts": [],
            "display": {"label": str(raw.get("title") or ""), "summary": "missing taskSpec", "tags": ["incomplete"]},
            "runnable": False,
            "nonRunnableReason": "taskSpec 缺失，節點不可直接執行",
        }

    execution_config = raw.get("executionConfig")
    if execution_config is not None and not isinstance(execution_config, dict):
        raise ValueError(f"v3 graph 驗證失敗：executionConfig 必須是 object：node_id={raw.get('id')}")

    return TaskNode(
        id=str(raw.get("id") or ""),
        node_type="TASK",
        title=str(raw.get("title") or ""),
        execution=str(raw.get("execution") or "SINGLE"),
        execution_config=execution_config,
        task_spec=task_spec_from_payload(task_spec_raw),
        output_contract=OutputContract(ports=ports),
    )


def _to_edge(raw: Any) -> GraphEdge:
    _ensure_dict(raw, name="v3 edge")
    return GraphEdge(
        from_node=str(raw.get("from") or ""),
        to_node=str(raw.get("to") or ""),
        edge_type=str(raw.get("edge_type") or ""),
        kind=str(raw.get("kind") or ""),
    )


def _default_runtime_capabilities() -> dict[str, Any]:
    return {
        "supports_parallel_map": True,
        "supports_recursive": True,
        "supports_gate": True,
        "supports_group": True,
        "supports_artifact_node": True,
    }


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _ensure_dict(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} 必須是 object")
    return value
