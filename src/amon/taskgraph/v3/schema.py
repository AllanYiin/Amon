"""JSON schema exporter for TaskGraph v3."""

from __future__ import annotations

from typing import Any

from .models import SCHEMA_VERSION_V3


def to_json_schema(_: object | None = None) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://amon.dev/schemas/taskgraph.v3.json",
        "title": "Amon TaskGraph v3",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schemaVersion",
            "nodes",
            "edges",
            "enums",
            "policy",
            "outputContract",
            "guardrails",
            "outputBoundary",
            "scorer",
        ],
        "properties": {
            "schemaVersion": {"const": SCHEMA_VERSION_V3},
            "nodes": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/node"}},
            "edges": {"type": "array", "items": {"$ref": "#/$defs/edge"}},
            "enums": {"type": "array", "items": {"$ref": "#/$defs/enumType"}},
            "policy": {"$ref": "#/$defs/policy"},
            "outputContract": {"$ref": "#/$defs/outputContract"},
            "guardrails": {"$ref": "#/$defs/guardrails"},
            "outputBoundary": {"$ref": "#/$defs/outputBoundary"},
            "scorer": {"$ref": "#/$defs/scorer"},
        },
        "$defs": {
            "typeRef": {
                "type": "string",
                "pattern": "^(string|number|integer|boolean|object|array|null|any|#/enums/[A-Za-z0-9_-]+)$",
            },
            "enumType": {
                "type": "object",
                "additionalProperties": False,
                "required": ["enumId", "values"],
                "properties": {
                    "enumId": {"type": "string", "minLength": 1},
                    "values": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                    "description": {"type": "string"},
                },
            },
            "port": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "typeRef"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "typeRef": {"$ref": "#/$defs/typeRef"},
                },
            },
            "node": {
                "type": "object",
                "additionalProperties": False,
                "required": ["nodeId", "kind", "inputs", "outputs", "config"],
                "properties": {
                    "nodeId": {"type": "string", "minLength": 1},
                    "kind": {"type": "string", "minLength": 1},
                    "title": {"type": "string"},
                    "inputs": {"type": "array", "items": {"$ref": "#/$defs/port"}},
                    "outputs": {"type": "array", "items": {"$ref": "#/$defs/port"}},
                    "config": {"type": "object"},
                },
            },
            "edge": {
                "type": "object",
                "additionalProperties": False,
                "required": ["edgeId", "fromNodeId", "fromPort", "toNodeId", "toPort"],
                "properties": {
                    "edgeId": {"type": "string", "minLength": 1},
                    "fromNodeId": {"type": "string", "minLength": 1},
                    "fromPort": {"type": "string", "minLength": 1},
                    "toNodeId": {"type": "string", "minLength": 1},
                    "toPort": {"type": "string", "minLength": 1},
                    "typeRef": {"$ref": "#/$defs/typeRef"},
                },
            },
            "policy": {
                "type": "object",
                "additionalProperties": False,
                "required": ["retryMax", "timeoutSec"],
                "properties": {
                    "retryMax": {"type": "integer", "minimum": 0},
                    "timeoutSec": {"type": "integer", "minimum": 0},
                },
            },
            "outputContract": {
                "type": "object",
                "additionalProperties": False,
                "required": ["required"],
                "properties": {
                    "typeRef": {"$ref": "#/$defs/typeRef"},
                    "required": {"type": "array", "items": {"type": "string", "minLength": 1}},
                },
            },
            "guardrails": {
                "type": "object",
                "additionalProperties": False,
                "required": ["blockedPatterns"],
                "properties": {
                    "blockedPatterns": {"type": "array", "items": {"type": "string"}},
                },
            },
            "outputBoundary": {
                "type": "object",
                "additionalProperties": False,
                "required": ["maxChars"],
                "properties": {
                    "maxChars": {"type": "integer", "minimum": 0},
                },
            },
            "scorer": {
                "type": "object",
                "additionalProperties": False,
                "required": ["metric", "threshold"],
                "properties": {
                    "metric": {"type": "string"},
                    "threshold": {"type": "number"},
                },
            },
        },
    }
