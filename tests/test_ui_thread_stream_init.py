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

                def fake_run_graph_stream(
                    prompt,
                    project_path,
                    project_id=None,
                    model=None,
                    llm_client=None,
                    available_tools=None,
                    available_skills=None,
                    stream_handler=None,
                    todo_handler=None,
                    run_id=None,
                    thread_id=None,
                    conversation_history=None,
                    request_id=None,
                ):
                    captured_prompts.append(prompt)
                    if stream_handler:
                        stream_handler("ok")
                    return SimpleNamespace(run_id="run-stream-init", execution_route="planner", planner_enabled=True), "完成"

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
                    "/v1/threads/stream/init",
                    body=json.dumps({"project_id": project.project_id, "message": long_message}),
                    headers={"Content-Type": "application/json"},
                )
                resp = conn.getresponse()
                self.assertEqual(resp.status, 201)
                token_payload = json.loads(resp.read().decode("utf-8"))
                stream_token = token_payload["stream_token"]

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch.object(
                    core,
                    "run_graph_stream",
                    side_effect=fake_run_graph_stream,
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/threads/stream?project_id={quote(project.project_id)}&stream_token={quote(stream_token)}",
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


    def test_stream_ignores_empty_token_chunks_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = str(Path(temp_dir) / "data")
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("stream-empty-chunks")

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                threading.Thread(target=server.serve_forever, daemon=True).start()

                def fake_run_graph_stream(
                    prompt,
                    project_path,
                    project_id=None,
                    model=None,
                    llm_client=None,
                    available_tools=None,
                    available_skills=None,
                    stream_handler=None,
                    todo_handler=None,
                    run_id=None,
                    thread_id=None,
                    conversation_history=None,
                    request_id=None,
                ):
                    if stream_handler:
                        stream_handler("第一段")
                        stream_handler("")
                        stream_handler("第二段")
                    return SimpleNamespace(run_id="run-empty-chunks", execution_route="planner", planner_enabled=True), "第一段第二段"

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request(
                    "POST",
                    "/v1/threads/stream/init",
                    body=json.dumps({"project_id": project.project_id, "message": "請回覆"}),
                    headers={"Content-Type": "application/json"},
                )
                resp = conn.getresponse()
                self.assertEqual(resp.status, 201)
                token_payload = json.loads(resp.read().decode("utf-8"))
                stream_token = token_payload["stream_token"]

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch.object(
                    core,
                    "run_graph_stream",
                    side_effect=fake_run_graph_stream,
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/threads/stream?project_id={quote(project.project_id)}&stream_token={quote(stream_token)}",
                    )
                    sse_resp = conn.getresponse()
                    self.assertEqual(sse_resp.status, 200)
                    events = _read_sse_events(sse_resp)

                done_events = [payload for event_type, payload in events if event_type == "done"]
                self.assertTrue(done_events)
                self.assertEqual(done_events[-1].get("status"), "ok")
                self.assertFalse([payload for event_type, payload in events if event_type == "error"])
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_stream_falls_back_to_placeholder_when_model_returns_empty_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = str(Path(temp_dir) / "data")
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("stream-empty-response")

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                threading.Thread(target=server.serve_forever, daemon=True).start()

                def fake_run_graph_stream(
                    prompt,
                    project_path,
                    project_id=None,
                    model=None,
                    llm_client=None,
                    available_tools=None,
                    available_skills=None,
                    stream_handler=None,
                    todo_handler=None,
                    run_id=None,
                    thread_id=None,
                    conversation_history=None,
                    request_id=None,
                ):
                    return SimpleNamespace(run_id="run-empty-response", execution_route="planner", planner_enabled=True), ""

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request(
                    "POST",
                    "/v1/threads/stream/init",
                    body=json.dumps({"project_id": project.project_id, "message": "請回覆"}),
                    headers={"Content-Type": "application/json"},
                )
                resp = conn.getresponse()
                self.assertEqual(resp.status, 201)
                token_payload = json.loads(resp.read().decode("utf-8"))
                stream_token = token_payload["stream_token"]

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch.object(
                    core,
                    "run_graph_stream",
                    side_effect=fake_run_graph_stream,
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/threads/stream?project_id={quote(project.project_id)}&stream_token={quote(stream_token)}",
                    )
                    sse_resp = conn.getresponse()
                    self.assertEqual(sse_resp.status, 200)
                    done = _read_done_payload(sse_resp)
                    self.assertIsNotNone(done)
                    self.assertEqual(done.get("final_text"), "（本輪未產生文字回覆）")
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)



def _read_sse_events(response):
    events = []
    event_type = ""
    for _ in range(240):
        line = response.fp.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="ignore").strip()
        if decoded.startswith("event: "):
            event_type = decoded.split(":", 1)[1].strip()
        elif decoded.startswith("data: "):
            data = json.loads(decoded.split(": ", 1)[1])
            events.append((event_type, data))
            if event_type == "done":
                break
    return events


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
