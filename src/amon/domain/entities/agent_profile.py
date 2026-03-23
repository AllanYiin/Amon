from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import VersionedEntity, copy_list, copy_mapping, utc_now_iso
from .task_definition import DEFINITION_STATUSES


@dataclass
class AgentProfile(VersionedEntity):
    name: str = ""
    purpose: str = ""
    system_prompt: str = ""
    default_skills: list[str] = field(default_factory=list)
    model_policy: dict[str, Any] = field(default_factory=dict)
    memory_policy: str = "project_scoped"
    output_style: str | None = None

    @classmethod
    def create(
        cls,
        *,
        agent_id: str,
        name: str,
        purpose: str,
        system_prompt: str,
        default_skills: list[str] | None = None,
        model_policy: dict[str, Any] | None = None,
        memory_policy: str = "project_scoped",
        output_style: str | None = None,
        status: str = "draft",
    ) -> "AgentProfile":
        return cls(
            id=agent_id,
            name=name,
            purpose=purpose,
            system_prompt=system_prompt,
            default_skills=copy_list(default_skills),
            model_policy=copy_mapping(model_policy),
            memory_policy=memory_policy,
            output_style=output_style,
            status=status,
        )

    def update(self, **changes: Any) -> "AgentProfile":
        for key in ["name", "purpose", "system_prompt", "memory_policy", "output_style", "status"]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "default_skills" in changes and changes["default_skills"] is not None:
            self.default_skills = copy_list(changes["default_skills"])
        if "model_policy" in changes and changes["model_policy"] is not None:
            self.model_policy = copy_mapping(changes["model_policy"])
        if self.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{self.status}")
        self.touch()
        return self

    def clone(self, *, new_id: str | None = None) -> "AgentProfile":
        payload = self.clone_payload()
        if new_id:
            payload["id"] = new_id
        return AgentProfile.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "purpose": self.purpose,
            "system_prompt": self.system_prompt,
            "default_skills": copy_list(self.default_skills),
            "model_policy": copy_mapping(self.model_policy),
            "memory_policy": self.memory_policy,
            "output_style": self.output_style,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentProfile":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            version=int(payload.get("version") or 1),
            name=str(payload.get("name") or ""),
            purpose=str(payload.get("purpose") or ""),
            system_prompt=str(payload.get("system_prompt") or ""),
            default_skills=copy_list(payload.get("default_skills")),
            model_policy=copy_mapping(payload.get("model_policy")),
            memory_policy=str(payload.get("memory_policy") or "project_scoped"),
            output_style=payload.get("output_style"),
            status=str(payload.get("status") or "draft"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if entity.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{entity.status}")
        return entity
