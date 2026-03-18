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
from amon.chat.thread_store import create_thread_session, append_event
from amon.chat.router_types import RouterResult
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class ChatContinuationFlowTests(unittest.TestCase):
    def test_stream_without_thread_id_reuses_active_session_and_persists_assistant(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("續聊修復測試")

                run_calls: list[tuple[str | None, list[dict[str, str]] | None]] = []
                call_count = 0

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
                    nonlocal call_count
                    call_count += 1
                    run_calls.append((run_id, conversation_history))
                    if stream_handler:
                        stream_handler("tok")
                    reply = "先選前端或後端" if call_count == 1 else "收到，延續剛剛的任務。"
                    return SimpleNamespace(run_id=run_id or "run-keep", execution_route="planner", planner_enabled=True), reply

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                threading.Thread(target=server.serve_forever, daemon=True).start()

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch(
                    "amon.ui_server.should_continue_run_with_llm", return_value=True
                ), patch.object(core, "run_graph_stream", side_effect=fake_run_graph_stream):
                    conn1 = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn1.request(
                        "GET",
                        f"/v1/threads/stream?project_id={quote(project.project_id)}&message={quote('幫我規劃上線')}",
                    )
                    resp1 = conn1.getresponse()
                    self.assertEqual(resp1.status, 200)
                    first_done = _read_done_payload(resp1)
                    self.assertIsNotNone(first_done)
                    first_thread_id = first_done["thread_id"]

                    # Simulate hydrate/reload path: UI reads server-side active thread.
                    ensure_conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    ensure_conn.request(
                        "GET",
                        f"/v1/projects/{quote(project.project_id)}/threads",
                    )
                    ensure_resp = ensure_conn.getresponse()
                    self.assertEqual(ensure_resp.status, 200)
                    ensure_payload = json.loads(ensure_resp.read().decode("utf-8"))
                    self.assertEqual(ensure_payload.get("active_thread_id"), first_thread_id)

                    conn2 = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn2.request(
                        "GET",
                        f"/v1/threads/stream?project_id={quote(project.project_id)}&message={quote('後端')}",
                    )
                    resp2 = conn2.getresponse()
                    self.assertEqual(resp2.status, 200)
                    second_done = _read_done_payload(resp2)
                    self.assertIsNotNone(second_done)
                    self.assertEqual(second_done["thread_id"], first_thread_id)
                    self.assertEqual(second_done.get("thread_id_source"), "active")
                    self.assertGreaterEqual(int(second_done.get("history_count") or 0), 2)

                self.assertEqual(run_calls[0][1], [])
                self.assertEqual(
                    run_calls[1][1],
                    [
                        {"role": "user", "content": "幫我規劃上線"},
                        {"role": "assistant", "content": "先選前端或後端"},
                    ],
                )

                session_file = data_dir / "projects" / project.project_id / ".amon" / "threads" / first_thread_id / "events.jsonl"
                payloads = [json.loads(line) for line in session_file.read_text(encoding="utf-8").splitlines() if line.strip()]
                assistant_events = [item for item in payloads if item.get("type") == "assistant"]
                self.assertGreaterEqual(len(assistant_events), 2)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_projects_create_command_handoffs_active_thread_to_new_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                source_project = core.create_project("原始專案")
                source_thread_id = create_thread_session(source_project.project_id)
                append_event(source_thread_id, {"type": "user", "text": "延續這串建立新專案", "project_id": source_project.project_id})

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                threading.Thread(target=server.serve_forever, daemon=True).start()

                with patch(
                    "amon.ui_server.route_intent",
                    return_value=RouterResult(
                        type="command_plan",
                        confidence=1.0,
                        api="projects.create",
                        args={"name": "移轉後專案"},
                    ),
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/threads/stream?project_id={quote(source_project.project_id)}&thread_id={quote(source_thread_id)}&message={quote('請幫我建立新專案並延續這串')}",  # noqa: E501
                    )
                    resp = conn.getresponse()
                    self.assertEqual(resp.status, 200)
                    events = _read_sse_events(resp)

                result_payload = next(payload for event_type, payload in events if event_type == "result")
                done_payload = next(payload for event_type, payload in events if event_type == "done")
                handoff_payload = done_payload.get("thread_handoff") or {}

                target_project_id = str(done_payload.get("project_id") or "").strip()
                self.assertNotEqual(target_project_id, source_project.project_id)
                self.assertEqual(result_payload.get("status"), "ok")
                self.assertEqual(handoff_payload.get("source_project_id"), source_project.project_id)
                self.assertEqual(handoff_payload.get("source_thread_id"), source_thread_id)
                self.assertEqual(handoff_payload.get("target_project_id"), target_project_id)
                self.assertEqual(handoff_payload.get("target_thread_id"), source_thread_id)
                self.assertEqual(done_payload.get("thread_id"), source_thread_id)

                source_threads_conn = HTTPConnection("127.0.0.1", port, timeout=5)
                source_threads_conn.request("GET", f"/v1/projects/{quote(source_project.project_id)}/threads")
                source_threads_resp = source_threads_conn.getresponse()
                self.assertEqual(source_threads_resp.status, 200)
                source_threads_payload = json.loads(source_threads_resp.read().decode("utf-8"))
                self.assertEqual(source_threads_payload.get("threads"), [])
                self.assertIsNone(source_threads_payload.get("active_thread_id"))

                target_threads_conn = HTTPConnection("127.0.0.1", port, timeout=5)
                target_threads_conn.request("GET", f"/v1/projects/{quote(target_project_id)}/threads")
                target_threads_resp = target_threads_conn.getresponse()
                self.assertEqual(target_threads_resp.status, 200)
                target_threads_payload = json.loads(target_threads_resp.read().decode("utf-8"))
                self.assertEqual(target_threads_payload.get("active_thread_id"), source_thread_id)
                target_thread_ids = {row.get("thread_id") for row in target_threads_payload.get("threads", [])}
                self.assertIn(source_thread_id, target_thread_ids)

                log_path = data_dir / "logs" / "amon.log"
                log_rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertTrue(
                    any(
                        row.get("event") == "ui_chat_stream_thread_handoff_completed"
                        and row.get("source_project_id") == source_project.project_id
                        and row.get("target_project_id") == target_project_id
                        for row in log_rows
                    )
                )
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


def _read_done_payload(response):
    event_type = ""
    for _ in range(150):
        raw_line = response.fp.readline()
        if not raw_line:
            break
        decoded = raw_line.decode("utf-8", errors="ignore").strip()
        if decoded.startswith("event: "):
            event_type = decoded.split(":", 1)[1].strip()
        elif decoded.startswith("data: ") and event_type == "done":
            return json.loads(decoded.split(": ", 1)[1])
    return None


def _read_sse_events(response):
    events = []
    event_type = ""
    for _ in range(150):
        raw_line = response.fp.readline()
        if not raw_line:
            break
        decoded = raw_line.decode("utf-8", errors="ignore").strip()
        if decoded.startswith("event: "):
            event_type = decoded.split(":", 1)[1].strip()
        elif decoded.startswith("data: "):
            payload = json.loads(decoded.split(": ", 1)[1])
            events.append((event_type, payload))
            if event_type == "done":
                break
    return events


if __name__ == "__main__":
    unittest.main()
