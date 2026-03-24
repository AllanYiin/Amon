"""Policy-aware executor compatibility checks for binding."""

from __future__ import annotations

from dataclasses import dataclass

from amon.domain import ExecutorBinding, TaskDefinition, ToolPolicy

_SIDE_EFFECT_ORDER = {
    "read_only": 0,
    "workspace_write": 1,
    "destructive_write": 2,
    "external_network": 3,
    "sandbox_exec": 4,
}

_LEGACY_CEILINGS = {
    "llm": "read_only",
    "tool": "workspace_write",
    "sandbox": "sandbox_exec",
    "human_gate": "read_only",
}


@dataclass(frozen=True)
class EffectiveExecutorPolicy:
    side_effect_ceiling: str
    allow_network: bool
    delegated_allowed: bool
    source: str
    tool_policy: ToolPolicy | None = None


@dataclass(frozen=True)
class PolicyCompatibilityResult:
    allowed: bool
    reason: str = ""
    effective_policy: EffectiveExecutorPolicy | None = None


def resolve_effective_executor_policy(
    executor: ExecutorBinding,
    tool_policies: dict[str, ToolPolicy],
) -> EffectiveExecutorPolicy:
    policy_ref = str(executor.tool_policy_ref or "").strip()
    if policy_ref:
        policy = tool_policies.get(policy_ref)
        if policy is not None and policy.status == "active":
            return EffectiveExecutorPolicy(
                side_effect_ceiling=str(policy.side_effect_ceiling or "read_only"),
                allow_network=bool(policy.allow_network),
                delegated_allowed=bool(policy.delegated_allowed),
                source="tool_policy",
                tool_policy=policy,
            )
    return EffectiveExecutorPolicy(
        side_effect_ceiling=_LEGACY_CEILINGS.get(str(executor.type or "").strip().lower(), "read_only"),
        allow_network=False,
        delegated_allowed=False,
        source="legacy_fallback",
        tool_policy=None,
    )


def evaluate_executor_policy_compatibility(
    task: TaskDefinition,
    executor: ExecutorBinding,
    tool_policies: dict[str, ToolPolicy],
) -> PolicyCompatibilityResult:
    effective = resolve_effective_executor_policy(executor, tool_policies)
    required_class = str(task.side_effect_class or "read_only")
    invocation_mode = str(executor.tool_invocation_mode or "").strip().lower()

    if _side_effect_value(effective.side_effect_ceiling) < _side_effect_value(required_class):
        return PolicyCompatibilityResult(
            allowed=False,
            reason=(
                f"executor policy ceiling 不足：executor_ref={executor.id}, "
                f"required={required_class}, ceiling={effective.side_effect_ceiling}"
            ),
            effective_policy=effective,
        )

    if required_class == "external_network" and not effective.allow_network:
        return PolicyCompatibilityResult(
            allowed=False,
            reason=f"executor policy 不允許 external_network：executor_ref={executor.id}",
            effective_policy=effective,
        )

    if invocation_mode == "delegated" and not effective.delegated_allowed:
        return PolicyCompatibilityResult(
            allowed=False,
            reason=f"executor policy 不允許 delegated tool invocation：executor_ref={executor.id}",
            effective_policy=effective,
        )

    return PolicyCompatibilityResult(allowed=True, effective_policy=effective)


def _side_effect_value(name: str) -> int:
    return _SIDE_EFFECT_ORDER.get(str(name or "read_only"), 0)
