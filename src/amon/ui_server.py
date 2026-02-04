"""Simple UI server for Amon."""

from __future__ import annotations

import functools
import json
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .core import AmonCore, ProjectRecord
from .logging import log_event


class AmonUIHandler(SimpleHTTPRequestHandler):
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
        if parsed.path == "/v1/projects":
            params = parse_qs(parsed.query)
            include_deleted = params.get("include_deleted", ["false"])[0].lower() == "true"
            records = self.core.list_projects(include_deleted=include_deleted)
            self._send_json(200, {"projects": [record.to_dict() for record in records]})
            return
        if parsed.path.startswith("/v1/projects/"):
            project_id = parsed.path.split("/")[3]
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
        if parsed.path == "/v1/projects":
            payload = self._read_json()
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
            project_id = parsed.path.split("/")[3]
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
            project_id = parsed.path.split("/")[3]
            payload = self._read_json()
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
            project_id = parsed.path.split("/")[3]
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

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

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
