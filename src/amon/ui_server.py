"""Simple UI server for Amon."""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve_ui(port: int = 8000) -> None:
    ui_dir = Path(__file__).resolve().parent / "ui"
    if not ui_dir.exists():
        raise FileNotFoundError(f"找不到 UI 資料夾：{ui_dir}")
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(ui_dir))
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"UI 已啟動：http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止 UI 伺服器")
    finally:
        server.server_close()
