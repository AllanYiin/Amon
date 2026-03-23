from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import VersionedEntity, copy_mapping, utc_now_iso

TEMPLATE_STATUSES = {"draft", "active", "archived"}


@dataclass
class Template(VersionedEntity):
    name: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    workflow_ref: str | None = None

    @classmethod
    def create(
        cls,
        *,
        template_id: str,
        name: str,
        parameters: dict[str, Any] | None = None,
        defaults: dict[str, Any] | None = None,
        workflow_ref: str | None = None,
        status: str = "draft",
    ) -> "Template":
        return cls(
            id=template_id,
            name=name,
            parameters=copy_mapping(parameters),
            defaults=copy_mapping(defaults),
            workflow_ref=workflow_ref,
            status=status,
        )

    def update(self, **changes: Any) -> "Template":
        for key in ["name", "workflow_ref", "status"]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "parameters" in changes and changes["parameters"] is not None:
            self.parameters = copy_mapping(changes["parameters"])
        if "defaults" in changes and changes["defaults"] is not None:
            self.defaults = copy_mapping(changes["defaults"])
        if self.status not in TEMPLATE_STATUSES:
            raise ValueError(f"不合法的 template status：{self.status}")
        self.touch()
        return self

    def clone(self, *, new_id: str | None = None) -> "Template":
        payload = self.clone_payload()
        if new_id:
            payload["id"] = new_id
        return Template.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "parameters": copy_mapping(self.parameters),
            "defaults": copy_mapping(self.defaults),
            "workflow_ref": self.workflow_ref,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Template":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            version=int(payload.get("version") or 1),
            name=str(payload.get("name") or ""),
            parameters=copy_mapping(payload.get("parameters")),
            defaults=copy_mapping(payload.get("defaults")),
            workflow_ref=payload.get("workflow_ref"),
            status=str(payload.get("status") or "draft"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if entity.status not in TEMPLATE_STATUSES:
            raise ValueError(f"不合法的 template status：{entity.status}")
        return entity
