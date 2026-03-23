from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import VersionedEntity, copy_mapping, utc_now_iso
from .task_definition import DEFINITION_STATUSES

EXECUTOR_TYPES = {"llm", "tool", "sandbox", "human_gate", "subgraph"}


@dataclass
class ExecutorBinding(VersionedEntity):
    type: str = "llm"
    capabilities: list[str] = field(default_factory=list)
    agent_profile_ref: str | None = None
    tool_plan: dict[str, Any] = field(default_factory=dict)
    tool_invocation_mode: str | None = None
    tool_policy_ref: str | None = None
    timeout_s: int = 180
    retry_policy: dict[str, Any] = field(default_factory=dict)
    approval_policy: dict[str, Any] = field(default_factory=dict)
    streaming_required: bool = True

    @classmethod
    def create(
        cls,
        *,
        executor_id: str,
        executor_type: str,
        capabilities: list[str] | None = None,
        agent_profile_ref: str | None = None,
        tool_plan: dict[str, Any] | None = None,
        tool_invocation_mode: str | None = None,
        tool_policy_ref: str | None = None,
        timeout_s: int = 180,
        retry_policy: dict[str, Any] | None = None,
        approval_policy: dict[str, Any] | None = None,
        streaming_required: bool = True,
        status: str = "draft",
    ) -> "ExecutorBinding":
        return cls(
            id=executor_id,
            type=executor_type,
            capabilities=[str(item) for item in (capabilities or (tool_plan or {}).get("capabilities", [])) if str(item).strip()],
            agent_profile_ref=agent_profile_ref,
            tool_plan=copy_mapping(tool_plan),
            tool_invocation_mode=tool_invocation_mode,
            tool_policy_ref=tool_policy_ref,
            timeout_s=timeout_s,
            retry_policy=copy_mapping(retry_policy),
            approval_policy=copy_mapping(approval_policy),
            streaming_required=streaming_required,
            status=status,
        )

    def update(self, **changes: Any) -> "ExecutorBinding":
        for key in [
            "type",
            "agent_profile_ref",
            "tool_invocation_mode",
            "tool_policy_ref",
            "timeout_s",
            "streaming_required",
            "status",
        ]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "capabilities" in changes and changes["capabilities"] is not None:
            self.capabilities = [str(item) for item in changes["capabilities"] if str(item).strip()]
        if "tool_plan" in changes and changes["tool_plan"] is not None:
            self.tool_plan = copy_mapping(changes["tool_plan"])
            if "capabilities" not in changes and self.tool_plan.get("capabilities") is not None:
                self.capabilities = [str(item) for item in self.tool_plan.get("capabilities", []) if str(item).strip()]
        if "retry_policy" in changes and changes["retry_policy"] is not None:
            self.retry_policy = copy_mapping(changes["retry_policy"])
        if "approval_policy" in changes and changes["approval_policy"] is not None:
            self.approval_policy = copy_mapping(changes["approval_policy"])
        if self.type not in EXECUTOR_TYPES:
            raise ValueError(f"不合法的 executor type：{self.type}")
        if self.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{self.status}")
        self.touch()
        return self

    def clone(self, *, new_id: str | None = None) -> "ExecutorBinding":
        payload = self.clone_payload()
        if new_id:
            payload["id"] = new_id
        return ExecutorBinding.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "type": self.type,
            "capabilities": list(self.capabilities),
            "agent_profile_ref": self.agent_profile_ref,
            "tool_plan": copy_mapping(self.tool_plan),
            "tool_invocation_mode": self.tool_invocation_mode,
            "tool_policy_ref": self.tool_policy_ref,
            "timeout_s": self.timeout_s,
            "retry_policy": copy_mapping(self.retry_policy),
            "approval_policy": copy_mapping(self.approval_policy),
            "streaming_required": self.streaming_required,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutorBinding":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            version=int(payload.get("version") or 1),
            type=str(payload.get("type") or "llm"),
            capabilities=[str(item) for item in (payload.get("capabilities") or []) if str(item).strip()],
            agent_profile_ref=payload.get("agent_profile_ref"),
            tool_plan=copy_mapping(payload.get("tool_plan")),
            tool_invocation_mode=payload.get("tool_invocation_mode"),
            tool_policy_ref=payload.get("tool_policy_ref"),
            timeout_s=int(payload.get("timeout_s") or 180),
            retry_policy=copy_mapping(payload.get("retry_policy")),
            approval_policy=copy_mapping(payload.get("approval_policy")),
            streaming_required=bool(payload.get("streaming_required", True)),
            status=str(payload.get("status") or "draft"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if not entity.capabilities and entity.tool_plan.get("capabilities") is not None:
            entity.capabilities = [str(item) for item in entity.tool_plan.get("capabilities", []) if str(item).strip()]
        if entity.type not in EXECUTOR_TYPES:
            raise ValueError(f"不合法的 executor type：{entity.type}")
        if entity.status not in DEFINITION_STATUSES:
            raise ValueError(f"不合法的 definition status：{entity.status}")
        return entity
