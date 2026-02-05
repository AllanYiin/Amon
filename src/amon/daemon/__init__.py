"""Amon daemon loop for automation tasks."""

from __future__ import annotations

import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

from amon.core import AmonCore
from amon.events import emit_event
from amon.hooks.runner import process_event
from amon.jobs.runner import start_job
from amon.logging import log_event
from amon.scheduler.engine import tick

from .queue import configure_action_queue


EventEmitter = Callable[[dict[str, Any]], str]


def run_daemon(
    *,
    data_dir: Path | None = None,
    tick_interval_seconds: int = 5,
    tool_executor: Callable[[str, dict[str, Any], str | None], dict[str, Any]] | None = None,
) -> None:
    core = AmonCore(data_dir=data_dir)
    core.ensure_base_structure()
    logger = core.logger
    os.environ.setdefault("AMON_DISABLE_HOOK_DISPATCH", "1")
    event_queue: deque[dict[str, Any]] = deque()
    started_jobs: set[str] = set()
    action_queue = configure_action_queue(tool_executor=tool_executor, data_dir=core.data_dir)

    def queue_emitter(event: dict[str, Any]) -> str:
        event_id = emit_event(event, dispatch_hooks=False)
        payload = dict(event)
        payload["event_id"] = event_id
        event_queue.append(payload)
        return event_id

    while True:
        try:
            _ensure_jobs_started(core.data_dir, started_jobs, queue_emitter)
            tick(data_dir=core.data_dir, event_emitter=queue_emitter)
            _drain_event_queue(core, event_queue)
        except Exception as exc:  # noqa: BLE001
            logger.error("Scheduler tick 失敗：%s", exc, exc_info=True)
        try:
            time.sleep(tick_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Daemon 已停止")
            break
    action_queue.stop()


def run_daemon_once(
    *,
    data_dir: Path | None = None,
    tool_executor: Callable[[str, dict[str, Any], str | None], dict[str, Any]] | None = None,
) -> None:
    core = AmonCore(data_dir=data_dir)
    core.ensure_base_structure()
    os.environ.setdefault("AMON_DISABLE_HOOK_DISPATCH", "1")
    event_queue: deque[dict[str, Any]] = deque()
    action_queue = configure_action_queue(tool_executor=tool_executor, data_dir=core.data_dir)

    def queue_emitter(event: dict[str, Any]) -> str:
        event_id = emit_event(event, dispatch_hooks=False)
        payload = dict(event)
        payload["event_id"] = event_id
        event_queue.append(payload)
        return event_id

    _ensure_jobs_started(core.data_dir, set(), queue_emitter)
    tick(data_dir=core.data_dir, event_emitter=queue_emitter)
    _drain_event_queue(core, event_queue)
    action_queue.wait_for_idle(timeout=10)
    action_queue.stop()


def _ensure_jobs_started(data_dir: Path, started_jobs: set[str], emitter: EventEmitter) -> None:
    jobs_dir = data_dir / "jobs"
    if not jobs_dir.exists():
        return
    for path in sorted(jobs_dir.glob("*.yaml")):
        job_id = path.stem
        if job_id in started_jobs:
            continue
        try:
            start_job(job_id, data_dir=data_dir, event_emitter=emitter)
            started_jobs.add(job_id)
            log_event({"event": "job_started", "job_id": job_id})
        except Exception as exc:  # noqa: BLE001
            log_event({"level": "ERROR", "event": "job_start_failed", "job_id": job_id, "error": str(exc)})


def _drain_event_queue(
    core: AmonCore,
    event_queue: deque[dict[str, Any]],
) -> None:
    while event_queue:
        event = event_queue.popleft()
        try:
            results = process_event(
                event,
                data_dir=core.data_dir,
                allow_llm=False,
            )
            log_event(
                {
                    "event": "automation_event_processed",
                    "event_id": event.get("event_id"),
                    "event_type": event.get("type"),
                    "actions": results,
                }
            )
        except Exception as exc:  # noqa: BLE001
            log_event(
                {
                    "level": "ERROR",
                    "event": "automation_event_failed",
                    "event_id": event.get("event_id"),
                    "event_type": event.get("type"),
                    "error": str(exc),
                }
            )
