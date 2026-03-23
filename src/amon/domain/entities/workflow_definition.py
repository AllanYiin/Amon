from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import VersionedEntity, copy_list, copy_mapping, utc_now_iso

WORKFLOW_STATUSES = {"draft", "valid", "invalid", "active", "archived"}
WORKFLOW_NODE_STATUSES = {"draft", "valid", "invalid", "disabled"}


@dataclass
class WorkflowNode:
    id: str
    task_ref: str
    executor_ref: str
    depends_on: list[str] = field(default_factory=list)
    condition: dict[str, Any] | None = None
    input_mapping: dict[str, Any] = field(default_factory=dict)
    output_mapping: dict[str, Any] = field(default_factory=dict)
    status: str = "draft"

    def update(self, **changes: Any) -> "WorkflowNode":
        for key in ["task_ref", "executor_ref", "status"]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "depends_on" in changes and changes["depends_on"] is not None:
            self.depends_on = copy_list(changes["depends_on"])
        if "condition" in changes:
            self.condition = copy_mapping(changes["condition"]) if changes["condition"] is not None else None
        if "input_mapping" in changes and changes["input_mapping"] is not None:
            self.input_mapping = copy_mapping(changes["input_mapping"])
        if "output_mapping" in changes and changes["output_mapping"] is not None:
            self.output_mapping = copy_mapping(changes["output_mapping"])
        if self.status not in WORKFLOW_NODE_STATUSES:
            raise ValueError(f"不合法的 workflow node status：{self.status}")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_ref": self.task_ref,
            "executor_ref": self.executor_ref,
            "depends_on": copy_list(self.depends_on),
            "condition": copy_mapping(self.condition) if self.condition else None,
            "input_mapping": copy_mapping(self.input_mapping),
            "output_mapping": copy_mapping(self.output_mapping),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowNode":
        node = cls(
            id=str(payload.get("id") or ""),
            task_ref=str(payload.get("task_ref") or ""),
            executor_ref=str(payload.get("executor_ref") or ""),
            depends_on=copy_list(payload.get("depends_on")),
            condition=copy_mapping(payload.get("condition")) if isinstance(payload.get("condition"), dict) else None,
            input_mapping=copy_mapping(payload.get("input_mapping")),
            output_mapping=copy_mapping(payload.get("output_mapping")),
            status=str(payload.get("status") or "draft"),
        )
        if node.status not in WORKFLOW_NODE_STATUSES:
            raise ValueError(f"不合法的 workflow node status：{node.status}")
        return node


@dataclass
class WorkflowDefinition(VersionedEntity):
    name: str = ""
    nodes: list[WorkflowNode] = field(default_factory=list)
    routes: list[dict[str, Any]] = field(default_factory=list)
    output_bindings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        workflow_id: str,
        name: str,
        nodes: list[WorkflowNode] | None = None,
        routes: list[dict[str, Any]] | None = None,
        output_bindings: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> "WorkflowDefinition":
        return cls(
            id=workflow_id,
            name=name,
            nodes=[WorkflowNode.from_dict(item.to_dict()) if isinstance(item, WorkflowNode) else WorkflowNode.from_dict(item) for item in (nodes or [])],
            routes=copy_list(routes),
            output_bindings=copy_mapping(output_bindings),
            status=status,
        )

    def update(self, **changes: Any) -> "WorkflowDefinition":
        for key in ["name", "status"]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "nodes" in changes and changes["nodes"] is not None:
            self.nodes = [
                WorkflowNode.from_dict(item.to_dict()) if isinstance(item, WorkflowNode) else WorkflowNode.from_dict(item)
                for item in changes["nodes"]
            ]
        if "routes" in changes and changes["routes"] is not None:
            self.routes = copy_list(changes["routes"])
        if "output_bindings" in changes and changes["output_bindings"] is not None:
            self.output_bindings = copy_mapping(changes["output_bindings"])
        if self.status not in WORKFLOW_STATUSES:
            raise ValueError(f"不合法的 workflow status：{self.status}")
        self.touch()
        return self

    def clone(self, *, new_id: str | None = None) -> "WorkflowDefinition":
        payload = self.clone_payload()
        if new_id:
            payload["id"] = new_id
        return WorkflowDefinition.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "nodes": [node.to_dict() for node in self.nodes],
            "routes": copy_list(self.routes),
            "output_bindings": copy_mapping(self.output_bindings),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowDefinition":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            version=int(payload.get("version") or 1),
            name=str(payload.get("name") or ""),
            nodes=[WorkflowNode.from_dict(item) for item in payload.get("nodes") or []],
            routes=copy_list(payload.get("routes")),
            output_bindings=copy_mapping(payload.get("output_bindings")),
            status=str(payload.get("status") or "draft"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if entity.status not in WORKFLOW_STATUSES:
            raise ValueError(f"不合法的 workflow status：{entity.status}")
        return entity
