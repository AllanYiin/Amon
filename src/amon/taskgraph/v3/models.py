"""TaskGraph v3 data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION_V3 = "taskgraph.v3"


@dataclass
class EnumTypeV3:
    enumId: str
    values: list[str] = field(default_factory=list)
    description: str | None = None


@dataclass
class PortV3:
    name: str
    typeRef: str


@dataclass
class NodeV3:
    nodeId: str
    kind: str
    title: str = ""
    inputs: list[PortV3] = field(default_factory=list)
    outputs: list[PortV3] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeV3:
    edgeId: str
    fromNodeId: str
    fromPort: str
    toNodeId: str
    toPort: str
    typeRef: str | None = None


@dataclass
class PolicyV3:
    retryMax: int = 0
    timeoutSec: int = 0


@dataclass
class OutputContractV3:
    typeRef: str | None = None
    required: list[str] = field(default_factory=list)


@dataclass
class GuardrailsV3:
    blockedPatterns: list[str] = field(default_factory=list)


@dataclass
class OutputBoundaryV3:
    maxChars: int = 0


@dataclass
class ScorerV3:
    metric: str = ""
    threshold: float = 0.0


@dataclass
class GraphV3:
    schemaVersion: str = SCHEMA_VERSION_V3
    nodes: list[NodeV3] = field(default_factory=list)
    edges: list[EdgeV3] = field(default_factory=list)
    enums: list[EnumTypeV3] = field(default_factory=list)
    policy: PolicyV3 = field(default_factory=PolicyV3)
    outputContract: OutputContractV3 = field(default_factory=OutputContractV3)
    guardrails: GuardrailsV3 = field(default_factory=GuardrailsV3)
    outputBoundary: OutputBoundaryV3 = field(default_factory=OutputBoundaryV3)
    scorer: ScorerV3 = field(default_factory=ScorerV3)
