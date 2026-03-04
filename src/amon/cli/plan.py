"""Planner step dispatch stubs for `amon plan` (step1..step5)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanStepResult:
    step: str
    output_dir: str


def dispatch_step(step: str, task: str, out_dir: str) -> PlanStepResult:
    """Return a normalized stub result for plan step execution."""
    if step not in {"step1", "step2", "step3", "step4", "step5"}:
        raise ValueError(f"Unsupported plan step: {step}")
    if not task.strip():
        raise ValueError("task must not be empty")
    return PlanStepResult(step=step, output_dir=out_dir)
