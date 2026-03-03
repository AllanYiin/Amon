"""TaskGraph v3 parsing and validation."""

from __future__ import annotations

from typing import Any

from amon.taskgraph2.serialize import loads_task_graph

from .models import (
    SCHEMA_VERSION_V3,
    EdgeV3,
    EnumTypeV3,
    GraphV3,
    GuardrailsV3,
    NodeV3,
    OutputBoundaryV3,
    OutputContractV3,
    PolicyV3,
    PortV3,
    ScorerV3,
)

_ALLOWED_PRIMITIVE_TYPE_REFS = {
    "string",
    "number",
    "integer",
    "boolean",
    "object",
    "array",
    "null",
    "any",
}


def detect_graph_version(payload: dict[str, Any]) -> str:
    version = str(payload.get("schemaVersion") or payload.get("schema_version") or "").strip()
    if version == SCHEMA_VERSION_V3:
        return SCHEMA_VERSION_V3
    if version == "2.0":
        return "2.0"
    raise ValueError(f"不支援的 graph schema 版本：{version or '<empty>'}")


def parse_graph(raw: dict[str, Any] | str) -> GraphV3:
    payload = raw
    if isinstance(raw, str):
        import json

        payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("graph payload 必須是 object")

    version = detect_graph_version(payload)
    if version != SCHEMA_VERSION_V3:
        raise ValueError(f"parse_graph 只接受 {SCHEMA_VERSION_V3}，目前為：{version}")

    graph = GraphV3(
        schemaVersion=str(payload.get("schemaVersion") or ""),
        nodes=[_parse_node(item) for item in _read_list(payload, "nodes")],
        edges=[_parse_edge(item) for item in _read_list(payload, "edges")],
        enums=[_parse_enum(item) for item in _read_list(payload, "enums", default=[])],
        policy=_parse_policy(payload.get("policy") or {}),
        outputContract=_parse_output_contract(payload.get("outputContract") or {}),
        guardrails=_parse_guardrails(payload.get("guardrails") or {}),
        outputBoundary=_parse_output_boundary(payload.get("outputBoundary") or {}),
        scorer=_parse_scorer(payload.get("scorer") or {}),
    )
    validate_structure(graph)
    validate_refs(graph)
    return graph


def parse_graph_any(raw: dict[str, Any] | str) -> GraphV3 | Any:
    payload = raw
    if isinstance(raw, str):
        import json

        payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("graph payload 必須是 object")

    version = detect_graph_version(payload)
    if version == SCHEMA_VERSION_V3:
        return parse_graph(payload)
    return loads_task_graph(raw if isinstance(raw, str) else __import__("json").dumps(payload, ensure_ascii=False))


def validate_structure(graph: GraphV3) -> None:
    if graph.schemaVersion != SCHEMA_VERSION_V3:
        raise ValueError(f"schemaVersion 必須固定為 {SCHEMA_VERSION_V3}")
    if not graph.nodes:
        raise ValueError("nodes 不可為空")

    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    seen_enums: set[str] = set()

    for enum_item in graph.enums:
        if not enum_item.enumId.strip():
            raise ValueError("enumId 必須是非空字串")
        if enum_item.enumId in seen_enums:
            raise ValueError(f"enumId 不可重複：{enum_item.enumId}")
        if not enum_item.values or any(not isinstance(v, str) or not v.strip() for v in enum_item.values):
            raise ValueError(f"enum.values 必須是非空字串陣列：enumId={enum_item.enumId}")
        seen_enums.add(enum_item.enumId)

    for node in graph.nodes:
        if not node.nodeId.strip():
            raise ValueError("nodeId 必須是非空字串")
        if node.nodeId in seen_nodes:
            raise ValueError(f"nodeId 不可重複：{node.nodeId}")
        if not node.kind.strip():
            raise ValueError(f"node.kind 必須是非空字串：nodeId={node.nodeId}")
        _validate_ports(node.inputs, "inputs", node.nodeId)
        _validate_ports(node.outputs, "outputs", node.nodeId)
        seen_nodes.add(node.nodeId)

    for edge in graph.edges:
        if not edge.edgeId.strip():
            raise ValueError("edgeId 必須是非空字串")
        if edge.edgeId in seen_edges:
            raise ValueError(f"edgeId 不可重複：{edge.edgeId}")
        if not edge.fromNodeId.strip() or not edge.toNodeId.strip():
            raise ValueError(f"edge node 參照不可為空：edgeId={edge.edgeId}")
        if not edge.fromPort.strip() or not edge.toPort.strip():
            raise ValueError(f"edge port 參照不可為空：edgeId={edge.edgeId}")
        if edge.typeRef is not None:
            _validate_type_ref_format(edge.typeRef)
        seen_edges.add(edge.edgeId)


def validate_refs(graph: GraphV3) -> None:
    node_map = {node.nodeId: node for node in graph.nodes}
    enum_ids = {enum_item.enumId for enum_item in graph.enums}

    for node in graph.nodes:
        for port in [*node.inputs, *node.outputs]:
            _validate_type_ref_exists(port.typeRef, enum_ids, f"nodeId={node.nodeId}, port={port.name}")

    for edge in graph.edges:
        source = node_map.get(edge.fromNodeId)
        if source is None:
            raise ValueError(f"edge.fromNodeId 不存在：edgeId={edge.edgeId}, nodeId={edge.fromNodeId}")
        target = node_map.get(edge.toNodeId)
        if target is None:
            raise ValueError(f"edge.toNodeId 不存在：edgeId={edge.edgeId}, nodeId={edge.toNodeId}")

        source_port = next((port for port in source.outputs if port.name == edge.fromPort), None)
        if source_port is None:
            raise ValueError(f"edge.fromPort 不存在：edgeId={edge.edgeId}, port={edge.fromPort}")
        target_port = next((port for port in target.inputs if port.name == edge.toPort), None)
        if target_port is None:
            raise ValueError(f"edge.toPort 不存在：edgeId={edge.edgeId}, port={edge.toPort}")

        if edge.typeRef:
            _validate_type_ref_exists(edge.typeRef, enum_ids, f"edgeId={edge.edgeId}")

    if graph.outputContract.typeRef:
        _validate_type_ref_exists(graph.outputContract.typeRef, enum_ids, "outputContract")


