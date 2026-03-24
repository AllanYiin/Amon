"""Canonical compiled node metadata contract shared by compiler and runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .entities import AgentProfile, ExecutorBinding, TaskDefinition, ToolPolicy
from .entities.base import copy_list, copy_mapping

_TASK_SPEC_EXECUTOR_FALLBACK = {
    "agent": "llm",
    "tool": "tool",
    "sandbox_run": "sandbox",
}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _default_tool_invocation_mode(executor_type: str) -> str:
    return "delegated" if executor_type == "llm" else "deterministic"


@dataclass(frozen=True)
class CompiledNodeMetadata:
    task_ref: str = ""
    task_version: int | None = None
    executor_ref: str = ""
    executor_version: int | None = None
    executor_type: str = ""
    streaming_required: bool = True
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    tool_invocation_mode: str | None = None
    tool_policy: dict[str, Any] | None = None
    agent_profile_ref: str | None = None
    agent_profile_version: int | None = None
    timeout_s: int | None = None
    approval_policy: dict[str, Any] = field(default_factory=dict)
    retry_policy: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_compile_inputs(
        cls,
        *,
        task: TaskDefinition,
        executor: ExecutorBinding,
        agent_profile: AgentProfile | None = None,
        tool_policy: ToolPolicy | None = None,
    ) -> "CompiledNodeMetadata":
        return cls(
            task_ref=task.id,
            task_version=task.version,
            executor_ref=executor.id,
            executor_version=executor.version,
            executor_type=str(executor.type or "").strip().lower(),
            streaming_required=bool(executor.streaming_required),
            required_capabilities=tuple(str(item) for item in task.required_capabilities if str(item).strip()),
            tool_invocation_mode=_optional_str(executor.tool_invocation_mode),
            tool_policy=tool_policy.to_dict() if tool_policy is not None else None,
            agent_profile_ref=_optional_str(executor.agent_profile_ref),
            agent_profile_version=agent_profile.version if agent_profile is not None else None,
            timeout_s=int(executor.timeout_s),
            approval_policy=copy_mapping(executor.approval_policy),
            retry_policy=copy_mapping(executor.retry_policy),
        )

    @classmethod
    def from_node(cls, node: Any) -> "CompiledNodeMetadata":
        metadata = node.metadata if isinstance(getattr(node, "metadata", None), dict) else {}
        executor_type = _optional_str(metadata.get("executor_type")) or _infer_executor_type_from_node(node)
        tool_invocation_mode = _optional_str(metadata.get("tool_invocation_mode"))
        if executor_type and tool_invocation_mode is None:
            tool_invocation_mode = _default_tool_invocation_mode(executor_type)
        policy_payload = metadata.get("tool_policy")
        return cls(
            task_ref=str(metadata.get("task_ref") or ""),
            task_version=_optional_int(metadata.get("task_version")),
            executor_ref=str(metadata.get("executor_ref") or ""),
            executor_version=_optional_int(metadata.get("executor_version")),
            executor_type=str(executor_type or ""),
            streaming_required=bool(metadata.get("streaming_required", True)),
            required_capabilities=tuple(
                str(item) for item in metadata.get("required_capabilities", []) if str(item).strip()
            ),
            tool_invocation_mode=tool_invocation_mode,
            tool_policy=copy_mapping(policy_payload) if isinstance(policy_payload, dict) else None,
            agent_profile_ref=_optional_str(metadata.get("agent_profile_ref")),
            agent_profile_version=_optional_int(metadata.get("agent_profile_version")),
            timeout_s=_optional_int(metadata.get("timeout_s")),
            approval_policy=copy_mapping(metadata.get("approval_policy")),
            retry_policy=copy_mapping(metadata.get("retry_policy")),
        )

    @property
    def runtime_executor_type(self) -> str:
        return str(self.executor_type or "")

    @property
    def runtime_tool_invocation_mode(self) -> str:
        if self.tool_invocation_mode:
            return self.tool_invocation_mode
        return _default_tool_invocation_mode(self.runtime_executor_type)

    @property
    def parsed_tool_policy(self) -> ToolPolicy | None:
        if not isinstance(self.tool_policy, dict):
            return None
        return ToolPolicy.from_dict(self.tool_policy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_ref": self.task_ref,
            "task_version": self.task_version,
            "executor_ref": self.executor_ref,
            "executor_version": self.executor_version,
            "executor_type": self.executor_type,
            "streaming_required": self.streaming_required,
            "required_capabilities": copy_list(list(self.required_capabilities)),
            "tool_invocation_mode": self.tool_invocation_mode,
            "tool_policy": copy_mapping(self.tool_policy) if isinstance(self.tool_policy, dict) else None,
            "agent_profile_ref": self.agent_profile_ref,
            "agent_profile_version": self.agent_profile_version,
            "timeout_s": self.timeout_s,
            "approval_policy": copy_mapping(self.approval_policy),
            "retry_policy": copy_mapping(self.retry_policy),
        }


def _infer_executor_type_from_node(node: Any) -> str:
    task_spec = getattr(node, "task_spec", None)
    executor = str(getattr(task_spec, "executor", "") or "").strip().lower()
    return _TASK_SPEC_EXECUTOR_FALLBACK.get(executor, "")
