"""Backpressure checks for trigger-created runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amon.domain.entities.run_record import RUN_STATUSES
from amon.storage.repositories.run_repo import RunRepository


TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "rolled_back", "archived"}


@dataclass(frozen=True)
class BackpressureDecision:
    allowed: bool
    reason: str | None
    active_runs: int


def count_active_trigger_runs(project_root: Path, *, trigger_kind: str, trigger_id: str) -> int:
    repository = RunRepository(project_root)
    total = 0
    for run in repository.list():
        if run.status not in RUN_STATUSES or run.status in TERMINAL_RUN_STATUSES:
            continue
        if str(run.trigger.get("kind") or "") != str(trigger_kind):
            continue
        if str(run.trigger.get("id") or "") != str(trigger_id):
            continue
        total += 1
    return total


def check_backpressure(
    project_root: Path,
    *,
    trigger_kind: str,
    trigger_id: str,
    max_active_runs: int | None = None,
    max_queue_depth: int | None = None,
) -> BackpressureDecision:
    active_runs = count_active_trigger_runs(
        project_root,
        trigger_kind=trigger_kind,
        trigger_id=trigger_id,
    )
    if max_active_runs is not None and active_runs >= max(max_active_runs, 0):
        return BackpressureDecision(False, "max_active_runs", active_runs)
    if max_queue_depth is not None and active_runs >= max(max_queue_depth, 0):
        return BackpressureDecision(False, "max_queue_depth", active_runs)
    return BackpressureDecision(True, None, active_runs)
