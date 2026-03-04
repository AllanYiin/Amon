"""Runner step dispatch stub for `amon run step6`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunStepResult:
    step: str = "step6"
    status: str = "succeeded"


def dispatch_step6(task: str) -> RunStepResult:
    """Return a deterministic mock execution result for step6."""
    if not task.strip():
        raise ValueError("task must not be empty")
    return RunStepResult()
