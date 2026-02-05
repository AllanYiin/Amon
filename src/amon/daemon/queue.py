"""Action queue for asynchronous hook dispatch."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from amon.hooks.runner import execute_hook_action


logger = logging.getLogger(__name__)

ActionExecutor = Callable[[dict[str, Any]], None]


@dataclass
class ActionQueue:
    tool_executor: Callable[[str, dict[str, Any], str | None], dict[str, Any]] | None = None
    graph_runner: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None
    data_dir: Path | None = None
    allow_llm: bool = False
    worker_count: int = 1
    _queue: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _workers: list[threading.Thread] = field(default_factory=list, init=False)

    def start(self) -> None:
        if self._workers:
            return
        for index in range(max(self.worker_count, 1)):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"amon-action-worker-{index}",
                daemon=True,
            )
            self._workers.append(thread)
            thread.start()

    def stop(self) -> None:
        if not self._workers:
            return
        self._stop_event.set()
        for thread in self._workers:
            thread.join(timeout=5)
        self._workers.clear()
        self._stop_event.clear()

    def enqueue_action(self, action: dict[str, Any]) -> str:
        payload = dict(action or {})
        action_id = str(payload.get("action_id") or uuid4().hex)
        payload["action_id"] = action_id
        self._queue.put(payload)
        return action_id

    def wait_for_idle(self, timeout: float | None = None) -> bool:
        start = time.monotonic()
        while True:
            if self._queue.unfinished_tasks == 0:
                return True
            if timeout is not None and (time.monotonic() - start) > timeout:
                return False
            time.sleep(0.05)

    def _worker_loop(self) -> None:
        while True:
            if self._stop_event.is_set() and self._queue.empty():
                break
            try:
                action = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                execute_hook_action(
                    action,
                    tool_executor=self.tool_executor,
                    graph_runner=self.graph_runner,
                    data_dir=self.data_dir,
                    allow_llm=self.allow_llm,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("執行 action 失敗：%s", exc, exc_info=True)
            finally:
                self._queue.task_done()


_DEFAULT_QUEUE: ActionQueue | None = None


def configure_action_queue(
    *,
    tool_executor: Callable[[str, dict[str, Any], str | None], dict[str, Any]] | None = None,
    graph_runner: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    data_dir: Path | None = None,
    allow_llm: bool = False,
    worker_count: int = 1,
) -> ActionQueue:
    global _DEFAULT_QUEUE
    if _DEFAULT_QUEUE:
        _DEFAULT_QUEUE.stop()
    _DEFAULT_QUEUE = ActionQueue(
        tool_executor=tool_executor,
        graph_runner=graph_runner,
        data_dir=data_dir,
        allow_llm=allow_llm,
        worker_count=worker_count,
    )
    _DEFAULT_QUEUE.start()
    return _DEFAULT_QUEUE


def get_action_queue() -> ActionQueue:
    global _DEFAULT_QUEUE
    if _DEFAULT_QUEUE is None:
        _DEFAULT_QUEUE = ActionQueue()
        _DEFAULT_QUEUE.start()
    return _DEFAULT_QUEUE


def enqueue_action(action: dict[str, Any]) -> str:
    return get_action_queue().enqueue_action(action)
