from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
from unittest.mock import patch

from amon.core import AmonCore
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class UIChatStreamInitTests(unittest.TestCase):
    def test_stream_token_supports_long_message_without_query_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = str(Path(temp_dir) / "data")
            server = None
            captured_prompts: list[str] = []
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("stream-init")
                long_message = "長訊息" * 1200

                def fake_run_single_stream(
                    prompt,
                    project_path,
                    model=None,
                    stream_handler=None,
                    skill_names=None,
                    run_id=None,
                    conversation_history=None,
                ):
                    captured_prompts.append(prompt)
                    if stream_handler:
                        stream_handler("ok")
                    return SimpleNamespace(run_id="run-stream-init"), "完成"

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                threading.Thread(target=server.serve_forever, daemon=True).start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request(
                    "POST",
                    "/v1/chat/stream/init",
                    body=json.dumps({"project_id": project.project_id, "message": long_message}),
                    headers={"Content-Type": "application/json"},
                )
                resp = conn.getresponse()
                self.assertEqual(resp.status, 201)
                token_payload = json.loads(resp.read().decode("utf-8"))
                stream_token = token_payload["stream_token"]

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch.object(
                    core,
                    "run_single_stream",
                    side_effect=fake_run_single_stream,
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&stream_token={quote(stream_token)}",
                    )
                    sse_resp = conn.getresponse()
                    self.assertEqual(sse_resp.status, 200)
                    done = _read_done_payload(sse_resp)
                    self.assertIsNotNone(done)

                self.assertTrue(captured_prompts)
                self.assertIn("長訊息", captured_prompts[0])
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)



def _read_done_payload(response):
    event_type = ""
    for _ in range(120):
        line = response.fp.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="ignore").strip()
        if decoded.startswith("event: "):
            event_type = decoded.split(":", 1)[1].strip()
        elif decoded.startswith("data: ") and event_type == "done":
            return json.loads(decoded.split(": ", 1)[1])
    return None


if __name__ == "__main__":
    unittest.main()
