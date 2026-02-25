"""Simple UI server for Amon."""

from __future__ import annotations

import functools
import json
import mimetypes
import re
import sys
import threading
import time
import traceback
import uuid
from collections import deque
from datetime import date, datetime, timezone

import yaml
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from amon.chat.cli import _build_plan_from_message
from amon.chat.continuation import assemble_chat_turn, is_short_continuation_message
from amon.chat.project_bootstrap import (
    bootstrap_project_if_needed,
    resolve_project_id_from_message,
)
from amon.chat.router import route_intent
from amon.chat.execution_mode import decide_execution_mode
from amon.chat.router_llm import should_continue_run_with_llm
from amon.chat.router_types import RouterResult
from amon.chat.session_store import (
    append_event,
    create_chat_session,
)
from amon.commands.executor import CommandPlan, execute
from amon.config import ConfigLoader
from amon.daemon.queue import get_queue_depth
from amon.events import emit_event
from amon.jobs.runner import start_job
from amon.observability import ensure_correlation_fields, normalize_project_id
from amon.tooling.audit import default_audit_log_path
from amon.tooling.types import ToolCall
from .core import AmonCore, ProjectRecord
from .logging import log_event
from .models import decode_reasoning_chunk
from .skills import build_skill_injection_preview
from .token_counter import count_non_dialogue_tokens, extract_dialogue_input_tokens



_CHAT_STREAM_INIT_LOCK = threading.Lock()
_CHAT_STREAM_INIT_TTL_S = 300
_CHAT_STREAM_INIT_STORE: dict[str, dict[str, Any]] = {}


def _create_chat_stream_token(*, message: str, project_id: str | None, chat_id: str | None) -> str:
    token = uuid.uuid4().hex
    now = time.time()
    payload = {"message": message, "project_id": project_id, "chat_id": chat_id, "created_at": now}
    with _CHAT_STREAM_INIT_LOCK:
        _CHAT_STREAM_INIT_STORE[token] = payload
        expired = [key for key, item in _CHAT_STREAM_INIT_STORE.items() if now - float(item.get("created_at") or now) > _CHAT_STREAM_INIT_TTL_S]
        for key in expired:
            _CHAT_STREAM_INIT_STORE.pop(key, None)
    return token


def _consume_chat_stream_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    now = time.time()
    with _CHAT_STREAM_INIT_LOCK:
        payload = _CHAT_STREAM_INIT_STORE.pop(token, None)
    if not payload:
        return None
    if now - float(payload.get("created_at") or now) > _CHAT_STREAM_INIT_TTL_S:
        return None
    return payload


