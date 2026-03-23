"""Canonical planner contract for manifest v1 logical workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


FORBIDDEN_PLANNER_FIELDS = frozenset({"agent", "agent_id", "persona", "owner", "assignment", "assignee"})


class PlannerContractError(ValueError):
    """Raised when the planner emits fields outside the logical workflow contract."""

    def __init__(self, message: str, *, code: str = "AMON_PLANNER_001") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PlanningStreamEvent:
    event: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class LogicalTaskPlan:
    id: str
    title: str
    goal: str
    required_capabilities: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    input_contract: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    side_effect_class: str = "read_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "goal": self.goal,
            "required_capabilities": list(self.required_capabilities),
            "acceptance_criteria": list(self.acceptance_criteria),
            "depends_on": list(self.depends_on),
            "input_contract": dict(self.input_contract),
            "output_contract": dict(self.output_contract),
            "side_effect_class": self.side_effect_class,
        }


@dataclass(frozen=True)
class LogicalWorkflowPlan:
    id: str
    name: str
    tasks: list[LogicalTaskPlan]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "tasks": [task.to_dict() for task in self.tasks]}


def validate_planner_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PlannerContractError("planner payload 必須是 object")
    _reject_forbidden_fields(payload)
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise PlannerContractError("planner payload 必須包含非空 tasks")
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise PlannerContractError(f"planner task 必須是 object：index={index}")
        task_id = str(task.get("id") or "").strip()
        goal = str(task.get("goal") or "").strip()
        if not task_id:
            raise PlannerContractError(f"planner task.id 不可為空：index={index}")
        if not goal:
            raise PlannerContractError(f"planner task.goal 不可為空：task_id={task_id}")
        required_capabilities = task.get("required_capabilities")
        if not isinstance(required_capabilities, list):
            raise PlannerContractError(f"planner task.required_capabilities 必須是 list：task_id={task_id}")
        acceptance_criteria = task.get("acceptance_criteria")
        if acceptance_criteria is not None and not isinstance(acceptance_criteria, list):
            raise PlannerContractError(f"planner task.acceptance_criteria 必須是 list：task_id={task_id}")
    return payload


def logical_workflow_from_payload(
    payload: dict[str, Any],
    *,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
) -> LogicalWorkflowPlan:
    validated = validate_planner_payload(payload)
    tasks = [
        LogicalTaskPlan(
            id=str(item.get("id") or "").strip(),
            title=str(item.get("title") or item.get("goal") or "").strip(),
            goal=str(item.get("goal") or "").strip(),
            required_capabilities=[str(cap).strip() for cap in item.get("required_capabilities", []) if str(cap).strip()],
            acceptance_criteria=[str(criteria).strip() for criteria in item.get("acceptance_criteria", []) if str(criteria).strip()],
            depends_on=[str(dep).strip() for dep in item.get("depends_on", []) if str(dep).strip()],
            input_contract=item.get("input_contract") if isinstance(item.get("input_contract"), dict) else {},
            output_contract=item.get("output_contract") if isinstance(item.get("output_contract"), dict) else {},
            side_effect_class=str(item.get("side_effect_class") or "read_only"),
        )
        for item in validated["tasks"]
    ]
    inferred_id = str(validated.get("id") or workflow_id or "workflow.planned").strip()
    inferred_name = str(validated.get("name") or workflow_name or inferred_id).strip()
    if not inferred_id:
        raise PlannerContractError("workflow_id 不可為空")
    return LogicalWorkflowPlan(id=inferred_id, name=inferred_name, tasks=tasks)


def build_planning_stream_events(
    chunks: Iterable[str],
    *,
    run_id: str | None = None,
    node_id: str = "__planner__",
) -> list[PlanningStreamEvent]:
    events: list[PlanningStreamEvent] = []
    for index, chunk in enumerate(chunks):
        text = str(chunk)
        if not text:
            continue
        events.append(
            PlanningStreamEvent(
                event="node.chunk",
                payload={
                    "run_id": run_id,
                    "node_id": node_id,
                    "chunk_index": index,
                    "text": text,
                },
            )
        )
    events.append(
        PlanningStreamEvent(
            event="plan_generated",
            payload={"run_id": run_id, "node_id": node_id, "chunk_count": len(events)},
        )
    )
    return events


def _reject_forbidden_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_PLANNER_FIELDS:
                raise PlannerContractError(
                    f"planner emitted forbidden field：path={path}.{key}",
                )
            _reject_forbidden_fields(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_fields(item, path=f"{path}[{index}]")
