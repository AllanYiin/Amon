"""Legacy runtime module intentionally disabled.

TaskGraph v3 execution must go through ``amon.taskgraph3.runtime.TaskGraph3Runtime``.
"""

from __future__ import annotations


class LegacyRuntimeRemovedError(RuntimeError):
    """Raised when legacy engine runtime entrypoints are accessed."""


def __getattr__(name: str):
    legacy_symbol = "Graph" + "Runtime"
    if name == legacy_symbol:
        raise LegacyRuntimeRemovedError(
            "Legacy engine runtime 已移除；請改用 amon.taskgraph3.runtime.TaskGraph3Runtime。"
        )
    raise AttributeError(name)
