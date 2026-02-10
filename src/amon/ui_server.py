"""Simple UI server for Amon."""

from __future__ import annotations

import functools
import json
import threading
import traceback
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from amon.chat.cli import _build_plan_from_message
from amon.chat.project_bootstrap import bootstrap_project_if_needed, resolve_project_id_from_message
from amon.chat.router import route_intent
from amon.chat.session_store import (
    append_event,
    build_prompt_with_history,
    create_chat_session,
    load_recent_dialogue,
)
from amon.commands.executor import CommandPlan, execute
from amon.daemon.queue import get_queue_depth
from amon.events import emit_event
from amon.jobs.runner import start_job
from .core import AmonCore, ProjectRecord
from .logging import log_event


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


class AmonUIHandler(SimpleHTTPRequestHandler):
    _MAX_BODY_BYTES = 10 * 1024 * 1024
    def __init__(self, *args: Any, core: AmonCore, **kwargs: Any) -> None:
        self.core = core
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/v1/"):
            self._handle_api_get()
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/v1/"):
            self._handle_api_post()
            return
        self.send_error(404, "Not Found")

    def do_PATCH(self) -> None:  # noqa: N802
        if self.path.startswith("/v1/"):
            self._handle_api_patch()
            return
        self.send_error(404, "Not Found")

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path.startswith("/v1/"):
            self._handle_api_delete()
            return
        self.send_error(404, "Not Found")

    def _handle_api_get(self) -> None:
        parsed = urlparse(self.path)
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
        if parsed.path == "/v1/projects":
            params = parse_qs(parsed.query)
            include_deleted = params.get("include_deleted", ["false"])[0].lower() == "true"
            records = self.core.list_projects(include_deleted=include_deleted)
            self._send_json(200, {"projects": [record.to_dict() for record in records]})
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
        return parts[index]

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_error(self, exc: Exception, status: int = 500) -> None:
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

        def send_event(event: str, data: dict[str, Any] | str) -> None:
            payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
            self.wfile.write(f"event: {event}\n".encode("utf-8"))
            for line in payload.splitlines() or [""]:
                self.wfile.write(f"data: {line}\n".encode("utf-8"))
            self.wfile.write(b"\n")
            self.wfile.flush()

        try:
            if project_id is None:
                inferred_project_id = resolve_project_id_from_message(self.core, message)
                if inferred_project_id:
                    project_id = inferred_project_id
            initial_context: dict[str, Any] | None = None
            if project_id and chat_id:
                history = load_recent_dialogue(project_id, chat_id)
                if history:
                    initial_context = {"conversation_history": history}
            router_result = route_intent(message, project_id=project_id, context=initial_context)
            created_project: ProjectRecord | None = None
            if project_id is None:
                created_project = bootstrap_project_if_needed(
                    core=self.core,
                    project_id=project_id,
                    message=message,
                    router_type=router_result.type,
                    build_plan_from_message=_build_plan_from_message,
                    is_slash_command=message.startswith("/"),
                )
                if created_project:
                    project_id = created_project.project_id
                else:
                    send_event("error", {"message": "缺少 project_id"})
                    send_event("done", {"status": "project_required"})
                    return
            if not chat_id:
                chat_id = create_chat_session(project_id)
            history = load_recent_dialogue(project_id, chat_id)
            router_context = {"conversation_history": history} if history else None
            router_result = route_intent(message, project_id=project_id, context=router_context)
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
                command_name, args = _build_plan_from_message(message, router_result.type)
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
                config = self.core.load_config(self.core.get_project_path(project_id))
                provider_name = config.get("amon", {}).get("provider", "openai")
                provider_cfg = config.get("providers", {}).get(provider_name, {})

                def stream_handler(token: str) -> None:
                    send_event("token", {"text": token})
                    append_event(
                        chat_id,
                        {"type": "assistant_chunk", "text": token, "project_id": project_id},
                    )

                result, response_text = self.core.run_single_stream(
                    build_prompt_with_history(message, history),
                    project_path=self.core.get_project_path(project_id),
                    stream_handler=stream_handler,
                )
                append_event(chat_id, {"type": "assistant", "text": response_text, "project_id": project_id})
                send_event(
                    "done",
                    {
                        "status": "ok",
                        "chat_id": chat_id,
                        "project_id": project_id,
                        "run_id": result.run_id,
                    },
                )
                return
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

    def _build_project_context(self, project_id: str) -> dict[str, Any]:
        project_path = self.core.get_project_path(project_id)
        graph = self._load_latest_graph(project_path)
        docs = self._list_docs(project_path / "docs")
        return {
            "graph_mermaid": self._graph_to_mermaid(graph),
            "docs": docs,
        }

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
        id_map = {}
        for node in nodes:
            node_id = str(node.get("id", ""))
            safe_id = node_id.replace("-", "_")
            id_map[node_id] = safe_id
            lines.append(f"  {safe_id}[\"{node_id}\"]")
        for edge in edges:
            source = id_map.get(str(edge.get("from", "")), str(edge.get("from", "")))
            target = id_map.get(str(edge.get("to", "")), str(edge.get("to", "")))
            if source and target:
                lines.append(f"  {source} --> {target}")
        return "\n".join(lines)


def serve_ui(port: int = 8000) -> None:
    ui_dir = Path(__file__).resolve().parent / "ui"
    if not ui_dir.exists():
        raise FileNotFoundError(f"找不到 UI 資料夾：{ui_dir}")
    core = AmonCore()
    core.ensure_base_structure()
    handler = functools.partial(AmonUIHandler, directory=str(ui_dir), core=core)
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"UI 已啟動：http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止 UI 伺服器")
    finally:
        server.server_close()
