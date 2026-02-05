"""Amon daemon loop for scheduler ticks."""

from __future__ import annotations

import time
from pathlib import Path

from amon.core import AmonCore
from amon.scheduler.engine import tick


def run_daemon(*, data_dir: Path | None = None, tick_interval_seconds: int = 5) -> None:
    core = AmonCore(data_dir=data_dir)
    core.ensure_base_structure()
    logger = core.logger

    while True:
        try:
            tick(data_dir=core.data_dir)
        except Exception as exc:  # noqa: BLE001
            logger.error("Scheduler tick 失敗：%s", exc, exc_info=True)
        try:
            time.sleep(tick_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Daemon 已停止")
            break
