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
    def test_chat_sessions_endpoint_ensures_existing_or_latest_chat_id(self) -> None:
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

                def ensure_session(chat_id: str | None = None) -> tuple[int, dict[str, str]]:
                    body = {"project_id": project.project_id}
                    if chat_id:
                        body["chat_id"] = chat_id
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "POST",
                        "/v1/chat/sessions",
                        body=json.dumps(body),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = conn.getresponse()
                    payload = json.loads(resp.read().decode("utf-8"))
                    return resp.status, payload

                first_status, first_payload = ensure_session()
                self.assertEqual(first_status, 201)
                self.assertEqual(first_payload.get("chat_id_source"), "new")

                second_status, second_payload = ensure_session()
                self.assertEqual(second_status, 200)
                self.assertEqual(second_payload.get("chat_id_source"), "latest")
                self.assertEqual(second_payload["chat_id"], first_payload["chat_id"])

                incoming_status, incoming_payload = ensure_session(first_payload["chat_id"])
                self.assertEqual(incoming_status, 200)
                self.assertEqual(incoming_payload.get("chat_id_source"), "incoming")
                self.assertEqual(incoming_payload["chat_id"], first_payload["chat_id"])
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
