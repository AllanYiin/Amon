from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import VersionedEntity, copy_list, copy_mapping, utc_now_iso
from .task_definition import DEFINITION_STATUSES


@dataclass
class ToolPolicy(VersionedEntity):
    allowed_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    allow_network: bool = False
    delegated_allowed: bool = False
    side_effect_ceiling: str = "read_only"
    approval_rules: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        policy_id: str,
        allowed_tools: list[str] | None = None,
        allowed_paths: list[str] | None = None,
        allow_network: bool = False,
        delegated_allowed: bool = False,
        side_effect_ceiling: str = "read_only",
        approval_rules: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> "ToolPolicy":
        return cls(
            id=policy_id,
            allowed_tools=copy_list(allowed_tools),
            allowed_paths=copy_list(allowed_paths),
            allow_network=allow_network,
            delegated_allowed=delegated_allowed,
            side_effect_ceiling=side_effect_ceiling,
            approval_rules=copy_mapping(approval_rules),
            status=status,
        )

    def update(self, **changes: Any) -> "ToolPolicy":
        for key in ["allow_network", "delegated_allowed", "side_effect_ceiling", "status"]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "allowed_tools" in changes and changes["allowed_tools"] is not None:
            self.allowed_tools = copy_list(changes["allowed_tools"])
        if "allowed_paths" in changes and changes["allowed_paths"] is not None:
            self.allowed_paths = copy_list(changes["allowed_paths"])
        if "approval_rules" in changes and changes["approval_rules"] is not None:
            self.approval_rules = copy_mapping(changes["approval_rules"])
        if self.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{self.status}")
        self.touch()
        return self

    def clone(self, *, new_id: str | None = None) -> "ToolPolicy":
        payload = self.clone_payload()
        if new_id:
            payload["id"] = new_id
        return ToolPolicy.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "allowed_tools": copy_list(self.allowed_tools),
            "allowed_paths": copy_list(self.allowed_paths),
            "allow_network": self.allow_network,
            "delegated_allowed": self.delegated_allowed,
            "side_effect_ceiling": self.side_effect_ceiling,
            "approval_rules": copy_mapping(self.approval_rules),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolPolicy":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            version=int(payload.get("version") or 1),
            allowed_tools=copy_list(payload.get("allowed_tools")),
            allowed_paths=copy_list(payload.get("allowed_paths")),
            allow_network=bool(payload.get("allow_network", False)),
            delegated_allowed=bool(payload.get("delegated_allowed", False)),
            side_effect_ceiling=str(payload.get("side_effect_ceiling") or "read_only"),
            approval_rules=copy_mapping(payload.get("approval_rules")),
            status=str(payload.get("status") or "draft"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if entity.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{entity.status}")
        return entity
