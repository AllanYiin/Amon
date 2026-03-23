"""Capability -> executor resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from amon.domain import AmonManifest, ExecutorBinding, TaskDefinition


_SIDE_EFFECT_ORDER = {
    "read_only": 0,
    "workspace_write": 1,
    "destructive_write": 2,
    "external_network": 3,
    "sandbox_exec": 4,
}


@dataclass(frozen=True)
class CapabilityMatch:
    executor: ExecutorBinding
    covered_capabilities: set[str] = field(default_factory=set)


class CapabilityRegistry:
    def __init__(self, executors: dict[str, ExecutorBinding]) -> None:
        self._executors = executors

    @classmethod
    def from_manifest(cls, manifest: AmonManifest) -> "CapabilityRegistry":
        return cls(executors=dict(manifest.executors))

    def candidates_for_task(self, task: TaskDefinition) -> list[CapabilityMatch]:
        required = {item for item in task.required_capabilities if item}
        matches: list[CapabilityMatch] = []
        for executor in self._executors.values():
            if executor.status != "active":
                continue
            declared = {item for item in executor.capabilities if item}
            if required and not required.issubset(declared):
                continue
            match = CapabilityMatch(executor=executor, covered_capabilities=declared)
            if self._sort_key(match, task)[0] >= 99:
                continue
            matches.append(match)
        matches.sort(key=lambda item: self._sort_key(item, task))
        return matches

    def resolve_executor(self, task: TaskDefinition) -> ExecutorBinding | None:
        matches = self.candidates_for_task(task)
        return matches[0].executor if matches else None

    def _sort_key(self, match: CapabilityMatch, task: TaskDefinition) -> tuple[int, int, int, str]:
        executor = match.executor
        tool_penalty = 1 if executor.type == "tool" else 0
        streaming_penalty = 0 if executor.streaming_required else 1
        side_effect_penalty = self._side_effect_distance(task.side_effect_class, executor)
        coverage_penalty = len(match.covered_capabilities - set(task.required_capabilities))
        return (side_effect_penalty, tool_penalty + streaming_penalty, coverage_penalty, executor.id)

    def _side_effect_distance(self, side_effect_class: str, executor: ExecutorBinding) -> int:
        target = _SIDE_EFFECT_ORDER.get(side_effect_class or "read_only", 0)
        if executor.type == "llm":
            ceiling = _SIDE_EFFECT_ORDER.get("read_only", 0)
        elif executor.type == "tool":
            ceiling = _SIDE_EFFECT_ORDER.get("workspace_write", 1)
        elif executor.type == "sandbox":
            ceiling = _SIDE_EFFECT_ORDER.get("sandbox_exec", 4)
        else:
            ceiling = target
        if ceiling < target:
            return 99
        return ceiling - target
