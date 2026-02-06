"""Run steering context utilities."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.logging import log_event
from amon.fs.safety import validate_run_id


def append_run_constraints(run_id: str, constraints: list[str]) -> None:
    """Append run context constraints to the run events log."""
    validate_run_id(run_id)
    if not isinstance(constraints, list) or any(not isinstance(item, str) for item in constraints):
        raise ValueError("constraints 必須為字串陣列")

    run_dir = _resolve_run_dir(run_id)
    events_path = run_dir / "events.jsonl"
    payload = {
        "event": "run_context_update",
        "run_id": run_id,
        "constraints": constraints,
        "ts": _now_iso(),
    }
    try:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except OSError as exc:
        log_event(
            {
                "level": "ERROR",
                "event": "run_context_update_failed",
                "run_id": run_id,
                "error": str(exc),
            }
        )
        raise


def get_effective_constraints(run_id: str) -> list[str]:
    """Return the latest constraints from run events."""
    validate_run_id(run_id)

    run_dir = _resolve_run_dir(run_id)
    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        return []

    latest: list[str] = []
    try:
        with events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("event") == "run_context_update":
                    constraints = payload.get("constraints")
                    if isinstance(constraints, list) and all(isinstance(item, str) for item in constraints):
                        latest = constraints
    except OSError as exc:
        log_event(
            {
                "level": "ERROR",
                "event": "run_context_read_failed",
                "run_id": run_id,
                "error": str(exc),
            }
        )
        raise
    return latest


def _resolve_run_dir(run_id: str) -> Path:
    project_path = os.environ.get("AMON_PROJECT_PATH")
    if project_path:
        candidate = Path(project_path).expanduser() / ".amon" / "runs" / run_id
        if candidate.exists():
            return candidate

    data_dir = Path(os.environ.get("AMON_HOME", "~/.amon")).expanduser()
    projects_dir = data_dir / "projects"
    if projects_dir.exists():
        for candidate in projects_dir.glob(f"*/.amon/runs/{run_id}"):
            if candidate.exists():
                return candidate
    raise FileNotFoundError("找不到指定的 run")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
