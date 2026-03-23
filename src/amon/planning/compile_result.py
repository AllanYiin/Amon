"""Stage 2 compile result types for manifest v1 -> taskgraph.v3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from amon.taskgraph3.schema import GraphDefinition
from amon.taskgraph3.serialize import dumps_graph_definition


@dataclass(frozen=True)
class SnapshotPin:
    ref: str
    version: int
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {"ref": self.ref, "version": self.version, "kind": self.kind}


@dataclass(frozen=True)
class CompileResult:
    workflow_ref: str
    graph: GraphDefinition
    snapshot_pins: dict[str, SnapshotPin] = field(default_factory=dict)

    @property
    def graph_payload(self) -> dict[str, Any]:
        return {
            "workflow_ref": self.workflow_ref,
            "snapshot_pins": {key: pin.to_dict() for key, pin in self.snapshot_pins.items()},
            "compiled_graph": self.compiled_graph,
        }

    @property
    def compiled_graph(self) -> dict[str, Any]:
        import json

        return json.loads(dumps_graph_definition(self.graph))

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_ref": self.workflow_ref,
            "snapshot_pins": {key: pin.to_dict() for key, pin in self.snapshot_pins.items()},
            "compiled_graph": self.compiled_graph,
        }
