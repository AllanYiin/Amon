from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import quote

from amon.core import AmonCore
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class ChatSessionEndpointBehaviorTests(unittest.TestCase):
    def test_thread_endpoints_use_active_thread_instead_of_latest(self) -> None:
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

                project_path = f"/v1/projects/{quote(project.project_id)}"

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("POST", f"{project_path}/threads", body=json.dumps({}), headers={"Content-Type": "application/json"})
                create1 = conn.getresponse()
                payload1 = json.loads(create1.read().decode("utf-8"))
                self.assertEqual(create1.status, 201)
                thread1 = payload1["thread_id"]

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("POST", f"{project_path}/threads", body=json.dumps({}), headers={"Content-Type": "application/json"})
                create2 = conn.getresponse()
                payload2 = json.loads(create2.read().decode("utf-8"))
                self.assertEqual(create2.status, 201)
                thread2 = payload2["thread_id"]

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("POST", f"{project_path}/active-thread", body=json.dumps({"thread_id": thread1}), headers={"Content-Type": "application/json"})
                select_resp = conn.getresponse()
                select_payload = json.loads(select_resp.read().decode("utf-8"))
                self.assertEqual(select_resp.status, 200)
                self.assertEqual(select_payload.get("active_thread_id"), thread1)

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", f"{project_path}/threads")
                list_resp = conn.getresponse()
                list_payload = json.loads(list_resp.read().decode("utf-8"))
                self.assertEqual(list_resp.status, 200)
                self.assertEqual(list_payload.get("active_thread_id"), thread1)
                ids = {row.get("thread_id") for row in list_payload.get("threads", [])}
                self.assertIn(thread1, ids)
                self.assertIn(thread2, ids)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
