"""Capability -> executor resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from amon.domain import AmonManifest, ExecutorBinding, TaskDefinition, ToolPolicy, is_compilable_executor_type

from .executor_policy_compatibility import evaluate_executor_policy_compatibility

_EXECUTOR_TYPE_PRIORITY = {
    "llm": 0,
    "tool": 1,
    "sandbox": 2,
    "human_gate": 3,
}


@dataclass(frozen=True)
class CapabilityMatch:
    executor: ExecutorBinding
    covered_capabilities: set[str] = field(default_factory=set)


class CapabilityRegistry:
    def __init__(self, executors: dict[str, ExecutorBinding], tool_policies: dict[str, ToolPolicy] | None = None) -> None:
        self._executors = executors
        self._tool_policies = tool_policies or {}

    @classmethod
    def from_manifest(cls, manifest: AmonManifest) -> "CapabilityRegistry":
        return cls(executors=dict(manifest.executors), tool_policies=dict(manifest.tool_policies))

    def candidates_for_task(self, task: TaskDefinition) -> list[CapabilityMatch]:
        required = {item for item in task.required_capabilities if item}
        matches: list[CapabilityMatch] = []
        for executor in self._executors.values():
            if executor.status != "active":
                continue
            if not is_compilable_executor_type(executor.type):
                continue
            declared = {item for item in executor.capabilities if item}
            if required and not required.issubset(declared):
                continue
            compatibility = evaluate_executor_policy_compatibility(task, executor, self._tool_policies)
            if not compatibility.allowed:
                continue
            match = CapabilityMatch(executor=executor, covered_capabilities=declared)
            matches.append(match)
        matches.sort(key=lambda item: self._sort_key(item, task))
        return matches

    def resolve_executor(self, task: TaskDefinition) -> ExecutorBinding | None:
        matches = self.candidates_for_task(task)
        return matches[0].executor if matches else None

    def _sort_key(self, match: CapabilityMatch, task: TaskDefinition) -> tuple[int, int, int, str]:
        executor = match.executor
        type_penalty = _EXECUTOR_TYPE_PRIORITY.get(str(executor.type or "").strip().lower(), 99)
        streaming_penalty = 0 if executor.streaming_required else 1
        effective = evaluate_executor_policy_compatibility(task, executor, self._tool_policies).effective_policy
        side_effect_penalty = self._side_effect_distance(task.side_effect_class, effective.side_effect_ceiling if effective else "read_only")
        coverage_penalty = len(match.covered_capabilities - set(task.required_capabilities))
        return (side_effect_penalty, type_penalty + streaming_penalty, coverage_penalty, executor.id)

    @staticmethod
    def _side_effect_distance(side_effect_class: str, ceiling: str) -> int:
        target_value = _side_effect_value(side_effect_class)
        ceiling_value = _side_effect_value(ceiling)
        return max(0, ceiling_value - target_value)


def _side_effect_value(name: str) -> int:
    return {
        "read_only": 0,
        "workspace_write": 1,
        "destructive_write": 2,
        "external_network": 3,
        "sandbox_exec": 4,
    }.get(str(name or "read_only"), 0)
