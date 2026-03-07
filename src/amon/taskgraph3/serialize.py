"""TaskGraph v3 serialization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .payloads import task_spec_to_payload
from .schema import GraphDefinition, validate_graph_definition


def dumps_graph_definition(graph: GraphDefinition) -> str:
    validate_graph_definition(graph)
    payload = _to_payload(graph)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _to_payload(graph: GraphDefinition) -> dict[str, Any]:
    payload = asdict(graph)
    payload["runtimeCapabilities"] = payload.pop("runtime_capabilities")

    for node_payload, node_obj in zip(payload.get("nodes", []), graph.nodes):
        if node_payload.get("node_type") == "TASK":
            node_payload["taskBoundaries"] = node_payload.pop("task_boundaries")
            node_payload["taskSpec"] = task_spec_to_payload(node_obj.task_spec)
            node_payload.pop("task_spec", None)
            output_contract = node_payload.get("output_contract") or {}
            node_payload["outputContract"] = output_contract
            node_payload.pop("output_contract", None)
            for port in node_payload["outputContract"].get("ports", []):
                port["jsonSchema"] = port.pop("json_schema")
                port["typeRef"] = port.pop("type_ref")
            if node_payload.get("execution_config") is not None:
                node_payload["executionConfig"] = node_payload.pop("execution_config")
            else:
                node_payload.pop("execution_config", None)
        elif node_payload.get("node_type") == "GATE":
            for route in node_payload.get("routes", []):
                route["onOutcome"] = route.pop("on_outcome")
                route["toNode"] = route.pop("to_node")
        elif node_payload.get("node_type") == "GROUP":
            node_payload["children"] = node_payload.get("children", [])

    for edge in payload.get("edges", []):
        edge["from"] = edge.pop("from_node")
        edge["to"] = edge.pop("to_node")

    return payload
