"""TaskGraph v3 serialization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .schema import GraphDefinition, validate_graph_definition


def dumps_graph_definition(graph: GraphDefinition) -> str:
    validate_graph_definition(graph)
    payload = _to_payload(graph)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _to_payload(graph: GraphDefinition) -> dict[str, Any]:
    payload = asdict(graph)
    payload["runtimeCapabilities"] = payload.pop("runtime_capabilities")

    for node in payload.get("nodes", []):
        if node.get("node_type") == "TASK":
            node["taskBoundaries"] = node.pop("task_boundaries")
            output_contract = node.get("output_contract") or {}
            node["outputContract"] = output_contract
            node.pop("output_contract", None)
            for port in node["outputContract"].get("ports", []):
                port["jsonSchema"] = port.pop("json_schema")
                port["typeRef"] = port.pop("type_ref")
        elif node.get("node_type") == "GATE":
            for route in node.get("routes", []):
                route["onOutcome"] = route.pop("on_outcome")
                route["toNode"] = route.pop("to_node")
        elif node.get("node_type") == "GROUP":
            node["children"] = node.get("children", [])

    for edge in payload.get("edges", []):
        edge["from"] = edge.pop("from_node")
        edge["to"] = edge.pop("to_node")

    return payload