class _TaskManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._run_cancel: dict[str, threading.Event] = {}

    def submit_run(
        self,
        *,
        request_id: str | None,
        core: AmonCore,
        project_path: Path,
        graph_path: str,
        variables: dict[str, Any],
        run_id: str,
    ) -> str:
        request_id = request_id or uuid.uuid4().hex
        cancel_event = threading.Event()
        with self._lock:
            self._tasks[request_id] = {
                "request_id": request_id,
                "status": "queued",
                "run_id": run_id,
                "type": "run",
            }
            self._run_cancel[run_id] = cancel_event

        def _run() -> None:
            try:
                with self._lock:
                    self._tasks[request_id]["status"] = "running"
                resolved_graph_path = Path(graph_path)
                if not resolved_graph_path.is_absolute():
                    resolved_graph_path = project_path / resolved_graph_path
                core.run_graph(
                    project_path=project_path,
                    graph_path=resolved_graph_path,
                    variables=variables,
                    run_id=run_id,
                    request_id=request_id,
                )
                with self._lock:
                    self._tasks[request_id]["status"] = "completed"
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._tasks[request_id]["status"] = "failed"
                    self._tasks[request_id]["error"] = str(exc)

        threading.Thread(target=_run, daemon=True).start()
        return request_id

    def submit_tool(
        self,
        *,
        request_id: str | None,
        core: AmonCore,
        tool_name: str,
        args: dict[str, Any],
        project_id: str | None,
    ) -> str:
        request_id = request_id or uuid.uuid4().hex
        with self._lock:
            self._tasks[request_id] = {
                "request_id": request_id,
                "status": "queued",
                "type": "tool",
            }

        def _run() -> None:
            try:
                with self._lock:
                    self._tasks[request_id]["status"] = "running"
                result = core.run_tool(tool_name, args, project_id=project_id)
                with self._lock:
                    self._tasks[request_id]["status"] = "completed"
                    self._tasks[request_id]["result"] = result
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._tasks[request_id]["status"] = "failed"
                    self._tasks[request_id]["error"] = str(exc)

        threading.Thread(target=_run, daemon=True).start()
        return request_id

    def submit_job(
        self,
        *,
        request_id: str | None,
        core: AmonCore,
        job_id: str,
    ) -> str:
        request_id = request_id or uuid.uuid4().hex
        with self._lock:
            self._tasks[request_id] = {
                "request_id": request_id,
                "status": "queued",
                "type": "job",
                "job_id": job_id,
            }

        def _run() -> None:
            try:
                with self._lock:
                    self._tasks[request_id]["status"] = "running"
                start_job(job_id, data_dir=core.data_dir)
                with self._lock:
                    self._tasks[request_id]["status"] = "completed"
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._tasks[request_id]["status"] = "failed"
                    self._tasks[request_id]["error"] = str(exc)

        threading.Thread(target=_run, daemon=True).start()
        return request_id

    def submit_schedule_tick(self, *, request_id: str | None, core: AmonCore) -> str:
        request_id = request_id or uuid.uuid4().hex
        with self._lock:
            self._tasks[request_id] = {
                "request_id": request_id,
                "status": "queued",
                "type": "schedule",
            }

        def _run() -> None:
            try:
                from amon.scheduler.engine import tick

                with self._lock:
                    self._tasks[request_id]["status"] = "running"
                tick(data_dir=core.data_dir)
                with self._lock:
                    self._tasks[request_id]["status"] = "completed"
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._tasks[request_id]["status"] = "failed"
                    self._tasks[request_id]["error"] = str(exc)

        threading.Thread(target=_run, daemon=True).start()
        return request_id

    def get_status(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            status = self._tasks.get(request_id)
            return dict(status) if status else None

    def cancel_run(self, run_id: str) -> None:
        with self._lock:
            cancel_event = self._run_cancel.get(run_id)
        if cancel_event:
            cancel_event.set()


_TASK_MANAGER = _TaskManager()


class _HealthMetrics:
    def __init__(self, window_seconds: int = 300) -> None:
        self._window_seconds = max(1, window_seconds)
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._request_timestamps: deque[float] = deque()
        self._error_timestamps: deque[float] = deque()

    def record_request(self, ts: float | None = None) -> None:
        now = ts if ts is not None else time.time()
        with self._lock:
            self._request_timestamps.append(now)
            self._trim(now)

    def record_error(self, ts: float | None = None) -> None:
        now = ts if ts is not None else time.time()
        with self._lock:
            self._error_timestamps.append(now)
            self._trim(now)

    def summary(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._trim(now)
            request_count = len(self._request_timestamps)
            error_count = len(self._error_timestamps)
        error_rate = (error_count / request_count) if request_count else 0.0
        return {
            "window_seconds": self._window_seconds,
            "request_count": request_count,
            "error_count": error_count,
            "error_rate": round(error_rate, 4),
            "uptime_seconds": int(now - self._started_at),
        }

    def _trim(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._request_timestamps and self._request_timestamps[0] < cutoff:
            self._request_timestamps.popleft()
        while self._error_timestamps and self._error_timestamps[0] < cutoff:
            self._error_timestamps.popleft()


_HEALTH_METRICS = _HealthMetrics()


def _build_health_payload() -> dict[str, Any]:
    metrics = _HEALTH_METRICS.summary()
    return {
        "status": "ok",
        "service": "amon-ui-server",
        "queue_depth": get_queue_depth(),
        "recent_error_rate": metrics,
        "observability": {
            "schema_version": "v0.1",
            "metrics_window_seconds": metrics["window_seconds"],
            "links": {
                "metrics": "/metrics",
            },
        },
    }


def _build_metrics_text() -> str:
    summary = _HEALTH_METRICS.summary()
    queue_depth = get_queue_depth()
    lines = [
        "# HELP amon_ui_queue_depth Number of pending UI async tasks.",
        "# TYPE amon_ui_queue_depth gauge",
        f"amon_ui_queue_depth {queue_depth}",
        "# HELP amon_ui_request_total Number of HTTP requests seen in the rolling window.",
        "# TYPE amon_ui_request_total gauge",
        f"amon_ui_request_total {summary['request_count']}",
        "# HELP amon_ui_error_total Number of HTTP error responses seen in the rolling window.",
        "# TYPE amon_ui_error_total gauge",
        f"amon_ui_error_total {summary['error_count']}",
        "# HELP amon_ui_error_rate Recent HTTP error rate in the rolling window.",
        "# TYPE amon_ui_error_rate gauge",
        f"amon_ui_error_rate {summary['error_rate']}",
        "",
    ]
    return "\n".join(lines)


def _resolve_command_plan_from_router(message: str, router_result: RouterResult) -> tuple[str, dict[str, Any]]:
    if router_result.api and isinstance(router_result.args, dict):
        return router_result.api, dict(router_result.args)
    return _build_plan_from_message(message, router_result.type)


def _should_continue_chat_run(*, project_id: str | None, last_assistant_text: str | None, user_message: str) -> bool:
    if is_short_continuation_message(user_message) and (last_assistant_text or "").strip():
        return True
    return should_continue_run_with_llm(
        project_id=project_id,
        last_assistant_text=last_assistant_text,
        user_message=user_message,
    )


def _is_duplicate_project_create(
    *,
    active_project: ProjectRecord | None,
    command_name: str,
    args: dict[str, Any],
) -> bool:
    if command_name != "projects.create" or not active_project:
        return False
    requested_name = " ".join(str(args.get("name", "")).split()).lower()
    if not requested_name:
        return False
    active_name = " ".join(active_project.name.split()).lower()
    active_project_id = active_project.project_id.lower()
    return requested_name in {active_name, active_project_id}


class AmonThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request: Any, client_address: tuple[str, int]) -> None:
        exc_type, _, _ = sys.exc_info()
        if exc_type and issubclass(exc_type, (BrokenPipeError, ConnectionResetError)):
            log_event(
                {
                    "level": "INFO",
                    "event": "ui_client_disconnected",
                    "client": client_address[0] if client_address else "unknown",
                }
            )
            return
        super().handle_error(request, client_address)


class AmonUIHandler(SimpleHTTPRequestHandler):
    _MAX_BODY_BYTES = 10 * 1024 * 1024
    def __init__(self, *args: Any, core: AmonCore, **kwargs: Any) -> None:
        self.core = core
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        _HEALTH_METRICS.record_request()
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, _build_health_payload())
            return
        if parsed.path == "/metrics":
            body = _build_metrics_text().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/v1/") or self.path.startswith("/api/"):
            self._handle_api_get()
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        _HEALTH_METRICS.record_request()
        if self.path.startswith("/v1/"):
            self._handle_api_post()
            return
        self.send_error(404, "Not Found")

    def do_PATCH(self) -> None:  # noqa: N802
        _HEALTH_METRICS.record_request()
        if self.path.startswith("/v1/"):
            self._handle_api_patch()
            return
        self.send_error(404, "Not Found")

    def do_PUT(self) -> None:  # noqa: N802
        _HEALTH_METRICS.record_request()
        if self.path.startswith("/v1/"):
            self._handle_api_put()
            return
        self.send_error(404, "Not Found")

    def do_DELETE(self) -> None:  # noqa: N802
        _HEALTH_METRICS.record_request()
        if self.path.startswith("/v1/"):
            self._handle_api_delete()
            return
        self.send_error(404, "Not Found")

    def _handle_api_get(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/docs" or parsed.path.startswith("/api/docs/"):
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip()
            if not project_id:
                self._send_json(400, {"message": "請提供 project_id"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
                docs = self._build_docs_catalog(project_id=project_id, project_path=project_path)
                if parsed.path == "/api/docs":
                    self._send_json(200, {"docs": docs})
                    return
                raw_doc_path = unquote(parsed.path.replace("/api/docs/", "", 1)).strip()
                if not raw_doc_path:
                    self._send_json(400, {"message": "請提供 doc_id_or_path"})
                    return
                selected = next((item for item in docs if item.get("path") == raw_doc_path or item.get("name") == raw_doc_path), None)
                if not selected:
                    self._send_json(404, {"message": "找不到文件"})
                    return
                resolved_path = self._resolve_doc_path(project_path, str(selected["path"]))
                content = resolved_path.read_text(encoding="utf-8")
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(
                200,
                {
                    "path": selected["path"],
                    "name": selected["name"],
                    "content": content,
                    "download_url": selected.get("download_url"),
                    "updated_at": selected.get("updated_at"),
                },
            )
            return
        if parsed.path == "/v1/queue/depth":
            self._send_json(200, {"depth": get_queue_depth()})
            return
        if parsed.path.startswith("/v1/runs/") and parsed.path.endswith("/status"):
            run_id = self._get_path_segment(parsed.path, 2)
            if not run_id:
                self._send_json(400, {"message": "無效的 run_id"})
                return
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip()
            if not project_id:
                self._send_json(400, {"message": "請提供 project_id"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
                status = self.core.get_run_status(project_path, run_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"run": status})
            return
        if parsed.path.startswith("/v1/runs/") and parsed.path.endswith("/artifacts"):
            run_id = self._get_path_segment(parsed.path, 2)
            if not run_id:
                self._send_json(400, {"message": "無效的 run_id"})
                return
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                _, project_path, artifacts = self._resolve_run_artifacts(run_id, project_id=project_id)
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"artifacts": [self._artifact_public_fields(item) for item in artifacts]})
            return
        if parsed.path.startswith("/v1/runs/") and "/artifacts/" in parsed.path:
            run_id = self._get_path_segment(parsed.path, 2)
            artifact_id = self._get_path_segment(parsed.path, 4)
            if not run_id or not artifact_id:
                self._send_json(400, {"message": "缺少 run_id 或 artifact_id"})
                return
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            inline = params.get("inline", ["false"])[0].lower() == "true"
            try:
                _, project_path, artifacts = self._resolve_run_artifacts(run_id, project_id=project_id)
                target = next((item for item in artifacts if item.get("id") == artifact_id or item.get("path") == artifact_id), None)
                if not target:
                    raise FileNotFoundError("找不到 artifact")
                body = self._resolve_allowed_project_path(Path(project_path), str(target["path"]), [Path(project_path) / "docs", Path(project_path) / "audits"]).read_bytes()
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            filename = str(target["name"])
            content_type = str(target.get("mime") or "application/octet-stream")
            disposition = "inline" if inline else "attachment"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'{disposition}; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/artifacts"):
            run_id = self._get_path_segment(parsed.path, 2)
            if not run_id:
                self._send_json(400, {"message": "無效的 run_id"})
                return
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                _, project_path, artifacts = self._resolve_run_artifacts(run_id, project_id=project_id, route_prefix="/api")
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"artifacts": [self._artifact_public_fields(item) for item in artifacts]})
            return
        if parsed.path.startswith("/api/runs/") and "/artifacts/" in parsed.path:
            run_id = self._get_path_segment(parsed.path, 2)
            artifact_id = self._get_path_segment(parsed.path, 4)
            if not run_id or not artifact_id:
                self._send_json(400, {"message": "缺少 run_id 或 artifact_id"})
                return
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            inline = params.get("inline", ["false"])[0].lower() == "true"
            try:
                _, project_path, artifacts = self._resolve_run_artifacts(run_id, project_id=project_id, route_prefix="/api")
                target = next((item for item in artifacts if item.get("id") == artifact_id or item.get("path") == artifact_id), None)
                if not target:
                    raise FileNotFoundError("找不到 artifact")
                body = self._resolve_allowed_project_path(Path(project_path), str(target["path"]), [Path(project_path) / "docs", Path(project_path) / "audits"]).read_bytes()
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            filename = str(target["name"])
            content_type = str(target.get("mime") or "application/octet-stream")
            disposition = "inline" if inline else "attachment"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'{disposition}; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path.startswith("/v1/jobs/") and parsed.path.endswith("/status"):
            job_id = self._get_path_segment(parsed.path, 2)
            if not job_id:
                self._send_json(400, {"message": "無效的 job_id"})
                return
            try:
                status = self.core.get_job_status(job_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"job": status})
            return
        if parsed.path.startswith("/v1/requests/") and parsed.path.endswith("/status"):
            request_id = self._get_path_segment(parsed.path, 2)
            if not request_id:
                self._send_json(400, {"message": "無效的 request_id"})
                return
            status = _TASK_MANAGER.get_status(request_id)
            if not status:
                self._send_json(404, {"message": "找不到 request"})
                return
            self._send_json(200, {"request": status})
            return
        if parsed.path == "/v1/chat/stream":
            self._handle_chat_stream(parsed)
            return
        if parsed.path == "/v1/billing/summary":
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                payload = self._build_billing_summary(project_id=project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path == "/v1/billing/series":
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                payload = self._build_billing_summary(project_id=project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"series": payload.get("run_trend", [])})
            return
        if parsed.path == "/v1/billing/stream":
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            self._handle_billing_stream(project_id=project_id)
            return
        if parsed.path == "/v1/projects":
            params = parse_qs(parsed.query)
            include_deleted = params.get("include_deleted", ["false"])[0].lower() == "true"
            records = self._list_projects_for_ui(include_deleted=include_deleted)
            self._send_json(200, {"projects": records})
            return
        if parsed.path == "/v1/runs":
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                runs = self._list_runs_for_ui(project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"runs": runs})
            return
        if parsed.path.startswith("/v1/runs/") and parsed.path.endswith("/graph"):
            run_id = self._get_path_segment(parsed.path, 2)
            if not run_id:
                self._send_json(400, {"message": "無效的 run_id"})
                return
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                payload = self._load_run_bundle(run_id=run_id, project_id=project_id)
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(
                200,
                {
                    "run_id": payload["run_id"],
                    "run_status": payload["run_status"],
                    "graph": payload["graph"],
                    "graph_mermaid": self._graph_to_mermaid(payload["graph"]),
                    "node_states": payload["node_states"],
                    "recent_events": payload["recent_events"],
                },
            )
            return
        if parsed.path.startswith("/v1/runs/") and "/nodes/" in parsed.path:
            run_id = self._get_path_segment(parsed.path, 2)
            node_id = self._get_path_segment(parsed.path, 4)
            if not run_id or not node_id:
                self._send_json(400, {"message": "缺少 run_id 或 node_id"})
                return
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                payload = self._load_run_bundle(run_id=run_id, project_id=project_id)
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            selected_node = next((node for node in payload["graph"].get("nodes", []) if str(node.get("id")) == node_id), None)
            self._send_json(
                200,
                {
                    "run_id": run_id,
                    "node_id": node_id,
                    "node": selected_node or {"id": node_id},
                    "state": payload["node_states"].get(node_id, {}),
                    "events": [event for event in payload["recent_events"] if str(event.get("node_id") or "") == node_id],
                },
            )
            return
        if parsed.path.endswith("/chat-history") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            try:
                payload = self._build_project_chat_history(project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path.endswith("/context") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            try:
                context = self._build_project_context(project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, context)
            return
        if parsed.path.endswith("/context/stats") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            try:
                payload = self._build_project_context_stats(project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path.endswith("/docs") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
                docs = self._build_docs_catalog(project_id=project_id, project_path=project_path)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"docs": docs})
            return
        if parsed.path.endswith("/docs/content") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            params = parse_qs(parsed.query)
            doc_path = params.get("path", [""])[0].strip()
            if not doc_path:
                self._send_json(400, {"message": "請提供 path"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
                resolved_path = self._resolve_doc_path(project_path, doc_path)
                content = resolved_path.read_text(encoding="utf-8")
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"path": doc_path, "content": content})
            return
        if parsed.path.endswith("/docs/download") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            params = parse_qs(parsed.query)
            doc_path = params.get("path", [""])[0].strip()
            if not doc_path:
                self._send_json(400, {"message": "請提供 path"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
                resolved_path = self._resolve_doc_path(project_path, doc_path)
                content = resolved_path.read_text(encoding="utf-8")
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            body = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{Path(doc_path).name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path.endswith("/docs/raw") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            params = parse_qs(parsed.query)
            doc_path = params.get("path", [""])[0].strip()
            if not doc_path:
                self._send_json(400, {"message": "請提供 path"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
                resolved_path = self._resolve_doc_path(project_path, doc_path)
                body = resolved_path.read_bytes()
            except FileNotFoundError as exc:
                self._handle_error(exc, status=404)
                return
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            content_type, _ = mimetypes.guess_type(str(resolved_path))
            if not content_type:
                content_type = "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{resolved_path.name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/v1/tools/catalog":
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            refresh = params.get("refresh", ["false"])[0].lower() == "true"
            try:
                payload = self._build_tools_catalog(project_id=project_id, refresh_mcp=refresh)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path == "/v1/skills/catalog":
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            try:
                payload = self._build_skills_catalog(project_id=project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path == "/v1/config/view":
            params = parse_qs(parsed.query)
            project_id = params.get("project_id", [""])[0].strip() or None
            cli_overrides = self._read_query_json_object(params, "cli_overrides")
            if cli_overrides is None:
                self._send_json(400, {"message": "cli_overrides 必須是 JSON 物件"})
                return
            chat_overrides = self._read_query_json_object(params, "chat_overrides")
            if chat_overrides is None:
                self._send_json(400, {"message": "chat_overrides 必須是 JSON 物件"})
                return
            try:
                payload = self._build_config_view_payload(
                    project_id=project_id,
                    cli_overrides=cli_overrides,
                    chat_overrides=chat_overrides,
                )
            except KeyError as exc:
                self._handle_error(exc, status=404)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path == "/v1/logs/query":
            params = parse_qs(parsed.query)
            try:
                payload = self._query_logs(params)
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path == "/v1/logs/download":
            params = parse_qs(parsed.query)
            try:
                payload = self._query_logs(params, include_paging=False)
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            body = "\n".join(json.dumps(item, ensure_ascii=False) for item in payload["items"]) + "\n"
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="amon-logs.ndjson"')
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return
        if parsed.path == "/v1/events/query":
            params = parse_qs(parsed.query)
            try:
                payload = self._query_events(params)
            except ValueError as exc:
                self._send_json(400, {"message": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, payload)
            return
        if parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            try:
                record = self.core.get_project(project_id)
            except KeyError as exc:
                self._handle_error(exc, status=404)
                return
            self._send_json(200, {"project": record.to_dict()})
            return
        self._send_json(404, {"message": "找不到 API 路徑"})

    def _handle_api_post(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/v1/context/clear":
            payload = self._read_json()
            if payload is None:
                return
            scope = str(payload.get("scope") or "project").strip().lower() or "project"
            project_id = str(payload.get("project_id") or "").strip()
            if scope not in {"project", "chat"}:
                self._send_json(400, {"message": "scope 僅允許 project 或 chat"})
                return
            if not project_id:
                self._send_json(400, {"message": "請提供 project_id"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
                if scope == "project":
                    context_path = self._project_context_file(project_path)
                    if context_path.exists():
                        context_path.unlink()
                self._send_json(200, {"status": "ok", "scope": scope})
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
            return
        if parsed.path == "/v1/ui/toasts":
            payload = self._read_json()
            if payload is None:
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"message": "payload 需為物件"})
                return
            message = str(payload.get("message", "")).strip()
            if not message:
                self._send_json(400, {"message": "請提供 toast 訊息"})
                return
            toast_type = str(payload.get("type", "info")).strip() or "info"
            severity = str(payload.get("level", "INFO")).strip().upper() or "INFO"
            if severity not in {"INFO", "WARNING", "ERROR"}:
                severity = "INFO"
            duration_ms = payload.get("duration_ms", 12000)
            if not isinstance(duration_ms, (int, float)):
                duration_ms = 12000
            duration_ms = max(0, min(int(duration_ms), 120000))
            metadata = payload.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            log_event(
                {
                    "level": severity,
                    "event": "ui_toast_displayed",
                    "type": toast_type,
                    "message": message[:600],
                    "message_length": len(message),
                    "duration_ms": duration_ms,
                    "project_id": str(payload.get("project_id", "")).strip() or None,
                    "chat_id": str(payload.get("chat_id", "")).strip() or None,
                    "route": str(payload.get("route", "")).strip() or None,
                    "source": str(payload.get("source", "ui")).strip() or "ui",
                    "metadata": metadata,
                }
            )
            self._send_json(202, {"status": "ok"})
            return
        if parsed.path == "/v1/runs":
            payload = self._read_json()
            if payload is None:
                return
            project_id = str(payload.get("project_id", "")).strip()
            graph_path = str(payload.get("graph_path", "")).strip()
            variables = payload.get("variables") or {}
            if not project_id or not graph_path:
                self._send_json(400, {"message": "請提供 project_id 與 graph_path"})
                return
            if not isinstance(variables, dict):
                self._send_json(400, {"message": "variables 需為物件"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
            except KeyError as exc:
                self._handle_error(exc, status=404)
                return
            run_id = payload.get("run_id") or uuid.uuid4().hex
            request_id = _TASK_MANAGER.submit_run(
                request_id=None,
                core=self.core,
                project_path=project_path,
                graph_path=graph_path,
                variables=variables,
                run_id=run_id,
            )
            self._send_json(202, {"request_id": request_id, "run_id": run_id})
            return
        if parsed.path == "/v1/runs/cancel":
            payload = self._read_json()
            if payload is None:
                return
            project_id = str(payload.get("project_id", "")).strip()
            run_id = str(payload.get("run_id", "")).strip()
            if not project_id or not run_id:
                self._send_json(400, {"message": "請提供 project_id 與 run_id"})
                return
            try:
                project_path = self.core.get_project_path(project_id)
            except KeyError as exc:
                self._handle_error(exc, status=404)
                return
            cancel_path = project_path / ".amon" / "runs" / run_id / "cancel.json"
            cancel_path.parent.mkdir(parents=True, exist_ok=True)
            cancel_path.write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
            _TASK_MANAGER.cancel_run(run_id)
            self._send_json(200, {"status": "cancelled", "run_id": run_id})
            return
        if parsed.path == "/v1/tools/run":
            payload = self._read_json()
            if payload is None:
                return
            tool_name = str(payload.get("tool_name", "")).strip()
            project_id = str(payload.get("project_id", "")).strip() or None
            args = payload.get("args") or {}
            if not tool_name:
                self._send_json(400, {"message": "請提供 tool_name"})
                return
            if not isinstance(args, dict):
                self._send_json(400, {"message": "args 需為物件"})
                return
            request_id = _TASK_MANAGER.submit_tool(
                request_id=None,
                core=self.core,
                tool_name=tool_name,
                args=args,
                project_id=project_id,
            )
            self._send_json(202, {"request_id": request_id})
            return
        if parsed.path == "/v1/jobs/start":
            payload = self._read_json()
            if payload is None:
                return
            job_id = str(payload.get("job_id", "")).strip()
            if not job_id:
                self._send_json(400, {"message": "請提供 job_id"})
                return
            request_id = _TASK_MANAGER.submit_job(request_id=None, core=self.core, job_id=job_id)
            self._send_json(202, {"request_id": request_id, "job_id": job_id})
            return
        if parsed.path == "/v1/hooks/dispatch":
            payload = self._read_json()
            if payload is None:
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"message": "payload 需為物件"})
                return
            try:
                event_id = emit_event(payload, dispatch_hooks=True)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(202, {"event_id": event_id})
            return
        if parsed.path == "/v1/schedules/tick":
            request_id = _TASK_MANAGER.submit_schedule_tick(request_id=None, core=self.core)
            self._send_json(202, {"request_id": request_id})
            return
        if parsed.path == "/v1/chat/stream/init":
            payload = self._read_json()
            if payload is None:
                return
            message = str(payload.get("message", "")).strip()
            project_id = str(payload.get("project_id", "")).strip() or None
            chat_id = str(payload.get("chat_id", "")).strip() or None
            if not message:
                self._send_json(400, {"message": "請提供 message"})
                return
            if len(message) > 100_000:
                self._send_json(413, {"message": "message 過長"})
                return
            token = _create_chat_stream_token(message=message, project_id=project_id, chat_id=chat_id)
            self._send_json(201, {"stream_token": token, "ttl_s": _CHAT_STREAM_INIT_TTL_S})
            return
        if parsed.path == "/v1/chat/sessions":
            payload = self._read_json()
            if payload is None:
                return
            project_id = str(payload.get("project_id", "")).strip()
            if not project_id:
                self._send_json(400, {"message": "請提供 project_id"})
                return
            try:
                chat_id = create_chat_session(project_id)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(201, {"chat_id": chat_id})
            return
        if parsed.path == "/v1/chat/plan/confirm":
            payload = self._read_json()
            if payload is None:
                return
            project_id = str(payload.get("project_id", "")).strip()
            chat_id = str(payload.get("chat_id", "")).strip()
            command = str(payload.get("command", "")).strip()
            args = payload.get("args") or {}
            confirmed = bool(payload.get("confirmed", False))
            if not (project_id and chat_id and command):
                self._send_json(400, {"message": "請提供 project_id、chat_id、command"})
                return
            if not isinstance(args, dict):
                self._send_json(400, {"message": "args 需為物件"})
                return
            append_event(
                chat_id,
                {
                    "type": "plan_confirm",
                    "text": "confirmed" if confirmed else "cancelled",
                    "project_id": project_id,
                    "command": command,
                },
            )
            if not confirmed:
                self._send_json(200, {"status": "cancelled"})
                return
            plan = CommandPlan(name=command, args=args, project_id=project_id, chat_id=chat_id)
            result = execute(plan, confirmed=True)
            append_event(
                chat_id,
                {
                    "type": "command_result",
                    "text": json.dumps(result, ensure_ascii=False),
                    "project_id": project_id,
                    "command": command,
                },
            )
            self._send_json(200, {"status": "ok", "result": result})
            return
        if parsed.path == "/v1/tools/policy/plan":
            payload = self._read_json()
            if payload is None:
                return
            action = str(payload.get("action", "")).strip()
            tool_name = str(payload.get("tool_name", "")).strip()
            if action not in {"enable", "disable", "require_confirm"}:
                self._send_json(400, {"message": "action 僅允許 enable/disable/require_confirm"})
                return
            if not tool_name:
                self._send_json(400, {"message": "請提供 tool_name"})
                return
            plan = {
                "command": "tools.policy.update",
                "args": {
                    "action": action,
                    "tool_name": tool_name,
                    "require_confirm": bool(payload.get("require_confirm", False)),
                },
                "plan_card": (
                    "即將更新工具權限設定，需二次確認。\n\n"
                    f"action: {action}\n"
                    f"tool: {tool_name}\n"
                    f"require_confirm: {bool(payload.get('require_confirm', False))}"
                ),
                "risk": {"require_confirm": True, "scope": "tools_policy", "level": "medium"},
                "commands": [f"tools.policy.{action}({tool_name})"],
            }
            self._send_json(200, {"plan": plan})
            return
        if parsed.path == "/v1/tools/policy/confirm":
            payload = self._read_json()
            if payload is None:
                return
            action = str(payload.get("action", "")).strip()
            tool_name = str(payload.get("tool_name", "")).strip()
            confirmed = bool(payload.get("confirmed"))
            if action not in {"enable", "disable", "require_confirm"}:
                self._send_json(400, {"message": "action 僅允許 enable/disable/require_confirm"})
                return
            if not tool_name:
                self._send_json(400, {"message": "請提供 tool_name"})
                return
            if not confirmed:
                self._send_json(200, {"status": "cancelled"})
                return
            try:
                self._apply_tool_policy_update(
                    action=action,
                    tool_name=tool_name,
                    require_confirm=bool(payload.get("require_confirm", False)),
                )
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"status": "updated"})
            return
        if parsed.path == "/v1/skills/trigger-preview":
            payload = self._read_json()
            if payload is None:
                return
            skill_name = str(payload.get("skill_name", "")).strip()
            project_id = str(payload.get("project_id", "")).strip() or None
            if not skill_name:
                self._send_json(400, {"message": "請提供 skill_name"})
                return
            try:
                preview = self._build_skill_trigger_preview(skill_name=skill_name, project_id=project_id)
            except KeyError as exc:
                self._handle_error(exc, status=404)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, preview)
            return
        if parsed.path == "/v1/projects":
            payload = self._read_json()
            if payload is None:
                return
            name = str(payload.get("name", "")).strip()
            if not name:
                self._send_json(400, {"message": "請提供專案名稱"})
                return
            try:
                record = self.core.create_project(name)
            except FileExistsError as exc:
                self._handle_error(exc, status=409)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(201, {"project": record.to_dict()})
            return
        if parsed.path.startswith("/v1/projects/") and parsed.path.endswith("/restore"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            try:
                record = self.core.restore_project(project_id)
            except (KeyError, ValueError, FileExistsError) as exc:
                status = 404 if isinstance(exc, KeyError) else 400
                self._handle_error(exc, status=status)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"project": record.to_dict()})
            return
        self._send_json(404, {"message": "找不到 API 路徑"})

    def _handle_api_put(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.endswith("/context") and parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            payload = self._read_json()
            if payload is None:
                return
            context_text = str(payload.get("context") or "")
            try:
                project_path = self.core.get_project_path(project_id)
                self._write_project_context(project_path, context_text)
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"project_id": project_id, "context": context_text})
            return
        self._send_json(404, {"message": "找不到 API 路徑"})

    def _handle_api_patch(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            payload = self._read_json()
            if payload is None:
                return
            name = str(payload.get("name", "")).strip()
            if not name:
                self._send_json(400, {"message": "請提供新的專案名稱"})
                return
            try:
                record = self.core.update_project_name(project_id, name)
            except KeyError as exc:
                self._handle_error(exc, status=404)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"project": record.to_dict()})
            return
        self._send_json(404, {"message": "找不到 API 路徑"})

    def _handle_api_delete(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/v1/projects/"):
            project_id = self._get_path_segment(parsed.path, 2)
            if not project_id:
                self._send_json(400, {"message": "無效的 project_id"})
                return
            try:
                record = self.core.delete_project(project_id)
            except (KeyError, ValueError) as exc:
                status = 404 if isinstance(exc, KeyError) else 400
                self._handle_error(exc, status=status)
                return
            except Exception as exc:  # noqa: BLE001
                self._handle_error(exc, status=500)
                return
            self._send_json(200, {"project": record.to_dict()})
            return
        self._send_json(404, {"message": "找不到 API 路徑"})

    def _build_tools_catalog(self, project_id: str | None, *, refresh_mcp: bool = False) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id) if project_id else None
        config = self.core.load_config(project_path)
        mcp_registry = self.core.get_mcp_registry(refresh=refresh_mcp)
        recent_usage = self._read_recent_tool_usage()
        server_map = {server.name: server for server in self.core._load_mcp_servers(config)}
        tool_registry = self._resolve_tool_registry(project_path)

        tools: list[dict[str, Any]] = []
        for server_name, server_info in (mcp_registry.get("servers") or {}).items():
            for tool in server_info.get("tools") or []:
                tool_name = str(tool.get("name") or "").strip()
                if not tool_name:
                    continue
                full_name = f"{server_name}:{tool_name}"
                tool_risk = "high" if self.core._is_high_risk_tool(tool_name) else "medium"
                decision = "deny" if tool_risk == "high" else "ask"
                reason = (
                    "高風險工具（可能寫入檔案、刪除資料或觸及機敏資訊）預設拒絕"
                    if decision == "deny"
                    else "中風險工具需人工確認後才可執行"
                )
                tools.append(
                    {
                        "type": "mcp",
                        "name": full_name,
                        "version": tool.get("version") or "unknown",
                        "input_schema": tool.get("inputSchema") or tool.get("input_schema") or {},
                        "output_schema": tool.get("outputSchema") or tool.get("output_schema") or {},
                        "risk": tool_risk,
                        "allowed_paths": config.get("tools", {}).get("allowed_paths", ["workspace"]),
                        "enabled": self.core._is_tool_allowed(full_name, config, server_map[server_name]) if server_name in server_map else True,
                        "require_confirm": decision == "ask",
                        "policy_decision": decision,
                        "policy_reason": reason,
                        "recent_usage": recent_usage.get(full_name),
                    }
                )

        for spec in tool_registry.list_specs():
            source = "forged" if spec.name.startswith("native:") else "built-in"
            decision, reason = tool_registry.policy.explain(
                ToolCall(tool=spec.name, args={}, caller="ui")
            )
            tools.append(
                {
                    "type": source,
                    "name": spec.name,
                    "version": str((spec.annotations or {}).get("version") or "builtin"),
                    "input_schema": spec.input_schema,
                    "output_schema": spec.output_schema or {},
                    "risk": spec.risk,
                    "allowed_paths": config.get("tools", {}).get("allowed_paths", ["workspace"]),
                    "enabled": self._is_internal_tool_enabled(spec.name, config),
                    "require_confirm": decision == "ask",
                    "policy_decision": decision,
                    "policy_reason": reason,
                    "recent_usage": recent_usage.get(spec.name),
                }
            )

        tools.sort(key=lambda item: (item.get("type", ""), item.get("name", "")))
        return {"tools": tools, "updated_at": self.core._now(), "policy_editable": True}

    def _resolve_tool_registry(self, project_path: Path | None) -> Any:
        registry = getattr(self.core, "tool_registry", None)
        if registry is not None:
            return registry
        from amon.tooling.builtin import build_registry

        workspace_root = project_path or Path.cwd()
        return build_registry(workspace_root)

    def _build_skills_catalog(self, project_id: str | None) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id) if project_id else None
        scanned = self.core.scan_skills(project_path=project_path)
        collisions: list[dict[str, Any]] = []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for skill in scanned:
            grouped.setdefault(str(skill.get("name") or ""), []).append(skill)
        for name, items in grouped.items():
            sources = {item.get("source") for item in items}
            if "global" in sources and "project" in sources:
                collisions.append({"name": name, "message": "project override global"})
        return {"skills": scanned, "collisions": collisions, "updated_at": self.core._now()}


    def _build_config_view_payload(
        self,
        *,
        project_id: str | None,
        cli_overrides: dict[str, Any],
        chat_overrides: dict[str, Any],
    ) -> dict[str, Any]:
        loader = ConfigLoader(data_dir=self.core.data_dir)
        global_config = loader.load_global()
        project_config: dict[str, Any] = {}
        if project_id:
            self.core.get_project_path(project_id)
            project_config = loader.load_project(project_id)
        resolution = loader.resolve(project_id=project_id, cli_overrides=cli_overrides or None)
        effective = resolution.effective
        sources = resolution.sources
        if chat_overrides:
            self._overlay_with_source(effective, sources, chat_overrides, "chat")
        return {
            "project_id": project_id,
            "global_config": global_config,
            "project_config": project_config,
            "effective_config": effective,
            "sources": sources,
        }

    @staticmethod
    def _overlay_with_source(base: dict[str, Any], sources: dict[str, Any], updates: dict[str, Any], source: str) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict) and isinstance(sources.get(key), dict):
                AmonUIHandler._overlay_with_source(base[key], sources[key], value, source)
                continue
            base[key] = value
            sources[key] = AmonUIHandler._assign_source_tree(value, source)

    @staticmethod
    def _assign_source_tree(value: Any, source: str) -> Any:
        if isinstance(value, dict):
            return {key: AmonUIHandler._assign_source_tree(item, source) for key, item in value.items()}
        return source

    @staticmethod
    def _read_query_json_object(params: dict[str, list[str]], key: str) -> dict[str, Any] | None:
        raw = params.get(key, [""])[0].strip()
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict):
            return None
        return value
    def _build_skill_trigger_preview(self, *, skill_name: str, project_id: str | None) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id) if project_id else None
        skill = self.core.load_skill(skill_name, project_path=project_path)
        preview = build_skill_injection_preview([skill])
        return {
            "skill": {
                "name": skill.get("name"),
                "source": skill.get("source"),
                "path": skill.get("path"),
                "frontmatter": skill.get("frontmatter") or {},
            },
            "injection_preview": preview,
            "note": "此 API 僅回傳可重現的注入預覽，不會觸發模型呼叫。",
        }

    def _apply_tool_policy_update(self, *, action: str, tool_name: str, require_confirm: bool) -> None:
        config_path = self.core._global_config_path()
        config = self.core.load_config()
        if ":" in tool_name:
            mcp = config.setdefault("mcp", {})
            allowed = mcp.setdefault("allowed_tools", [])
            if action == "enable" and tool_name not in allowed:
                allowed.append(tool_name)
            if action == "disable" and tool_name in allowed:
                allowed.remove(tool_name)
        else:
            tooling = config.setdefault("tooling", {})
            disabled = tooling.setdefault("disabled_tools", [])
            ask = tooling.setdefault("ask_tools", [])
            if action == "enable" and tool_name in disabled:
                disabled.remove(tool_name)
            if action == "disable" and tool_name not in disabled:
                disabled.append(tool_name)
            if action == "require_confirm":
                if require_confirm and tool_name not in ask:
                    ask.append(tool_name)
                if (not require_confirm) and tool_name in ask:
                    ask.remove(tool_name)
        self.core._atomic_write_text(config_path, yaml.safe_dump(config, allow_unicode=True, sort_keys=False))

    def _is_internal_tool_enabled(self, tool_name: str, config: dict[str, Any]) -> bool:
        disabled = config.get("tooling", {}).get("disabled_tools", []) or []
        return tool_name not in disabled

    def _read_recent_tool_usage(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        log_path = default_audit_log_path()
        if not log_path.exists():
            return latest
        try:
            with log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        item = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    name = str(item.get("tool") or "").strip()
                    ts_ms = int(item.get("ts_ms") or 0)
                    if not name:
                        continue
                    prev = latest.get(name)
                    if prev and prev.get("ts_ms", 0) >= ts_ms:
                        continue
                    latest[name] = {
                        "ts_ms": ts_ms,
                        "decision": item.get("decision"),
                        "source": item.get("source"),
                    }
        except OSError:
            return latest
        return latest

    def _read_json(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > self._MAX_BODY_BYTES:
            self._send_json(413, {"message": "請求內容過大"})
            return None
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _get_path_segment(self, path: str, index: int) -> str | None:
        parts = [part for part in path.split("/") if part]
        if len(parts) <= index:
            return None
        return unquote(parts[index])

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_error(self, exc: Exception, status: int = 500) -> None:
        _HEALTH_METRICS.record_error()
        log_event(
            {
                "level": "ERROR",
                "event": "ui_api_error",
                "message": str(exc),
                "stack": traceback.format_exc(),
            }
        )
        self._send_json(status, {"message": str(exc)})

    def _handle_chat_stream(self, parsed) -> None:
        params = parse_qs(parsed.query)
        project_id = params.get("project_id", [""])[0].strip() or None
        chat_id = params.get("chat_id", [""])[0].strip()
        message = params.get("message", [""])[0].strip()
        stream_token = params.get("stream_token", [""])[0].strip()
        last_event_id_raw = params.get("last_event_id", [""])[0].strip()
        request_id = uuid.uuid4().hex

        if not message and stream_token:
            token_payload = _consume_chat_stream_token(stream_token)
            if token_payload:
                message = str(token_payload.get("message", "")).strip()
                project_id = project_id or str(token_payload.get("project_id", "")).strip() or None
                chat_id = chat_id or str(token_payload.get("chat_id", "")).strip()

        if not message:
            self.send_error(400, "缺少 message")
            return
        if project_id is None:
            chat_id = ""

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        event_seq = 0
        if last_event_id_raw:
            try:
                event_seq = int(last_event_id_raw)
            except ValueError:
                event_seq = 0

        def send_event(event: str, data: dict[str, Any] | str) -> None:
            nonlocal event_seq
            event_seq += 1
            payload_obj = {"text": data} if isinstance(data, str) else dict(data)
            payload_obj = ensure_correlation_fields(
                payload_obj,
                project_id=project_id,
                request_id=request_id,
            )
            payload = json.dumps(payload_obj, ensure_ascii=False)
            self.wfile.write(f"id: {event_seq}\n".encode("utf-8"))
            self.wfile.write(f"event: {event}\n".encode("utf-8"))
            for line in payload.splitlines() or [""]:
                self.wfile.write(f"data: {line}\n".encode("utf-8"))
            self.wfile.write(b"\n")
            self.wfile.flush()

        try:
            log_event(
                {
                    "level": "INFO",
                    "event": "ui_chat_stream_received",
                    "project_id": project_id,
                    "chat_id": chat_id or None,
                }
            )
            send_event("notice", {"text": "Amon：已收到你的需求，正在判斷意圖與專案。"})
            if project_id is None:
                inferred_project_id = resolve_project_id_from_message(self.core, message)
                if inferred_project_id:
                    project_id = inferred_project_id
            created_project: ProjectRecord | None = None
            if project_id is None:
                bootstrap_router = route_intent(
                    message,
                    project_id=project_id,
                    run_id=None,
                    context=None,
                )
                created_project = bootstrap_project_if_needed(
                    core=self.core,
                    project_id=project_id,
                    message=message,
                    router_type=bootstrap_router.type,
                    build_plan_from_message=_build_plan_from_message,
                    is_slash_command=message.startswith("/"),
                )
                if created_project:
                    project_id = created_project.project_id
                    log_event(
                        {
                            "level": "INFO",
                            "event": "ui_chat_stream_project_bootstrapped",
                            "project_id": normalize_project_id(project_id),
                        }
                    )
                    send_event(
                        "notice",
                        {
                            "text": f"Amon：已自動建立新專案「{created_project.name}」（{created_project.project_id}），並繼續執行你的需求。",
                            "project_id": project_id,
                        },
                    )
                else:
                    log_event(
                        {
                            "level": "WARNING",
                            "event": "ui_chat_stream_project_required",
                            "project_id": project_id,
                        }
                    )
                    send_event(
                        "notice",
                        {"text": "Amon：目前尚未指定專案，且無法自動判斷任務範圍。請補充任務目標，或先建立專案。"},
                    )
                    send_event("error", {"message": "缺少 project_id"})
                    send_event("done", {"status": "project_required"})
                    return
            turn_bundle = assemble_chat_turn(project_id=project_id, chat_id=chat_id, message=message)
            chat_id = turn_bundle.chat_id
            history = turn_bundle.history
            run_context = turn_bundle.run_context
            router_result = route_intent(
                message,
                project_id=project_id,
                run_id=str(run_context.get("run_id") or "") or None,
                context=turn_bundle.router_context,
            )
            if turn_bundle.short_continuation and router_result.type != "chat_response":
                log_event(
                    {
                        "level": "INFO",
                        "event": "ui_chat_force_continuation",
                        "project_id": project_id,
                        "chat_id": chat_id,
                        "original_router_type": router_result.type,
                    }
                )
                router_result = RouterResult(type="chat_response", confidence=1.0, reason="short_continuation")
            append_event(chat_id, {"type": "user", "text": message, "project_id": project_id})
            append_event(
                chat_id,
                {
                    "type": "router",
                    "text": router_result.type,
                    "project_id": project_id,
                },
            )
            if router_result.type in {"command_plan", "graph_patch_plan"}:
                command_name, args = _resolve_command_plan_from_router(message, router_result)
                active_project = self.core.get_project(project_id) if project_id else None
                if _is_duplicate_project_create(active_project=active_project, command_name=command_name, args=args):
                    append_event(
                        chat_id,
                        {
                            "type": "notice",
                            "text": "skip_duplicate_projects_create",
                            "project_id": project_id,
                        },
                    )
                    send_event(
                        "notice",
                        {
                            "text": f"Amon：目前已在專案「{active_project.name}」，略過重複建立專案。",
                            "project_id": active_project.project_id,
                        },
                    )
                    send_event(
                        "done",
                        {
                            "status": "ok",
                            "project_id": active_project.project_id,
                            "chat_id": chat_id,
                        },
                    )
                    return
                plan = CommandPlan(
                    name=command_name,
                    args=args,
                    project_id=project_id,
                    chat_id=chat_id,
                    metadata={"plan_type": router_result.type},
                )
                append_event(
                    chat_id,
                    {
                        "type": "plan_created",
                        "text": command_name,
                        "project_id": project_id,
                    },
                )
                result = execute(plan, confirmed=False)
                append_event(
                    chat_id,
                    {
                        "type": "command_result",
                        "text": json.dumps(result, ensure_ascii=False),
                        "project_id": project_id,
                        "command": command_name,
                    },
                )
                if result.get("status") == "confirm_required":
                    plan_card = result.get("plan_card") or ""
                    append_event(
                        chat_id,
                        {
                            "type": "plan_card",
                            "text": plan_card,
                            "project_id": project_id,
                            "command": command_name,
                        },
                    )
                    send_event(
                        "plan",
                        {
                            "plan_card": plan_card,
                            "command": command_name,
                            "args": args,
                            "project_id": project_id,
                            "chat_id": chat_id,
                        },
                    )
                    send_event(
                        "done",
                        {"status": "confirm_required", "chat_id": chat_id, "project_id": project_id},
                    )
                    return
                send_event("result", result)
                send_event("done", {"status": "ok", "chat_id": chat_id, "project_id": project_id})
                return
            if router_result.type == "chat_response":
                send_event("notice", {"text": "Amon：正在分析需求並進入執行流程。"})
                execution_mode = decide_execution_mode(message, project_id=project_id, context=turn_bundle.router_context)
                prompt_with_history = turn_bundle.prompt_with_history

                streamed_token_count = 0

                def stream_handler(token: str) -> None:
                    nonlocal streamed_token_count
                    is_reasoning, reasoning_text = decode_reasoning_chunk(token)
                    if is_reasoning:
                        send_event("reasoning", {"text": reasoning_text})
                        append_event(
                            chat_id,
                            {"type": "assistant_reasoning", "text": reasoning_text, "project_id": project_id},
                        )
                        return
                    streamed_token_count += 1
                    send_event("token", {"text": token})
                    append_event(
                        chat_id,
                        {"type": "assistant_chunk", "text": token, "project_id": project_id},
                    )

                run_id = ""
                if execution_mode == "single":
                    continued_run_id = None
                    if _should_continue_chat_run(project_id=project_id, last_assistant_text=run_context.get("last_assistant_text"), user_message=message):
                        continued_run_id = str(run_context.get("run_id") or "").strip() or None
                    result, response_text = self.core.run_single_stream(
                        prompt_with_history,
                        project_path=self.core.get_project_path(project_id),
                        stream_handler=stream_handler,
                        run_id=continued_run_id,
                        conversation_history=history,
                    )
                    run_id = result.run_id
                elif execution_mode == "self_critique":
                    send_event("notice", {"text": "Amon：偵測為專業文件撰寫，改用 self_critique 流程。"})
                    response_text = self.core.run_self_critique(
                        prompt_with_history,
                        project_path=self.core.get_project_path(project_id),
                        stream_handler=stream_handler,
                    )
                elif execution_mode == "team":
                    send_event("notice", {"text": "Amon：這題我會改用 team 流程分工處理，完成後用自然語氣一次整理回覆給你。"})
                    response_text = self.core.run_team(
                        prompt_with_history,
                        project_path=self.core.get_project_path(project_id),
                        stream_handler=None,
                    )
                else:
                    send_event("notice", {"text": "Amon：已路由到 plan_execute，將先產生計畫並編譯執行圖。"})
                    response_text = self.core.run_plan_execute(
                        prompt_with_history,
                        project_path=self.core.get_project_path(project_id),
                        project_id=project_id,
                        stream_handler=stream_handler,
                    )
                assistant_payload: dict[str, Any] = {"type": "assistant", "text": response_text, "project_id": project_id}
                if run_id:
                    assistant_payload["run_id"] = run_id
                append_event(chat_id, assistant_payload)
                done_payload: dict[str, Any] = {
                    "status": "ok",
                    "chat_id": chat_id,
                    "project_id": project_id,
                    "run_id": run_id,
                    "execution_mode": execution_mode,
                }
                if streamed_token_count == 0 and response_text:
                    done_payload["final_text"] = response_text
                send_event(
                    "done",
                    done_payload,
                )
                return
            send_event(
                "notice",
                {
                    "text": "Amon：已收到你的訊息，但目前無法判斷可執行的意圖。請改用更明確的任務描述，我會立即繼續處理。",
                    "chat_id": chat_id,
                    "project_id": project_id,
                },
            )
            send_event("done", {"status": "unsupported", "chat_id": chat_id, "project_id": project_id})
        except Exception as exc:  # noqa: BLE001
            log_event(
                {
                    "level": "ERROR",
                    "event": "ui_chat_stream_error",
                    "message": str(exc),
                    "stack": traceback.format_exc(),
                }
            )
            if chat_id and project_id:
                append_event(chat_id, {"type": "error", "text": str(exc), "project_id": project_id})
            send_event("error", {"message": str(exc)})
            send_event("done", {"status": "failed", "chat_id": chat_id})

    def _list_projects_for_ui(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        records = self.core.list_projects(include_deleted=include_deleted)
        merged: dict[str, dict[str, Any]] = {record.project_id: record.to_dict() for record in records}

        projects_dir = self.core.projects_dir
        if projects_dir.exists():
            for child in projects_dir.iterdir():
                if not child.is_dir():
                    continue
                project_id = child.name.strip()
                if not project_id or project_id in merged:
                    continue
                merged[project_id] = {
                    "project_id": project_id,
                    "name": project_id,
                    "path": str(child),
                    "created_at": "",
                    "updated_at": "",
                    "status": "active",
                }

        projects = list(merged.values())
        projects.sort(key=lambda item: item.get("project_id") or "")
        return projects

    def _build_project_chat_history(self, project_id: str) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id)
        sessions_dir = project_path / "sessions" / "chat"
        if not sessions_dir.exists():
            return {"project_id": project_id, "chat_id": None, "messages": []}

        session_files = [path for path in sessions_dir.glob("*.jsonl") if path.is_file()]
        if not session_files:
            return {"project_id": project_id, "chat_id": None, "messages": []}

        def _read_session_messages(path: Path) -> list[dict[str, Any]]:
            parsed_messages: list[dict[str, Any]] = []
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = str(payload.get("type") or "").strip()
                text = payload.get("text")
                if event_type not in {"user", "assistant"} or not isinstance(text, str) or not text.strip():
                    continue
                parsed_messages.append(
                    {
                        "role": "user" if event_type == "user" else "assistant",
                        "text": text.strip(),
                        "ts": str(payload.get("ts") or "").strip(),
                    }
                )
            return parsed_messages

        selected_session = max(session_files, key=lambda path: path.stat().st_mtime)
        selected_messages = _read_session_messages(selected_session)

        if not selected_messages:
            for session_file in sorted(session_files, key=lambda path: path.stat().st_mtime, reverse=True):
                fallback_messages = _read_session_messages(session_file)
                if fallback_messages:
                    selected_session = session_file
                    selected_messages = fallback_messages
                    break

        return {"project_id": project_id, "chat_id": selected_session.stem, "messages": selected_messages[-60:]}

    def _build_project_context(self, project_id: str) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id)
        run_bundle = self._load_latest_run_bundle(project_path)
        graph = run_bundle["graph"]
        docs = self._build_docs_catalog(project_id=project_id, project_path=project_path)
        project_context_text = self._read_project_context(project_path)
        return {
            "graph_mermaid": self._graph_to_mermaid(graph),
            "graph": graph,
            "run_id": run_bundle["run_id"],
            "run_status": run_bundle["run_status"],
            "node_states": run_bundle["node_states"],
            "recent_events": run_bundle["recent_events"],
            "docs": docs,
            "context": project_context_text,
        }


    def _build_project_context_stats(self, project_id: str) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id)
        chat_history = self._build_project_chat_history(project_id)
        tools_catalog = self._build_tools_catalog(project_id=project_id, refresh_mcp=False)
        skills_catalog = self._build_skills_catalog(project_id=project_id)
        config_payload = self._build_config_view_payload(project_id=project_id, cli_overrides={}, chat_overrides={})
        latest_run = self._load_latest_run_bundle(project_path)
        recent_events = latest_run.get("recent_events") or []

        effective_config = config_payload.get("effective_config") or {}
        project_context_text = self._read_project_context(project_path)
        system_prompt = (
            (effective_config.get("agent") or {}).get("system_prompt")
            or (effective_config.get("prompts") or {}).get("system")
            or (effective_config.get("chat") or {}).get("system_prompt")
            or ""
        )
        chat_messages = chat_history.get("messages") or []
        tool_defs = tools_catalog.get("tools") or []
        skills = skills_catalog.get("skills") or []

        non_dialogue_counts = {
            "project_context": count_non_dialogue_tokens(project_context_text, effective_config=effective_config),
            "system_prompt": count_non_dialogue_tokens(system_prompt, effective_config=effective_config),
            "tools_definition": count_non_dialogue_tokens(tool_defs, effective_config=effective_config),
            "skills": count_non_dialogue_tokens(skills, effective_config=effective_config),
        }

        tool_use_events = [
            event
            for event in recent_events
            if str(event.get("type") or event.get("event") or "").lower()
            in {"tool.call", "tool_complete", "tool_error", "mcp_tool_call", "web_search"}
        ]
        web_search_events = [
            event
            for event in recent_events
            if "web" in str(event.get("tool") or event.get("name") or event.get("event") or "").lower()
            and "search" in str(event.get("tool") or event.get("name") or event.get("event") or "").lower()
        ]

        dialogue_usage = extract_dialogue_input_tokens(recent_events)

        categories = [
            {
                "key": "project_context",
                "label": "Project Context",
                "tokens": int(non_dialogue_counts["project_context"].tokens or 0),
                "items": 1 if project_context_text else 0,
                "note": "專案 Context 草稿",
            },
            {
                "key": "system_prompt",
                "label": "System Prompt",
                "tokens": int(non_dialogue_counts["system_prompt"].tokens or 0),
                "items": 1 if system_prompt else 0,
                "note": "模型系統指令",
            },
            {
                "key": "tools_definition",
                "label": "Tools Definition",
                "tokens": int(non_dialogue_counts["tools_definition"].tokens or 0),
                "items": len(tool_defs),
                "note": "工具清單與 schema",
            },
            {
                "key": "skills",
                "label": "Skills",
                "tokens": int(non_dialogue_counts["skills"].tokens or 0),
                "items": len(skills),
                "note": "可觸發技能與前言",
            },
            {
                "key": "tool_use",
                "label": "Tool Use (Web Search…)",
                "tokens": 0,
                "items": len(tool_use_events),
                "extra": {"web_search_hits": len(web_search_events)},
                "note": "最近 run 的工具呼叫與搜尋痕跡（tokens 併入 API 對話統計）",
            },
            {
                "key": "chat_history",
                "label": "Chat History",
                "tokens": int(dialogue_usage.tokens or 0),
                "items": len(chat_messages),
                "note": "最近對話訊息",
            },
        ]

        total_used = sum(int(item.get("tokens") or 0) for item in categories)
        provider_name = str((effective_config.get("amon") or {}).get("provider") or "")
        provider_cfg = (effective_config.get("providers") or {}).get(provider_name) if provider_name else {}
        capacity = int((provider_cfg or {}).get("context_window") or (provider_cfg or {}).get("max_input_tokens") or 12000)
        remaining = max(capacity - total_used, 0)
        usage_ratio = (total_used / capacity) if capacity > 0 else 0.0

        return {
            "project_id": project_id,
            "chat_id": chat_history.get("chat_id"),
            "run_id": latest_run.get("run_id"),
            "token_estimate": {
                "used": total_used,
                "capacity": capacity,
                "remaining": remaining,
                "usage_ratio": usage_ratio,
                "estimated_cost_usd": round(total_used * 0.0000025, 6),
                "unit": "estimated_tokens",
            },
            "categories": categories,
            "meta": {
                "has_system_prompt": bool(system_prompt),
                "has_project_context": bool(project_context_text),
                "dialogue_token_source": dialogue_usage.method,
                "non_dialogue_tokenizer": {
                    key: value.method for key, value in non_dialogue_counts.items()
                },
                "tool_count": len(tool_defs),
                "skill_count": len(skills),
                "chat_message_count": len(chat_messages),
                "recent_event_count": len(recent_events),
            },
        }

    @staticmethod
    def _project_context_file(project_path: Path) -> Path:
        return project_path / ".amon" / "context" / "project_context.md"

    def _read_project_context(self, project_path: Path) -> str:
        context_path = self._project_context_file(project_path)
        if not context_path.exists():
            return ""
        try:
            return context_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.logger.warning("讀取 project context 失敗：%s", exc)
            return ""

    def _write_project_context(self, project_path: Path, context_text: str) -> None:
        context_path = self._project_context_file(project_path)
        context_path.parent.mkdir(parents=True, exist_ok=True)
        safe_text = str(context_text or "")
        context_path.write_text(safe_text, encoding="utf-8")

    def _load_latest_run_bundle(self, project_path: Path) -> dict[str, Any]:
        fallback_graph = self._load_latest_graph(project_path)
        runs_dir = project_path / ".amon" / "runs"
        if not runs_dir.exists():
            return {
                "run_id": None,
                "run_status": "not_found",
                "graph": fallback_graph,
                "node_states": {},
                "recent_events": [],
            }

        run_dirs = [path for path in runs_dir.iterdir() if path.is_dir()]
        if not run_dirs:
            return {
                "run_id": None,
                "run_status": "not_found",
                "graph": fallback_graph,
                "node_states": {},
                "recent_events": [],
            }

        latest = max(run_dirs, key=lambda path: path.stat().st_mtime)
        run_id = latest.name

        graph = fallback_graph
        resolved_path = latest / "graph.resolved.json"
        if resolved_path.exists():
            try:
                graph = json.loads(resolved_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                graph = fallback_graph

        state_payload: dict[str, Any] = {}
        state_path = latest / "state.json"
        if state_path.exists():
            try:
                state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state_payload = {}

        events: list[dict[str, Any]] = []
        events_path = latest / "events.jsonl"
        if events_path.exists():
            try:
                for line in events_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        events.append(payload)
            except OSError:
                events = []

        return {
            "run_id": run_id,
            "run_status": state_payload.get("status", "unknown"),
            "graph": graph,
            "node_states": state_payload.get("nodes", {}),
            "recent_events": events[-100:],
        }

    def _load_run_bundle(self, run_id: str, project_id: str | None = None) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id) if project_id else self._resolve_project_path_from_run_id(run_id)
        run_dir = project_path / ".amon" / "runs" / run_id
        if not run_dir.exists():
            raise FileNotFoundError("找不到 run")

        fallback_graph = self._load_latest_graph(project_path)
        graph = fallback_graph
        resolved_path = run_dir / "graph.resolved.json"
        if resolved_path.exists():
            try:
                graph = json.loads(resolved_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                graph = fallback_graph

        state_payload: dict[str, Any] = {}
        state_path = run_dir / "state.json"
        if state_path.exists():
            try:
                state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state_payload = {}

        events: list[dict[str, Any]] = []
        events_path = run_dir / "events.jsonl"
        if events_path.exists():
            try:
                for raw in events_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        events.append(payload)
            except OSError:
                events = []

        return {
            "run_id": run_id,
            "run_status": state_payload.get("status", "unknown"),
            "graph": graph,
            "node_states": state_payload.get("nodes", {}),
            "recent_events": events[-100:],
        }

    def _list_runs_for_ui(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            project_ids = [project_id]
        else:
            project_ids = [record.project_id for record in self.core.list_projects()]

        runs: list[dict[str, Any]] = []
        for pid in project_ids:
            project_path = self.core.get_project_path(pid)
            runs_dir = project_path / ".amon" / "runs"
            if not runs_dir.exists():
                continue
            for run_dir in runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                run_id = run_dir.name
                state_payload: dict[str, Any] = {}
                state_path = run_dir / "state.json"
                if state_path.exists():
                    try:
                        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        state_payload = {}
                runs.append(
                    {
                        "id": run_id,
                        "run_id": run_id,
                        "project_id": pid,
                        "status": state_payload.get("status", "unknown"),
                        "created_at": datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc).isoformat(),
                        "updated_at": datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc).isoformat(),
                    }
                )

        runs.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return runs

    def _query_logs(self, params: dict[str, list[str]], *, include_paging: bool = True) -> dict[str, Any]:
        source = params.get("source", ["amon"])[0].strip().lower()
        if source not in {"amon", "project", "billing"}:
            raise ValueError("source 僅支援 amon/project/billing")
        project_id = params.get("project_id", [""])[0].strip() or None
        run_id = params.get("run_id", [""])[0].strip() or None
        node_id = params.get("node_id", [""])[0].strip() or None
        severity = params.get("severity", [""])[0].strip().upper() or None
        component = params.get("component", [""])[0].strip().lower() or None
        time_from = self._parse_time(params.get("time_from", [""])[0].strip())
        time_to = self._parse_time(params.get("time_to", [""])[0].strip())
        page = max(int(params.get("page", ["1"])[0] or "1"), 1)
        page_size = min(max(int(params.get("page_size", ["50"])[0] or "50"), 1), 200)

        items = self._read_logs_source(source, project_id=project_id)
        filtered = []
        for item in items:
            if project_id and str(item.get("project_id") or "") != project_id:
                continue
            if run_id and str(item.get("run_id") or "") != run_id:
                continue
            if node_id and str(item.get("node_id") or "") != node_id:
                continue
            if severity and str(item.get("level") or "").upper() != severity:
                continue
            if component and component not in str(item.get("component") or item.get("event") or "").lower():
                continue
            ts = self._parse_time(str(item.get("ts") or ""))
            if time_from and ts and ts < time_from:
                continue
            if time_to and ts and ts > time_to:
                continue
            filtered.append(item)
        filtered.sort(key=lambda payload: str(payload.get("ts") or ""), reverse=True)

        if not include_paging:
            return {"items": filtered, "total": len(filtered), "page": 1, "page_size": len(filtered), "has_next": False}
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": filtered[start:end],
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
            "has_next": end < len(filtered),
        }

    def _query_events(self, params: dict[str, list[str]]) -> dict[str, Any]:
        project_id = params.get("project_id", [""])[0].strip() or None
        run_id = params.get("run_id", [""])[0].strip() or None
        node_id = params.get("node_id", [""])[0].strip() or None
        event_type = params.get("type", [""])[0].strip().lower() or None
        time_from = self._parse_time(params.get("time_from", [""])[0].strip())
        time_to = self._parse_time(params.get("time_to", [""])[0].strip())
        page = max(int(params.get("page", ["1"])[0] or "1"), 1)
        page_size = min(max(int(params.get("page_size", ["50"])[0] or "50"), 1), 200)

        entries = self._read_project_run_events(project_id=project_id)
        filtered = []
        for item in entries:
            if project_id and str(item.get("project_id") or "") != project_id:
                continue
            if run_id and str(item.get("run_id") or "") != run_id:
                continue
            if node_id and str(item.get("node_id") or "") != node_id:
                continue
            if event_type and event_type not in str(item.get("event") or item.get("type") or "").lower():
                continue
            ts = self._parse_time(str(item.get("ts") or ""))
            if time_from and ts and ts < time_from:
                continue
            if time_to and ts and ts > time_to:
                continue
            item["drilldown"] = {
                "run_id": item.get("run_id"),
                "node_id": item.get("node_id"),
                "hook_id": item.get("hook_id"),
                "schedule_id": item.get("schedule_id"),
                "job_id": item.get("job_id"),
            }
            filtered.append(item)
        filtered.sort(key=lambda payload: str(payload.get("ts") or ""), reverse=True)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": filtered[start:end],
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
            "has_next": end < len(filtered),
        }

    def _read_logs_source(self, source: str, *, project_id: str | None) -> list[dict[str, Any]]:
        if source == "amon":
            return self._read_jsonl_records(self.core.data_dir / "logs" / "amon.log")
        if source == "billing":
            return self._read_jsonl_records(self.core.data_dir / "logs" / "billing.log")
        return self._read_project_run_events(project_id=project_id)

    def _read_project_run_events(self, *, project_id: str | None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        projects = [self.core.get_project(project_id)] if project_id else self.core.list_projects(include_deleted=False)
        for project in projects:
            project_path = Path(project.path)
            runs_dir = project_path / ".amon" / "runs"
            if not runs_dir.exists():
                continue
            run_dirs = [path for path in runs_dir.iterdir() if path.is_dir()]
            for run_dir in run_dirs:
                for payload in self._read_jsonl_records(run_dir / "events.jsonl"):
                    payload.setdefault("project_id", project.project_id)
                    payload.setdefault("run_id", run_dir.name)
                    payload.setdefault("source", "project")
                    if "type" in payload and "event" not in payload:
                        payload["event"] = payload.get("type")
                    records.append(payload)
        return records

    def _billing_amount(self, record: dict[str, Any]) -> float:
        amount = record.get("cost", record.get("amount", record.get("usage", record.get("token", 0))))
        try:
            parsed = float(amount)
        except (TypeError, ValueError):
            return 0.0
        if parsed < 0:
            return 0.0
        return parsed

    def _billing_bucket(self, record: dict[str, Any]) -> str:
        mode_value = str(record.get("mode") or record.get("interaction") or record.get("channel") or "").lower()
        if mode_value in {"automation", "auto", "daemon", "scheduled", "batch"}:
            return "automation"
        return "interactive"

    @staticmethod
    def _extract_date(text: str | None) -> date | None:
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    def _safe_budget_value(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0:
            return None
        return parsed

    def _build_billing_summary(self, *, project_id: str | None) -> dict[str, Any]:
        records = self._read_jsonl_records(self.core.data_dir / "logs" / "billing.log")
        today = datetime.now().date()
        summary: dict[str, Any] = {
            "currency": "USD",
            "today": {"cost": 0.0, "usage": 0.0, "records": 0},
            "project_total": {"cost": 0.0, "usage": 0.0, "records": 0},
            "breakdown": {"provider": {}, "model": {}, "agent": {}, "node": {}},
            "mode_breakdown": {
                "automation": {"cost": 0.0, "usage": 0.0, "records": 0},
                "interactive": {"cost": 0.0, "usage": 0.0, "records": 0},
            },
            "budgets": {
                "daily_budget": None,
                "per_project_budget": None,
                "automation_budget": None,
                "daily_usage": 0.0,
                "project_usage": 0.0,
                "automation_usage": 0.0,
            },
            "exceeded_events": [],
            "current_run": {"run_id": None, "cost": 0.0, "usage": 0.0, "records": 0},
            "run_trend": [],
        }

        config = self.core.load_config(self.core.get_project_path(project_id)) if project_id else self.core.load_config(None)
        billing_cfg = config.get("billing", {}) if isinstance(config, dict) else {}
        summary["currency"] = str(billing_cfg.get("currency") or "USD")
        summary["budgets"]["daily_budget"] = self._safe_budget_value(billing_cfg.get("daily_budget"))
        summary["budgets"]["per_project_budget"] = self._safe_budget_value(billing_cfg.get("per_project_budget"))
        summary["budgets"]["automation_budget"] = self._safe_budget_value(billing_cfg.get("automation_budget"))

        run_buckets: dict[str, dict[str, Any]] = {}
        for record in records:
            record_project_id = str(record.get("project_id") or "").strip() or None
            if project_id and record_project_id != project_id:
                continue
            amount = self._billing_amount(record)
            record_date = self._extract_date(str(record.get("ts") or ""))
            mode_bucket = self._billing_bucket(record)
            run_id = str(record.get("run_id") or "unknown")

            bucket = run_buckets.setdefault(run_id, {"run_id": run_id, "cost": 0.0, "usage": 0.0, "records": 0, "last_ts": ""})
            bucket["cost"] += amount
            bucket["usage"] += amount
            bucket["records"] += 1
            bucket["last_ts"] = max(str(bucket.get("last_ts") or ""), str(record.get("ts") or ""))

            summary["project_total"]["cost"] += amount
            summary["project_total"]["usage"] += amount
            summary["project_total"]["records"] += 1
            summary["mode_breakdown"][mode_bucket]["cost"] += amount
            summary["mode_breakdown"][mode_bucket]["usage"] += amount
            summary["mode_breakdown"][mode_bucket]["records"] += 1

            if record_date == today:
                summary["today"]["cost"] += amount
                summary["today"]["usage"] += amount
                summary["today"]["records"] += 1

            for key in ("provider", "model", "agent", "node"):
                raw_value = record.get(f"{key}_id", record.get(key))
                value = str(raw_value or "unknown")
                bucket = summary["breakdown"][key].setdefault(value, {"cost": 0.0, "usage": 0.0, "records": 0})
                bucket["cost"] += amount
                bucket["usage"] += amount
                bucket["records"] += 1

        # Budgets使用全域/專案資料，不受 project filter 影響 daily_usage
        all_records = self._read_jsonl_records(self.core.data_dir / "logs" / "billing.log")
        for record in all_records:
            amount = self._billing_amount(record)
            record_date = self._extract_date(str(record.get("ts") or ""))
            if record_date == today:
                summary["budgets"]["daily_usage"] += amount
            if project_id and str(record.get("project_id") or "").strip() == project_id:
                summary["budgets"]["project_usage"] += amount
            if self._billing_bucket(record) == "automation":
                summary["budgets"]["automation_usage"] += amount

        for event in self._read_jsonl_records(self.core.data_dir / "logs" / "amon.log"):
            if str(event.get("event") or "") != "budget_exceeded":
                continue
            if project_id and str(event.get("project_id") or "") != project_id:
                continue
            summary["exceeded_events"].append(event)
        summary["exceeded_events"].sort(key=lambda item: str(item.get("ts") or ""), reverse=True)
        summary["exceeded_events"] = summary["exceeded_events"][:50]
        summary["run_trend"] = sorted(run_buckets.values(), key=lambda item: str(item.get("last_ts") or ""))[-20:]
        if summary["run_trend"]:
            latest = summary["run_trend"][-1]
            summary["current_run"] = {
                "run_id": latest.get("run_id"),
                "cost": float(latest.get("cost") or 0.0),
                "usage": float(latest.get("usage") or 0.0),
                "records": int(latest.get("records") or 0),
            }
        return summary

    def _handle_billing_stream(self, *, project_id: str | None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        billing_log = self.core.data_dir / "logs" / "billing.log"
        amon_log = self.core.data_dir / "logs" / "amon.log"

        def emit(event_type: str, payload: dict[str, Any]) -> None:
            body = f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            self.wfile.write(body.encode("utf-8"))
            self.wfile.flush()

        try:
            last_billing_mtime = billing_log.stat().st_mtime if billing_log.exists() else 0.0
            last_amon_mtime = amon_log.stat().st_mtime if amon_log.exists() else 0.0
            known_budget_count = len(
                [
                    item
                    for item in self._read_jsonl_records(amon_log)
                    if str(item.get("event") or "") == "budget_exceeded"
                    and (not project_id or str(item.get("project_id") or "") == project_id)
                ]
            )
            emit("usage_updated", self._build_billing_summary(project_id=project_id))
            while True:
                time.sleep(2)
                current_billing_mtime = billing_log.stat().st_mtime if billing_log.exists() else 0.0
                if current_billing_mtime != last_billing_mtime:
                    last_billing_mtime = current_billing_mtime
                    emit("usage_updated", self._build_billing_summary(project_id=project_id))

                current_amon_mtime = amon_log.stat().st_mtime if amon_log.exists() else 0.0
                if current_amon_mtime == last_amon_mtime:
                    continue
                last_amon_mtime = current_amon_mtime
                budget_events = [
                    item
                    for item in self._read_jsonl_records(amon_log)
                    if str(item.get("event") or "") == "budget_exceeded"
                    and (not project_id or str(item.get("project_id") or "") == project_id)
                ]
                if len(budget_events) > known_budget_count:
                    for item in budget_events[known_budget_count:]:
                        emit("budget_exceeded", item)
                    known_budget_count = len(budget_events)
                    emit("usage_updated", self._build_billing_summary(project_id=project_id))
        except (BrokenPipeError, ConnectionResetError):
            return

    def _read_jsonl_records(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
        except OSError:
            return []
        return records

    def _parse_time(self, text: str) -> datetime | None:
        value = text.strip()
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("time range 必須是 ISO 時間格式") from exc

    def _load_latest_graph(self, project_path: Path) -> dict[str, Any]:
        runs_dir = project_path / ".amon" / "runs"
        if runs_dir.exists():
            run_dirs = [path for path in runs_dir.iterdir() if path.is_dir()]
            if run_dirs:
                latest = max(run_dirs, key=lambda path: path.stat().st_mtime)
                resolved_path = latest / "graph.resolved.json"
                if resolved_path.exists():
                    return json.loads(resolved_path.read_text(encoding="utf-8"))
        fallback = project_path / ".amon" / "graphs" / "single_graph.resolved.json"
        if fallback.exists():
            return json.loads(fallback.read_text(encoding="utf-8"))
        return {"nodes": [], "edges": []}

    def _build_docs_catalog(self, *, project_id: str, project_path: Path) -> list[dict[str, Any]]:
        docs_dir = project_path / "docs"
        if not docs_dir.exists():
            return []
        source_by_path: dict[str, dict[str, str]] = {}
        runs_dir = project_path / ".amon" / "runs"
        if runs_dir.exists():
            for run_dir in runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                for event in self._read_jsonl_records(run_dir / "events.jsonl"):
                    node_id = str(event.get("node_id") or "").strip()
                    for key in ("path", "output_path", "doc_path", "artifact_path"):
                        raw_path = str(event.get(key) or "").strip()
                        if not raw_path or not raw_path.startswith("docs/"):
                            continue
                        relative_path = raw_path.replace("docs/", "", 1)
                        source_by_path.setdefault(
                            relative_path,
                            {
                                "run_id": run_dir.name,
                                "node_id": node_id or "unknown",
                            },
                        )

        docs: list[dict[str, Any]] = []
        for path in sorted(docs_dir.rglob("*")):
            if not path.is_file():
                continue
            relative_path = str(path.relative_to(docs_dir))
            mime_type, _ = mimetypes.guess_type(str(path))
            inferred = source_by_path.get(relative_path, {})
            run_id = inferred.get("run_id") or self._infer_run_id_from_path(relative_path)
            node_id = inferred.get("node_id") or "unknown"
            task_id = self._infer_task_id_from_path(relative_path)
            encoded_project_id = quote(project_id, safe="")
            encoded_path = quote(relative_path, safe="")
            docs.append(
                {
                    "path": relative_path,
                    "name": path.name,
                    "mime_type": mime_type,
                    "type": mime_type,
                    "run_id": run_id or "unknown",
                    "node_id": node_id,
                    "task_id": task_id or "ungrouped",
                    "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    "download_url": f"/v1/projects/{encoded_project_id}/docs/download?path={encoded_path}",
                    "raw_url": f"/v1/projects/{encoded_project_id}/docs/raw?path={encoded_path}",
                    "open_url": f"/v1/projects/{encoded_project_id}/docs/content?path={encoded_path}",
                }
            )
        return docs

    def _resolve_doc_path(self, project_path: Path, relative_path: str) -> Path:
        docs_dir = (project_path / "docs").resolve()
        candidate = (docs_dir / relative_path).resolve()
        if docs_dir not in candidate.parents and candidate != docs_dir:
            raise ValueError("path 必須位於 docs 目錄下")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError("找不到文件")
        return candidate

    def _resolve_run_artifacts(
        self,
        run_id: str,
        *,
        project_id: str | None,
        route_prefix: str = "/v1",
    ) -> tuple[str, Path, list[dict[str, Any]]]:
        if not run_id or "/" in run_id or ".." in run_id:
            raise ValueError("run_id 格式不正確")

        matched_projects: list[ProjectRecord] = []
        if project_id:
            matched_projects = [self.core.get_project(project_id)]
        else:
            for record in self.core.list_projects(include_deleted=False):
                run_dir = Path(record.path) / ".amon" / "runs" / run_id
                if run_dir.exists() and run_dir.is_dir():
                    matched_projects.append(record)
            if len(matched_projects) > 1:
                raise ValueError("run_id 對應多個專案，請提供 project_id")

        if not matched_projects:
            raise FileNotFoundError("找不到指定的 run")

        project = matched_projects[0]
        run_dir = Path(project.path) / ".amon" / "runs" / run_id
        if not run_dir.exists() or not run_dir.is_dir():
            raise FileNotFoundError("找不到指定的 run")

        artifacts = self._build_run_artifacts_catalog(
            project_id=project.project_id,
            project_path=Path(project.path),
            run_id=run_id,
            route_prefix=route_prefix,
        )
        return project.project_id, Path(project.path), artifacts

    def _build_run_artifacts_catalog(
        self,
        *,
        project_id: str,
        project_path: Path,
        run_id: str,
        route_prefix: str = "/v1",
    ) -> list[dict[str, Any]]:
        run_dir = project_path / ".amon" / "runs" / run_id
        if not run_dir.exists() or not run_dir.is_dir():
            raise FileNotFoundError("找不到指定的 run")

        allowed_dirs = [project_path / "docs", project_path / "audits"]
        candidates: dict[str, Path] = {}

        event_path = run_dir / "events.jsonl"
        for event in self._read_jsonl_records(event_path):
            for key in ("path", "output_path", "doc_path", "artifact_path"):
                raw_path = str(event.get(key) or "").strip()
                if not raw_path:
                    continue
                try:
                    resolved = self._resolve_allowed_project_path(project_path, raw_path, allowed_dirs)
                except (FileNotFoundError, ValueError):
                    continue
                candidates.setdefault(raw_path, resolved)

        artifacts_hint_dir = project_path / "docs" / "artifacts" / run_id
        if artifacts_hint_dir.exists() and artifacts_hint_dir.is_dir():
            for file_path in artifacts_hint_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                rel = str(file_path.relative_to(project_path))
                candidates.setdefault(rel, file_path)

        artifacts: list[dict[str, Any]] = []
        encoded_project_id = quote(project_id, safe="")
        for relative_path, resolved_path in sorted(candidates.items()):
            stat = resolved_path.stat()
            mime_type, _ = mimetypes.guess_type(str(resolved_path))
            artifact_id = quote(relative_path, safe="")
            encoded_run_id = quote(run_id, safe="")
            base_url = f"{route_prefix}/runs/{encoded_run_id}/artifacts/{artifact_id}"
            artifacts.append(
                {
                    "id": artifact_id,
                    "name": resolved_path.name,
                    "path": relative_path,
                    "size": stat.st_size,
                    "mime": mime_type or "application/octet-stream",
                    "created_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                    "url": f"{base_url}?project_id={encoded_project_id}&inline=true",
                    "download_url": f"{base_url}?project_id={encoded_project_id}",
                    "_resolved_path": str(resolved_path),
                }
            )
        return artifacts

    def _resolve_allowed_project_path(
        self,
        project_path: Path,
        relative_path: str,
        allowed_dirs: list[Path],
    ) -> Path:
        candidate = (project_path / relative_path).resolve()
        allowed_roots = [allowed_dir.resolve() for allowed_dir in allowed_dirs]
        if not any(candidate == root or root in candidate.parents for root in allowed_roots):
            raise ValueError("artifact path 不在允許目錄")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError("找不到 artifact")
        return candidate

    def _artifact_public_fields(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "path": item.get("path"),
            "size": item.get("size"),
            "mime": item.get("mime"),
            "created_at": item.get("created_at"),
            "url": item.get("url"),
            "download_url": item.get("download_url"),
        }

    def _infer_run_id_from_path(self, relative_path: str) -> str | None:
        matched = re.search(r"(?:^|[_-])run[_-]?([a-zA-Z0-9]+)", relative_path)
        if matched:
            return f"run_{matched.group(1)}"
        return None

    def _infer_task_id_from_path(self, relative_path: str) -> str | None:
        parts = Path(relative_path).parts
        if "tasks" in parts:
            index = parts.index("tasks")
            if index + 1 < len(parts):
                return parts[index + 1]
        return None

    def _list_docs(self, docs_dir: Path) -> list[str]:
        if not docs_dir.exists():
            return []
        docs: list[str] = []
        for path in docs_dir.rglob("*"):
            if path.is_file():
                docs.append(str(path.relative_to(docs_dir)))
        return sorted(docs)

    def _graph_to_mermaid(self, graph: dict[str, Any]) -> str:
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        if not nodes:
            return "graph TD\n  empty[\"尚無 graph\"]"
        lines = ["graph TD"]
        id_map: dict[str, str] = {}
        used_ids: set[str] = set()

        def to_safe_mermaid_id(node_id: str) -> str:
            base = re.sub(r"[^0-9A-Za-z_]", "_", node_id).strip("_")
            if not base:
                base = "node"
            if re.match(r"^[0-9]", base):
                base = f"n_{base}"
            candidate = base
            suffix = 2
            while candidate in used_ids:
                candidate = f"{base}_{suffix}"
                suffix += 1
            used_ids.add(candidate)
            return candidate

        def escape_mermaid_label(label: str) -> str:
            return (
                label.replace("\\", "\\\\")
                .replace('"', r'\"')
                .replace("\n", "\\n")
            )

        for node in nodes:
            node_id = str(node.get("id", ""))
            safe_id = to_safe_mermaid_id(node_id)
            id_map[node_id] = safe_id
            lines.append(f"  {safe_id}[\"{escape_mermaid_label(node_id)}\"]")
        for edge in edges:
            source = id_map.get(str(edge.get("from", "")), "")
            target = id_map.get(str(edge.get("to", "")), "")
            if source and target:
                lines.append(f"  {source} --> {target}")
        return "\n".join(lines)


def serve_ui(port: int = 8000, data_dir: Path | None = None) -> None:
    ui_dir = Path(__file__).resolve().parent / "ui"
    if not ui_dir.exists():
        raise FileNotFoundError(f"找不到 UI 資料夾：{ui_dir}")
    core = AmonCore(data_dir=data_dir)
    core.ensure_base_structure()
    handler = functools.partial(AmonUIHandler, directory=str(ui_dir), core=core)
    server = AmonThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"UI 已啟動：http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止 UI 伺服器")
    finally:
        server.server_close()
