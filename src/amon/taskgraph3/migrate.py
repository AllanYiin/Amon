"""One-shot migrators from legacy/TaskGraph2 payloads to TaskGraph v3."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import GraphDefinition, GraphEdge, OutputContract, OutputPort, RuntimeCapabilities, TaskNode, validate_graph_definition


def legacy_to_v3(graph_json: dict[str, Any]) -> dict[str, Any]:
    """Convert a legacy graph payload to TaskGraph v3 JSON payload."""
    _ensure_dict(graph_json, name="legacy graph")
    nodes_payload = graph_json.get("nodes")
    edges_payload = graph_json.get("edges")
    if not isinstance(nodes_payload, list):
        raise ValueError("legacy graph 轉換失敗：nodes 必須是 list")
    if not isinstance(edges_payload, list):
        raise ValueError("legacy graph 轉換失敗：edges 必須是 list")

    v3_nodes: list[dict[str, Any]] = []
    v3_edges: list[dict[str, Any]] = []

    for index, node in enumerate(nodes_payload):
        _ensure_dict(node, name=f"legacy node[{index}]")
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            raise ValueError(f"legacy graph 轉換失敗：node[{index}].id 必須是非空字串")

        task_node = {
            "id": node_id,
            "node_type": "TASK",
            "title": str(node.get("title") or node.get("name") or node.get("type") or node_id),
            "execution": "SINGLE",
            "outputContract": {
                "ports": [
                    {
                        "name": "result",
                        "jsonSchema": {"type": _legacy_output_schema_type(node)},
                    }
                ]
            },
            "policy": {},
        }
        v3_nodes.append(task_node)
        for artifact in _extract_legacy_artifacts(node):
            artifact_id = _artifact_node_id(node_id, artifact["name"])
            v3_nodes.append(
                {
                    "id": artifact_id,
                    "node_type": "ARTIFACT",
                    "title": artifact["title"],
                }
            )
            v3_edges.append(
                {
                    "from": node_id,
                    "to": artifact_id,
                    "edge_type": "DATA",
                    "kind": "EMITS",
                }
            )

    v3_edges.extend(_convert_control_edges(edges_payload, source_label="legacy graph"))
    v3_graph = {
        "version": "taskgraph.v3",
        "nodes": v3_nodes,
        "edges": v3_edges,
        "runtimeCapabilities": _default_runtime_capabilities(),
    }
    validate_v3_graph_json(v3_graph)
    return v3_graph


def v2_to_v3(taskgraph2_json: dict[str, Any]) -> dict[str, Any]:
    """Convert a TaskGraph2 payload to TaskGraph v3 JSON payload."""
    _ensure_dict(taskgraph2_json, name="taskgraph2 graph")
    nodes_payload = taskgraph2_json.get("nodes")
    edges_payload = taskgraph2_json.get("edges")
    if not isinstance(nodes_payload, list):
        raise ValueError("taskgraph2 轉換失敗：nodes 必須是 list")
    if not isinstance(edges_payload, list):
        raise ValueError("taskgraph2 轉換失敗：edges 必須是 list")

    v3_nodes: list[dict[str, Any]] = []
    v3_edges: list[dict[str, Any]] = []

    for index, node in enumerate(nodes_payload):
        _ensure_dict(node, name=f"taskgraph2 node[{index}]")
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            raise ValueError(f"taskgraph2 轉換失敗：node[{index}].id 必須是非空字串")
        output = node.get("output") if isinstance(node.get("output"), dict) else {}
        schema_type = _v2_output_schema_type(output)

        task_node: dict[str, Any] = {
            "id": node_id,
            "node_type": "TASK",
            "title": str(node.get("title") or node_id),
            "execution": "SINGLE",
            "outputContract": {
                "ports": [
                    {
                        "name": "result",
                        "jsonSchema": {"type": schema_type},
                    }
                ]
            },
            "policy": {},
        }

        guardrails = node.get("guardrails")
        if isinstance(guardrails, dict):
            migrated_guardrails = {
                key: value
                for key, value in guardrails.items()
                if key in {"allow_interrupt", "require_human_approval"}
            }
            if migrated_guardrails:
                task_node["guardrails"] = migrated_guardrails
            boundaries = guardrails.get("boundaries")
            if isinstance(boundaries, list) and boundaries:
                task_node["taskBoundaries"] = [str(item) for item in boundaries]

        v3_nodes.append(task_node)
        writes = node.get("writes") if isinstance(node.get("writes"), dict) else {}
        for write_key, write_path in writes.items():
            artifact_name = str(write_key or "result")
            artifact_id = _artifact_node_id(node_id, artifact_name)
            v3_nodes.append(
                {
                    "id": artifact_id,
                    "node_type": "ARTIFACT",
                    "title": str(write_path or artifact_name),
                }
            )
            v3_edges.append(
                {
                    "from": node_id,
                    "to": artifact_id,
                    "edge_type": "DATA",
                    "kind": "EMITS",
                }
            )

    v3_edges.extend(_convert_control_edges(edges_payload, source_label="taskgraph2"))
    v3_graph = {
        "version": "taskgraph.v3",
        "nodes": v3_nodes,
        "edges": v3_edges,
        "runtimeCapabilities": _default_runtime_capabilities(),
    }
    validate_v3_graph_json(v3_graph)
    return v3_graph


def migrate_json_file(*, input_path: Path, output_path: Path, source_format: str) -> Path:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"讀取輸入 JSON 失敗：{input_path}（{exc}）") from exc

    if source_format == "legacy":
        migrated = legacy_to_v3(payload)
    elif source_format == "v2":
        migrated = v2_to_v3(payload)
    else:
        raise ValueError(f"不支援的來源格式：{source_format}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def validate_v3_graph_json(graph_json: dict[str, Any]) -> None:
    _ensure_dict(graph_json, name="v3 graph")
    nodes_payload = graph_json.get("nodes")
    edges_payload = graph_json.get("edges")
    if not isinstance(nodes_payload, list) or not isinstance(edges_payload, list):
        raise ValueError("v3 graph 驗證失敗：nodes/edges 必須是 list")

    nodes = [_to_task_node(raw) for raw in nodes_payload]
    edges = [_to_edge(raw) for raw in edges_payload]
    graph = GraphDefinition(
        version=str(graph_json.get("version") or ""),
        nodes=nodes,
        edges=edges,
        runtime_capabilities=RuntimeCapabilities(**_default_runtime_capabilities()),
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

    return TaskNode(
        id=str(raw.get("id") or ""),
        node_type="TASK",
        title=str(raw.get("title") or ""),
        execution=str(raw.get("execution") or "SINGLE"),
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


def _convert_control_edges(edges_payload: list[Any], *, source_label: str) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for index, edge in enumerate(edges_payload):
        _ensure_dict(edge, name=f"{source_label} edge[{index}]")
        from_node = str(edge.get("from") or "").strip()
        to_node = str(edge.get("to") or "").strip()
        if not from_node or not to_node:
            raise ValueError(f"{source_label} 轉換失敗：edge[{index}] from/to 必須是非空字串")
        converted.append(
            {
                "from": from_node,
                "to": to_node,
                "edge_type": "CONTROL",
                "kind": "DEPENDS_ON",
            }
        )
    return converted


def _legacy_output_schema_type(node: dict[str, Any]) -> str:
    output = node.get("output")
    if isinstance(output, dict):
        output_type = str(output.get("type") or "").lower()
        if output_type in {"json", "object", "artifact"}:
            return "object"
    node_type = str(node.get("type") or "").lower()
    if node_type in {"write_file", "tool.call", "tool_call"}:
        return "object"
    return "string"


def _v2_output_schema_type(output: dict[str, Any]) -> str:
    output_type = str(output.get("type") or "text").lower()
    if output_type in {"json", "artifact"}:
        return "object"
    return "string"


def _extract_legacy_artifacts(node: dict[str, Any]) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for key in ("path", "output_path", "artifact", "target"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            artifacts.append({"name": key, "title": value})
    return artifacts


def _artifact_node_id(node_id: str, output_name: str) -> str:
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in output_name).strip("_") or "result"
    return f"{node_id}__artifact__{safe_name}"


def _default_runtime_capabilities() -> dict[str, bool]:
    return {
        "supports_control_edges": True,
        "supports_data_edges": True,
        "supports_parallel_map": True,
        "supports_recursive": True,
        "supports_task_guardrails": True,
        "supports_task_boundaries": True,
    }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _ensure_dict(value: Any, *, name: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{name} 必須是 object")

