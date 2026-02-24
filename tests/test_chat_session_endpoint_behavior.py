from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from pathlib import Path

from amon.core import AmonCore
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class ChatSessionEndpointBehaviorTests(unittest.TestCase):
    def test_chat_sessions_endpoint_creates_new_id_each_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = str(Path(temp_dir) / "data")
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("chat-session-endpoint")

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                def create_session() -> str:
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "POST",
                        "/v1/chat/sessions",
                        body=json.dumps({"project_id": project.project_id}),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = conn.getresponse()
                    self.assertEqual(resp.status, 201)
                    payload = json.loads(resp.read().decode("utf-8"))
                    return payload["chat_id"]

                first = create_session()
                second = create_session()
                self.assertNotEqual(first, second)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