def _validate_ports(ports: list[PortV3], field_name: str, node_id: str) -> None:
    names: set[str] = set()
    for port in ports:
        if not port.name.strip():
            raise ValueError(f"{field_name}.name 必須是非空字串：nodeId={node_id}")
        if port.name in names:
            raise ValueError(f"{field_name}.name 不可重複：nodeId={node_id}, name={port.name}")
        _validate_type_ref_format(port.typeRef)
        names.add(port.name)


def _validate_type_ref_format(type_ref: str) -> None:
    if type_ref in _ALLOWED_PRIMITIVE_TYPE_REFS:
        return
    if not type_ref.startswith("#/enums/"):
        raise ValueError(f"typeRef 格式不合法：{type_ref}")
    _, _, enum_id = type_ref.partition("#/enums/")
    if not enum_id.strip():
        raise ValueError(f"typeRef 格式不合法：{type_ref}")


def _validate_type_ref_exists(type_ref: str, enum_ids: set[str], context: str) -> None:
    _validate_type_ref_format(type_ref)
    if type_ref.startswith("#/enums/"):
        enum_id = type_ref.replace("#/enums/", "", 1)
        if enum_id not in enum_ids:
            raise ValueError(f"typeRef 指向不存在 enum：{type_ref} ({context})")


def _parse_node(raw: Any) -> NodeV3:
    if not isinstance(raw, dict):
        raise ValueError("node 必須是 object")
    return NodeV3(
        nodeId=str(raw.get("nodeId") or ""),
        kind=str(raw.get("kind") or ""),
        title=str(raw.get("title") or ""),
        inputs=[_parse_port(item) for item in _read_list(raw, "inputs", default=[])],
        outputs=[_parse_port(item) for item in _read_list(raw, "outputs", default=[])],
        config=dict(raw.get("config") or {}),
    )


def _parse_edge(raw: Any) -> EdgeV3:
    if not isinstance(raw, dict):
        raise ValueError("edge 必須是 object")
    type_ref = raw.get("typeRef")
    if type_ref is not None:
        type_ref = str(type_ref)
    return EdgeV3(
        edgeId=str(raw.get("edgeId") or ""),
        fromNodeId=str(raw.get("fromNodeId") or ""),
        fromPort=str(raw.get("fromPort") or ""),
        toNodeId=str(raw.get("toNodeId") or ""),
        toPort=str(raw.get("toPort") or ""),
        typeRef=type_ref,
    )


def _parse_enum(raw: Any) -> EnumTypeV3:
    if not isinstance(raw, dict):
        raise ValueError("enum 必須是 object")
    return EnumTypeV3(
        enumId=str(raw.get("enumId") or ""),
        values=[str(item) for item in _read_list(raw, "values")],
        description=str(raw.get("description")) if raw.get("description") is not None else None,
    )


def _parse_port(raw: Any) -> PortV3:
    if not isinstance(raw, dict):
        raise ValueError("port 必須是 object")
    return PortV3(name=str(raw.get("name") or ""), typeRef=str(raw.get("typeRef") or ""))


def _parse_policy(raw: Any) -> PolicyV3:
    if not isinstance(raw, dict):
        raise ValueError("policy 必須是 object")
    return PolicyV3(retryMax=int(raw.get("retryMax", 0)), timeoutSec=int(raw.get("timeoutSec", 0)))


def _parse_output_contract(raw: Any) -> OutputContractV3:
    if not isinstance(raw, dict):
        raise ValueError("outputContract 必須是 object")
    type_ref = raw.get("typeRef")
    return OutputContractV3(
        typeRef=str(type_ref) if type_ref is not None else None,
        required=[str(item) for item in _read_list(raw, "required", default=[])],
    )


def _parse_guardrails(raw: Any) -> GuardrailsV3:
    if not isinstance(raw, dict):
        raise ValueError("guardrails 必須是 object")
    return GuardrailsV3(blockedPatterns=[str(item) for item in _read_list(raw, "blockedPatterns", default=[])])


def _parse_output_boundary(raw: Any) -> OutputBoundaryV3:
    if not isinstance(raw, dict):
        raise ValueError("outputBoundary 必須是 object")
    return OutputBoundaryV3(maxChars=int(raw.get("maxChars", 0)))


def _parse_scorer(raw: Any) -> ScorerV3:
    if not isinstance(raw, dict):
        raise ValueError("scorer 必須是 object")
    threshold = raw.get("threshold", 0.0)
    return ScorerV3(metric=str(raw.get("metric") or ""), threshold=float(threshold))


def _read_list(payload: dict[str, Any], key: str, default: list[Any] | None = None) -> list[Any]:
    value = payload.get(key, default if default is not None else None)
    if not isinstance(value, list):
        raise ValueError(f"{key} 必須是 list")
    return value
