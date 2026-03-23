"""Shared runtime context for vNext executor dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class RuntimeExecutionContext:
    core: Any
    project_path: Path
    run_id: str
    variables: dict[str, Any]
    stream_handler: Callable[[str], None] | None = None
    request_id: str | None = None
    thread_id: str | None = None
    event_sink: Callable[[dict[str, Any]], None] | None = None
    render_context: Callable[[Any, dict[str, Any]], dict[str, Any]] | None = None
    render_payload: Callable[[Any, dict[str, Any]], Any] | None = None
    build_conversation_history: Callable[[Any, dict[str, Any], dict[str, Any]], list[dict[str, str]]] | None = None

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        if callable(self.event_sink):
            self.event_sink({"event": event, "payload": payload})
