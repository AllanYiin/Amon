from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import VersionedEntity, copy_list, copy_mapping, utc_now_iso

DEFINITION_STATUSES = {"draft", "active", "deprecated", "archived"}


@dataclass
class TaskDefinition(VersionedEntity):
    title: str = ""
    goal: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    input_contract: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    side_effect_class: str = "read_only"

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        title: str,
        goal: str,
        required_capabilities: list[str] | None = None,
        input_contract: dict[str, Any] | None = None,
        output_contract: dict[str, Any] | None = None,
        acceptance_criteria: list[str] | None = None,
        side_effect_class: str = "read_only",
        status: str = "draft",
    ) -> "TaskDefinition":
        return cls(
            id=task_id,
            title=title,
            goal=goal,
            required_capabilities=copy_list(required_capabilities),
            input_contract=copy_mapping(input_contract),
            output_contract=copy_mapping(output_contract),
            acceptance_criteria=copy_list(acceptance_criteria),
            side_effect_class=side_effect_class,
            status=status,
        )

    def update(self, **changes: Any) -> "TaskDefinition":
        for key in ["title", "goal", "side_effect_class", "status"]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "required_capabilities" in changes and changes["required_capabilities"] is not None:
            self.required_capabilities = copy_list(changes["required_capabilities"])
        if "input_contract" in changes and changes["input_contract"] is not None:
            self.input_contract = copy_mapping(changes["input_contract"])
        if "output_contract" in changes and changes["output_contract"] is not None:
            self.output_contract = copy_mapping(changes["output_contract"])
        if "acceptance_criteria" in changes and changes["acceptance_criteria"] is not None:
            self.acceptance_criteria = copy_list(changes["acceptance_criteria"])
        if self.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{self.status}")
        self.touch()
        return self

    def clone(self, *, new_id: str | None = None) -> "TaskDefinition":
        payload = self.clone_payload()
        if new_id:
            payload["id"] = new_id
        return TaskDefinition.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "goal": self.goal,
            "required_capabilities": copy_list(self.required_capabilities),
            "input_contract": copy_mapping(self.input_contract),
            "output_contract": copy_mapping(self.output_contract),
            "acceptance_criteria": copy_list(self.acceptance_criteria),
            "side_effect_class": self.side_effect_class,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskDefinition":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            version=int(payload.get("version") or 1),
            title=str(payload.get("title") or ""),
            goal=str(payload.get("goal") or ""),
            required_capabilities=copy_list(payload.get("required_capabilities")),
            input_contract=copy_mapping(payload.get("input_contract")),
            output_contract=copy_mapping(payload.get("output_contract")),
            acceptance_criteria=copy_list(payload.get("acceptance_criteria")),
            side_effect_class=str(payload.get("side_effect_class") or "read_only"),
            status=str(payload.get("status") or "draft"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if entity.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{entity.status}")
        return entity
