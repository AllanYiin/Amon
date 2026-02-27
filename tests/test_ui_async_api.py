import json
import os
import tempfile
import threading
import time
import unittest
from functools import partial
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import quote

import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class UIAsyncAPITests(unittest.TestCase):

    def test_health_endpoint_includes_queue_depth_and_error_rate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", "/v1/projects/not-found/context")
                err_resp = conn.getresponse()
                err_resp.read()
                self.assertEqual(err_resp.status, 500)

                conn.request("GET", "/health")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertEqual(payload["status"], "ok")
                self.assertIn("queue_depth", payload)
                self.assertIn("recent_error_rate", payload)
                self.assertIn("observability", payload)
                self.assertEqual(payload["observability"]["schema_version"], "v0.1")
                self.assertEqual(payload["observability"]["links"]["metrics"], "/metrics")
                self.assertEqual(
                    payload["recent_error_rate"]["window_seconds"],
                    payload["observability"]["metrics_window_seconds"],
                )
                self.assertGreaterEqual(payload["recent_error_rate"]["request_count"], 2)
                self.assertGreaterEqual(payload["recent_error_rate"]["error_count"], 1)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_metrics_endpoint_exposes_health_counters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", "/health")
                health_response = conn.getresponse()
                health_response.read()
                self.assertEqual(health_response.status, 200)

                conn.request("GET", "/metrics")
                response = conn.getresponse()
                payload = response.read().decode("utf-8")

                self.assertEqual(response.status, 200)
                self.assertIn("text/plain", response.getheader("Content-Type", ""))
                self.assertIn("amon_ui_queue_depth", payload)
                self.assertIn("amon_ui_request_total", payload)
                self.assertIn("amon_ui_error_total", payload)
                self.assertIn("amon_ui_error_rate", payload)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_tools_catalog_endpoint_returns_builtin_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", "/v1/tools/catalog")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertIn("tools", payload)
                self.assertTrue(any(item.get("name") == "filesystem.read" for item in payload["tools"]))
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_chat_stream_emits_immediate_notice_without_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                message = quote("你好")
                conn.request("GET", f"/v1/chat/stream?message={message}")
                response = conn.getresponse()

                self.assertEqual(response.status, 200)
                self.assertIn("text/event-stream", response.getheader("Content-Type", ""))

                lines: list[str] = []
                for _ in range(20):
                    raw_line = response.fp.readline()
                    if not raw_line:
                        break
                    decoded = raw_line.decode("utf-8", errors="ignore").strip()
                    if decoded:
                        lines.append(decoded)
                    if decoded == "event: done":
                        break

                joined = "\n".join(lines)
                self.assertIn("event: notice", joined)
                self.assertIn("已收到你的需求", joined)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_chat_stream_payload_contains_request_id_and_virtual_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", f"/v1/chat/stream?message={quote('哈囉')}")
                response = conn.getresponse()

                self.assertEqual(response.status, 200)
                event_type = ""
                payload = None
                for _ in range(50):
                    raw_line = response.fp.readline()
                    if not raw_line:
                        break
                    decoded = raw_line.decode("utf-8", errors="ignore").strip()
                    if decoded.startswith("event: "):
                        event_type = decoded.split(":", 1)[1].strip()
                    if decoded.startswith("data: ") and event_type == "notice":
                        payload = json.loads(decoded.split(": ", 1)[1])
                        break

                self.assertIsNotNone(payload)
                for key in ("project_id", "run_id", "node_id", "event_id", "request_id", "tool"):
                    self.assertIn(key, payload)
                self.assertEqual(payload["project_id"], "__virtual__")
                self.assertTrue(payload["request_id"])
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_chat_stream_token_and_session_events_include_run_chat_project_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("stream-contract")

                def fake_run_single_stream(
                    prompt,
                    project_path,
                    model=None,
                    stream_handler=None,
                    skill_names=None,
                    run_id=None,
                    conversation_history=None,
                ):
                    if stream_handler:
                        stream_handler("tok-A")
                        stream_handler("tok-B")
                    return SimpleNamespace(run_id=run_id or "run-contract-001"), "final-contract"

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch.object(
                    core,
                    "run_single_stream",
                    side_effect=fake_run_single_stream,
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&message={quote('請輸出完整結果')}",
                    )
                    resp = conn.getresponse()
                    self.assertEqual(resp.status, 200)

                    event_type = ""
                    token_payload = None
                    done_payload = None
                    for _ in range(200):
                        raw_line = resp.fp.readline()
                        if not raw_line:
                            break
                        decoded = raw_line.decode("utf-8", errors="ignore").strip()
                        if decoded.startswith("event: "):
                            event_type = decoded.split(":", 1)[1].strip()
                        elif decoded.startswith("data: "):
                            payload = json.loads(decoded.split(": ", 1)[1])
                            if event_type == "token" and token_payload is None:
                                token_payload = payload
                            if event_type == "done":
                                done_payload = payload
                                break

                self.assertIsNotNone(token_payload)
                self.assertIsNotNone(done_payload)
                self.assertEqual(token_payload["project_id"], project.project_id)
                self.assertTrue(token_payload.get("chat_id"))
                self.assertIn("run_id", token_payload)

                chat_id = done_payload.get("chat_id")
                self.assertTrue(chat_id)
                session_path = core.get_project_path(project.project_id) / "sessions" / "chat" / f"{chat_id}.jsonl"
                lines = [json.loads(line) for line in session_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                assistant_events = [item for item in lines if item.get("type") == "assistant"]
                self.assertTrue(assistant_events)
                self.assertEqual(assistant_events[-1].get("run_id"), done_payload.get("run_id"))
                self.assertEqual(assistant_events[-1].get("project_id"), project.project_id)
                self.assertEqual(assistant_events[-1].get("chat_id"), chat_id)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_chat_followup_reuses_previous_run_id_when_assistant_asked_question(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("追問延續測試")

                observed_run_ids: list[str | None] = []
                observed_histories: list[list[dict[str, str]] | None] = []
                call_count = 0

                def fake_run_single_stream(
                    prompt,
                    project_path,
                    model=None,
                    stream_handler=None,
                    skill_names=None,
                    run_id=None,
                    conversation_history=None,
                ):
                    nonlocal call_count
                    call_count += 1
                    observed_run_ids.append(run_id)
                    observed_histories.append(conversation_history)
                    if stream_handler:
                        stream_handler("token")
                    response = "好的，請問你要先做前端還是後端？" if call_count == 1 else "了解，我會接續上一段任務繼續完成。"
                    resolved_run_id = run_id or "run-followup-001"
                    return SimpleNamespace(run_id=resolved_run_id), response

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch(
                    "amon.ui_server.should_continue_run_with_llm", return_value=True
                ), patch.object(
                    core,
                    "run_single_stream",
                    side_effect=fake_run_single_stream,
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&message={quote('請幫我建立完整功能')}"
                    )
                    resp1 = conn.getresponse()
                    self.assertEqual(resp1.status, 200)
                    done_payload_1 = None
                    event_type = ""
                    for _ in range(120):
                        raw_line = resp1.fp.readline()
                        if not raw_line:
                            break
                        decoded = raw_line.decode("utf-8", errors="ignore").strip()
                        if decoded.startswith("event: "):
                            event_type = decoded.split(":", 1)[1].strip()
                        elif decoded.startswith("data: ") and event_type == "done":
                            done_payload_1 = json.loads(decoded.split(": ", 1)[1])
                            break

                    self.assertIsNotNone(done_payload_1)
                    chat_id = done_payload_1["chat_id"]
                    self.assertEqual(done_payload_1["run_id"], "run-followup-001")

                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&chat_id={quote(chat_id)}&message={quote('先做後端')}"
                    )
                    resp2 = conn.getresponse()
                    self.assertEqual(resp2.status, 200)
                    event_type = ""
                    done_payload_2 = None
                    for _ in range(120):
                        raw_line = resp2.fp.readline()
                        if not raw_line:
                            break
                        decoded = raw_line.decode("utf-8", errors="ignore").strip()
                        if decoded.startswith("event: "):
                            event_type = decoded.split(":", 1)[1].strip()
                        elif decoded.startswith("data: ") and event_type == "done":
                            done_payload_2 = json.loads(decoded.split(": ", 1)[1])
                            break

                    self.assertIsNotNone(done_payload_2)
                    self.assertEqual(done_payload_2["run_id"], "run-followup-001")

                self.assertEqual(observed_run_ids, [None, "run-followup-001"])
                self.assertEqual(observed_histories[0], [])
                self.assertEqual(
                    observed_histories[1],
                    [
                        {"role": "user", "content": "請幫我建立完整功能"},
                        {"role": "assistant", "content": "好的，請問你要先做前端還是後端？"},
                    ],
                )
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_chat_followup_reuses_previous_run_id_without_question_mark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("追問延續無問號測試")

                observed_run_ids: list[str | None] = []
                call_count = 0

                def fake_run_single_stream(
                    prompt,
                    project_path,
                    model=None,
                    stream_handler=None,
                    skill_names=None,
                    run_id=None,
                    conversation_history=None,
                ):
                    nonlocal call_count
                    call_count += 1
                    observed_run_ids.append(run_id)
                    if stream_handler:
                        stream_handler("token")
                    response = "請提供你要優先處理的範圍，例如前端或後端" if call_count == 1 else "收到，我會直接延續同一個任務 run。"
                    resolved_run_id = run_id or "run-followup-guard-001"
                    return SimpleNamespace(run_id=resolved_run_id), response

                handler = partial(
                    AmonUIHandler,
                    directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"),
                    core=core,
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                with patch("amon.ui_server.decide_execution_mode", return_value="single"), patch(
                    "amon.ui_server.should_continue_run_with_llm", return_value=True
                ), patch.object(
                    core,
                    "run_single_stream",
                    side_effect=fake_run_single_stream,
                ):
                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&message={quote('請幫我規劃上線任務')}"
                    )
                    resp1 = conn.getresponse()
                    self.assertEqual(resp1.status, 200)
                    done_payload_1 = None
                    event_type = ""
                    for _ in range(120):
                        raw_line = resp1.fp.readline()
                        if not raw_line:
                            break
                        decoded = raw_line.decode("utf-8", errors="ignore").strip()
                        if decoded.startswith("event: "):
                            event_type = decoded.split(":", 1)[1].strip()
                        elif decoded.startswith("data: ") and event_type == "done":
                            done_payload_1 = json.loads(decoded.split(": ", 1)[1])
                            break

                    self.assertIsNotNone(done_payload_1)
                    chat_id = done_payload_1["chat_id"]
                    self.assertEqual(done_payload_1["run_id"], "run-followup-guard-001")

                    conn = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&chat_id={quote(chat_id)}&message={quote('後端')}"
                    )
                    resp2 = conn.getresponse()
                    self.assertEqual(resp2.status, 200)
                    event_type = ""
                    done_payload_2 = None
                    for _ in range(120):
                        raw_line = resp2.fp.readline()
                        if not raw_line:
                            break
                        decoded = raw_line.decode("utf-8", errors="ignore").strip()
                        if decoded.startswith("event: "):
                            event_type = decoded.split(":", 1)[1].strip()
                        elif decoded.startswith("data: ") and event_type == "done":
                            done_payload_2 = json.loads(decoded.split(": ", 1)[1])
                            break

                    self.assertIsNotNone(done_payload_2)
                    self.assertEqual(done_payload_2["run_id"], "run-followup-guard-001")

                self.assertEqual(observed_run_ids, [None, "run-followup-guard-001"])
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_run_request_is_non_blocking_and_cancelable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("API 專案")
                project_path = Path(project.path)

                tools_dir = data_dir / "tools"
                tools_dir.mkdir(parents=True, exist_ok=True)
                config_path = data_dir / "config.yaml"
                config_path.write_text(
                    json.dumps({"tools": {"global_dir": str(tools_dir)}}, ensure_ascii=False),
                    encoding="utf-8",
                )
                sleeper_dir = tools_dir / "sleeper"
                sleeper_dir.mkdir(parents=True, exist_ok=True)
                (sleeper_dir / "tool.py").write_text(
                    "\n".join(
                        [
                            "import json",
                            "import sys",
                            "import time",
                            "payload = json.loads(sys.stdin.read() or \"{}\")",
                            "time.sleep(float(payload.get(\"sleep_s\", 2)))",
                            "print(json.dumps({\"ok\": True}))",
                        ]
                    ),
                    encoding="utf-8",
                )
                (sleeper_dir / "tool.yaml").write_text(
                    json.dumps(
                        {
                            "name": "sleeper",
                            "version": "0.1.0",
                            "inputs_schema": {"type": "object"},
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                graph = {
                    "nodes": [
                        {
                            "id": "slow",
                            "type": "tool.call",
                            "tool": "sleeper",
                            "args": {"sleep_s": 5},
                            "timeout_s": 30,
                        }
                    ],
                    "edges": [],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                payload = json.dumps(
                    {
                        "project_id": project.project_id,
                        "graph_path": str(graph_path),
                    }
                )
                conn.request("POST", "/v1/runs", body=payload, headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                body = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 202)
                run_id = body["run_id"]

                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/runs/{run_id}/status?project_id={encoded_project}")
                status_resp = conn.getresponse()
                status_body = json.loads(status_resp.read().decode("utf-8"))
                self.assertEqual(status_resp.status, 200)
                self.assertIn(
                    status_body["run"]["status"],
                    {"running", "pending", "completed", "failed", "canceled", "not_found"},
                )

                cancel_payload = json.dumps({"project_id": project.project_id, "run_id": run_id})
                conn.request("POST", "/v1/runs/cancel", body=cancel_payload, headers={"Content-Type": "application/json"})
                cancel_resp = conn.getresponse()
                cancel_body = json.loads(cancel_resp.read().decode("utf-8"))
                self.assertEqual(cancel_resp.status, 200)
                self.assertEqual(cancel_body["status"], "cancelled")

                end_time = time.monotonic() + 5
                final_status = None
                while time.monotonic() < end_time:
                    conn.request("GET", f"/v1/runs/{run_id}/status?project_id={encoded_project}")
                    poll_resp = conn.getresponse()
                    poll_body = json.loads(poll_resp.read().decode("utf-8"))
                    final_status = poll_body["run"]["status"]
                    if final_status in {"canceled", "failed", "completed"}:
                        break
                    time.sleep(0.1)
                self.assertIsNotNone(final_status)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_project_context_contains_graph_runtime_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("graph-context-test")
                project_path = Path(project.path)

                run_dir = project_path / ".amon" / "runs" / "run-001"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "graph.resolved.json").write_text(
                    json.dumps(
                        {
                            "nodes": [{"id": "draft", "type": "llm.generate", "prompt": "hi"}],
                            "edges": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                (run_dir / "state.json").write_text(
                    json.dumps(
                        {
                            "status": "running",
                            "nodes": {
                                "draft": {
                                    "status": "running",
                                    "output": {"artifacts": ["draft.md"]},
                                }
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                (run_dir / "events.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"event": "node_start", "node_id": "draft"}, ensure_ascii=False),
                            json.dumps({"event": "node_complete", "node_id": "draft"}, ensure_ascii=False),
                        ]
                    ),
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/projects/{encoded_project}/context")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertEqual(payload["run_id"], "run-001")
                self.assertEqual(payload["run_status"], "running")
                self.assertIn("graph", payload)
                self.assertIn("node_states", payload)
                self.assertEqual(payload["node_states"]["draft"]["status"], "running")
                self.assertGreaterEqual(len(payload["recent_events"]), 1)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_project_chat_history_prefers_latest_non_empty_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("chat-history-test")
                project_path = Path(project.path)
                sessions_dir = project_path / "sessions" / "chat"
                sessions_dir.mkdir(parents=True, exist_ok=True)

                filled_session = sessions_dir / "chat-has-history.jsonl"
                filled_session.write_text(
                    "\n".join(
                        [
                            json.dumps({"type": "user", "text": "你好", "ts": "2026-01-01T10:00:00Z"}, ensure_ascii=False),
                            json.dumps({"type": "assistant", "text": "已收到", "ts": "2026-01-01T10:00:01Z"}, ensure_ascii=False),
                        ]
                    ),
                    encoding="utf-8",
                )

                empty_session = sessions_dir / "chat-empty.jsonl"
                empty_session.write_text("", encoding="utf-8")
                os.utime(empty_session, None)

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/projects/{encoded_project}/chat-history")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertEqual(payload["chat_id"], "chat-has-history")
                self.assertEqual(len(payload["messages"]), 2)
                self.assertEqual(payload["messages"][0]["role"], "user")
                self.assertEqual(payload["messages"][1]["role"], "assistant")
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)




    def test_project_context_stats_reads_persisted_project_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("context-persist-test")

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                context_text = "這是正式專案情境，包含產品目標與限制。"

                conn.request(
                    "PUT",
                    f"/v1/projects/{encoded_project}/context",
                    body=json.dumps({"context": context_text}, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                put_response = conn.getresponse()
                put_payload = json.loads(put_response.read().decode("utf-8"))
                self.assertEqual(put_response.status, 200)
                self.assertEqual(put_payload.get("context"), context_text)

                conn.request("GET", f"/v1/projects/{encoded_project}/context")
                get_response = conn.getresponse()
                get_payload = json.loads(get_response.read().decode("utf-8"))
                self.assertEqual(get_response.status, 200)
                self.assertEqual(get_payload.get("context"), context_text)

                conn.request("GET", f"/v1/projects/{encoded_project}/context/stats")
                stats_response = conn.getresponse()
                stats_payload = json.loads(stats_response.read().decode("utf-8"))

                self.assertEqual(stats_response.status, 200)
                category_keys = {item.get("key") for item in stats_payload.get("categories", [])}
                self.assertIn("project_context", category_keys)
                project_context = next(item for item in stats_payload["categories"] if item.get("key") == "project_context")
                self.assertGreaterEqual(project_context.get("tokens", 0), 0)
                self.assertTrue(stats_payload.get("meta", {}).get("has_project_context"))
                tokenizer_meta = stats_payload.get("meta", {}).get("non_dialogue_tokenizer", {})
                self.assertIn("project_context", tokenizer_meta)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_project_context_stats_endpoint_returns_required_categories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("context-stats-test")
                project_path = Path(project.path)

                sessions_dir = project_path / "sessions" / "chat"
                sessions_dir.mkdir(parents=True, exist_ok=True)
                (sessions_dir / "chat-01.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"type": "user", "text": "請幫我搜尋最新 AI 新聞", "ts": "2026-01-01T10:00:00Z"}, ensure_ascii=False),
                            json.dumps({"type": "assistant", "text": "我先整理 context。", "ts": "2026-01-01T10:00:01Z"}, ensure_ascii=False),
                        ]
                    ),
                    encoding="utf-8",
                )

                run_dir = project_path / ".amon" / "runs" / "run-context-001"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "events.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"type": "tool.call", "tool": "web.search"}, ensure_ascii=False),
                            json.dumps({"event": "mcp_tool_call", "name": "search_web"}, ensure_ascii=False),
                        ]
                    ),
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/projects/{encoded_project}/context/stats")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertIn("token_estimate", payload)
                self.assertIn("categories", payload)
                category_keys = {item.get("key") for item in payload["categories"]}
                self.assertTrue({"system_prompt", "tools_definition", "skills", "tool_use", "chat_history"}.issubset(category_keys))
                tool_use = next(item for item in payload["categories"] if item.get("key") == "tool_use")
                self.assertGreaterEqual(tool_use.get("items", 0), 1)
                chat_history = next(item for item in payload["categories"] if item.get("key") == "chat_history")
                self.assertEqual(chat_history.get("tokens"), 0)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_project_context_stats_chat_tokens_follow_api_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("context-chat-usage-test")
                project_path = Path(project.path)

                run_dir = project_path / ".amon" / "runs" / "run-context-usage-001"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "events.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"event": "run_usage", "usage": {"prompt_tokens": 321, "completion_tokens": 123}}, ensure_ascii=False),
                            json.dumps({"event": "run_usage", "prompt_tokens": 79}, ensure_ascii=False),
                        ]
                    ),
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/projects/{encoded_project}/context/stats")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                chat_history = next(item for item in payload["categories"] if item.get("key") == "chat_history")
                self.assertEqual(chat_history.get("tokens"), 400)
                self.assertEqual(payload.get("meta", {}).get("dialogue_token_source"), "api_usage")
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_context_clear_chat_requires_chat_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("context-clear-chat-requires-chat-id")

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                conn.request(
                    "POST",
                    "/v1/context/clear",
                    body=json.dumps({"scope": "chat", "project_id": project.project_id}, ensure_ascii=False),
                    headers={"Content-Type": "application/json"},
                )
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 400)
                self.assertIn("chat_id", payload.get("message", ""))
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_context_clear_chat_only_removes_target_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("context-clear-chat-target-only")
                project_path = Path(project.path)
                sessions_dir = project_path / "sessions" / "chat"
                sessions_dir.mkdir(parents=True, exist_ok=True)
                (sessions_dir / "chat-a.jsonl").write_text('{"type":"user","text":"A"}\n', encoding="utf-8")
                (sessions_dir / "chat-b.jsonl").write_text('{"type":"user","text":"B"}\n', encoding="utf-8")

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                conn.request(
                    "POST",
                    "/v1/context/clear",
                    body=json.dumps({"scope": "chat", "project_id": project.project_id, "chat_id": "chat-a"}, ensure_ascii=False),
                    headers={"Content-Type": "application/json"},
                )
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertEqual(payload.get("scope"), "chat")
                self.assertEqual(payload.get("chat_id"), "chat-a")
                self.assertFalse((sessions_dir / "chat-a.jsonl").exists())
                self.assertTrue((sessions_dir / "chat-b.jsonl").exists())
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_context_clear_project_preserves_chat_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("context-clear-project-preserve-chat")
                project_path = Path(project.path)
                context_path = project_path / ".amon" / "context" / "project_context.md"
                context_path.parent.mkdir(parents=True, exist_ok=True)
                context_path.write_text("project context", encoding="utf-8")
                sessions_dir = project_path / "sessions" / "chat"
                sessions_dir.mkdir(parents=True, exist_ok=True)
                (sessions_dir / "chat-a.jsonl").write_text('{"type":"user","text":"A"}\n', encoding="utf-8")

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                conn.request(
                    "POST",
                    "/v1/context/clear",
                    body=json.dumps({"scope": "project", "project_id": project.project_id}, ensure_ascii=False),
                    headers={"Content-Type": "application/json"},
                )
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertEqual(payload.get("scope"), "project")
                self.assertFalse(context_path.exists())
                self.assertTrue((sessions_dir / "chat-a.jsonl").exists())
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_config_view_api_returns_sources_and_chat_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("config-view-test")
                project_path = Path(project.path)

                (data_dir / "config.yaml").write_text(
                    json.dumps({"amon": {"ui": {"theme": "light"}}}, ensure_ascii=False),
                    encoding="utf-8",
                )
                (project_path / "amon.project.yaml").write_text(
                    json.dumps({"amon": {"ui": {"theme": "dark"}}}, ensure_ascii=False),
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                chat_overrides = quote(json.dumps({"amon": {"ui": {"theme": "chat-theme"}}}, ensure_ascii=False))
                conn.request("GET", f"/v1/config/view?project_id={encoded_project}&chat_overrides={chat_overrides}")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 200)
                self.assertEqual(payload["global_config"]["amon"]["ui"]["theme"], "light")
                self.assertEqual(payload["project_config"]["amon"]["ui"]["theme"], "dark")
                self.assertEqual(payload["effective_config"]["amon"]["ui"]["theme"], "chat-theme")
                self.assertEqual(payload["sources"]["amon"]["ui"]["theme"], "chat")
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)



    def test_logs_and_events_query_api_supports_filters_and_paging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("logs-events-test")
                project_path = Path(project.path)

                logs_dir = data_dir / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                (logs_dir / "amon.log").write_text(
                    "\n".join(
                        [
                            json.dumps({"ts": "2026-01-01T00:00:00+00:00", "level": "INFO", "component": "daemon", "project_id": project.project_id}, ensure_ascii=False),
                            json.dumps({"ts": "2026-01-02T00:00:00+00:00", "level": "ERROR", "component": "runner", "project_id": project.project_id, "run_id": "run-001"}, ensure_ascii=False),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                (logs_dir / "billing.log").write_text(
                    json.dumps({"ts": "2026-01-03T00:00:00+00:00", "level": "INFO", "project_id": project.project_id, "cost": 0.15}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                run_dir = project_path / ".amon" / "runs" / "run-001"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "events.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"ts": "2026-01-02T01:00:00+00:00", "event": "node_start", "node_id": "n1"}, ensure_ascii=False),
                            json.dumps({"ts": "2026-01-02T01:01:00+00:00", "event": "job_triggered", "job_id": "job-1"}, ensure_ascii=False),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/logs/query?source=amon&project_id={encoded_project}&severity=ERROR&page=1&page_size=1")
                logs_resp = conn.getresponse()
                logs_payload = json.loads(logs_resp.read().decode("utf-8"))
                self.assertEqual(logs_resp.status, 200)
                self.assertEqual(logs_payload["total"], 1)
                self.assertEqual(logs_payload["items"][0]["level"], "ERROR")

                conn.request("GET", f"/v1/events/query?project_id={encoded_project}&type=job&page=1&page_size=10")
                events_resp = conn.getresponse()
                events_payload = json.loads(events_resp.read().decode("utf-8"))
                self.assertEqual(events_resp.status, 200)
                self.assertEqual(events_payload["total"], 1)
                self.assertEqual(events_payload["items"][0]["drilldown"]["job_id"], "job-1")

                conn.request("GET", f"/v1/logs/download?source=billing&project_id={encoded_project}")
                download_resp = conn.getresponse()
                body = download_resp.read().decode("utf-8")
                self.assertEqual(download_resp.status, 200)
                self.assertIn("application/x-ndjson", download_resp.getheader("Content-Type"))
                self.assertIn("cost", body)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_docs_api_supports_catalog_preview_download_and_raw_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("docs-api-test")
                project_path = Path(project.path)

                docs_dir = project_path / "docs" / "tasks" / "task-a"
                docs_dir.mkdir(parents=True, exist_ok=True)
                (docs_dir / "result_run_001.md").write_text("# 任務結果\n- 測試", encoding="utf-8")
                binary_bytes = bytes([0, 1, 2, 250, 255])
                (docs_dir / "artifact.bin").write_bytes(binary_bytes)

                run_dir = project_path / ".amon" / "runs" / "run-001"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "events.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"event": "node_output", "node_id": "writer", "output_path": "docs/tasks/task-a/result_run_001.md"}, ensure_ascii=False),
                            json.dumps({"event": "node_output", "node_id": "writer", "artifact_path": "docs/tasks/task-a/artifact.bin"}, ensure_ascii=False),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                encoded_markdown_path = quote("tasks/task-a/result_run_001.md")
                encoded_binary_path = quote("tasks/task-a/artifact.bin")
                conn.request("GET", f"/v1/projects/{encoded_project}/docs")
                docs_resp = conn.getresponse()
                docs_payload = json.loads(docs_resp.read().decode("utf-8"))
                self.assertEqual(docs_resp.status, 200)
                self.assertEqual(len(docs_payload["docs"]), 2)
                conn.request("GET", f"/api/docs?project_id={encoded_project}")
                api_docs_resp = conn.getresponse()
                api_docs_payload = json.loads(api_docs_resp.read().decode("utf-8"))
                self.assertEqual(api_docs_resp.status, 200)
                self.assertEqual(len(api_docs_payload["docs"]), 2)

                markdown_doc = next(doc for doc in docs_payload["docs"] if doc["path"].endswith("result_run_001.md"))
                binary_doc = next(doc for doc in docs_payload["docs"] if doc["path"].endswith("artifact.bin"))
                self.assertEqual(markdown_doc["task_id"], "task-a")
                self.assertEqual(markdown_doc["node_id"], "writer")
                self.assertEqual(markdown_doc["mime_type"], "text/markdown")
                self.assertEqual(markdown_doc["type"], "text/markdown")
                self.assertIn("/docs/raw?path=", markdown_doc["raw_url"])
                self.assertEqual(binary_doc["mime_type"], "application/octet-stream")
                self.assertEqual(binary_doc["type"], "application/octet-stream")

                conn.request("GET", f"/v1/projects/{encoded_project}/docs/content?path={encoded_markdown_path}")
                preview_resp = conn.getresponse()
                preview_payload = json.loads(preview_resp.read().decode("utf-8"))
                self.assertEqual(preview_resp.status, 200)
                self.assertIn("# 任務結果", preview_payload["content"])
                conn.request("GET", f"/api/docs/tasks/task-a/result_run_001.md?project_id={encoded_project}")
                api_doc_resp = conn.getresponse()
                api_doc_payload = json.loads(api_doc_resp.read().decode("utf-8"))
                self.assertEqual(api_doc_resp.status, 200)
                self.assertEqual(api_doc_payload["name"], "result_run_001.md")
                self.assertIn("任務結果", api_doc_payload["content"])

                conn.request("GET", f"/v1/projects/{encoded_project}/docs/download?path={encoded_markdown_path}")
                download_resp = conn.getresponse()
                download_body = download_resp.read().decode("utf-8")
                self.assertEqual(download_resp.status, 200)
                self.assertIn("text/markdown", download_resp.getheader("Content-Type"))
                self.assertIn("任務結果", download_body)

                conn.request("GET", f"/v1/projects/{encoded_project}/docs/raw?path={encoded_binary_path}")
                raw_resp = conn.getresponse()
                raw_body = raw_resp.read()
                self.assertEqual(raw_resp.status, 200)
                self.assertEqual(raw_resp.getheader("Content-Type"), "application/octet-stream")
                self.assertEqual(raw_body, binary_bytes)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_billing_summary_api_returns_breakdown_and_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("bill-page-test")
                project_path = Path(project.path)
                (project_path / "amon.project.yaml").write_text(
                    json.dumps({"billing": {"daily_budget": 5, "per_project_budget": 3, "automation_budget": 2}}, ensure_ascii=False),
                    encoding="utf-8",
                )

                usage_path = project_path / ".amon" / "billing" / "usage.jsonl"
                usage_path.parent.mkdir(parents=True, exist_ok=True)
                usage_path.write_text(
                    "\n".join(
                        [
                            json.dumps({"ts": "2026-01-03T00:00:00+00:00", "project_id": project.project_id, "provider": "openai", "model": "gpt-5.2", "node_id": "n1", "mode": "interactive", "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost": 1.2}, ensure_ascii=False),
                            json.dumps({"ts": "2026-01-03T01:00:00+00:00", "project_id": project.project_id, "provider": "openai", "model": "gpt-5.2", "node_id": "n2", "mode": "automation", "prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200, "cost": 0.8}, ensure_ascii=False),
                        ]
                    ) + "\n",
                    encoding="utf-8",
                )
                logs_dir = data_dir / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                (logs_dir / "amon.log").write_text(
                    json.dumps({"ts": "2026-01-03T02:00:00+00:00", "event": "budget_exceeded", "project_id": project.project_id, "daily_usage": 5.6}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/billing/summary?project_id={encoded_project}")
                resp = conn.getresponse()
                payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(resp.status, 200)
                self.assertIn("openai", payload["breakdown"]["provider"])
                self.assertAlmostEqual(payload["mode_breakdown"]["automation"]["cost"], 0.8)
                self.assertEqual(payload["project_total"]["tokens"], 350)
                self.assertEqual(payload["budgets"]["automation_budget"], 2.0)
                self.assertEqual(len(payload["exceeded_events"]), 1)
                self.assertIn("run_trend", payload)
                self.assertIn("current_run", payload)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_billing_summary_api_returns_breakdown_and_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("bill-page-test")
                project_path = Path(project.path)
                (project_path / "amon.project.yaml").write_text(
                    json.dumps({"billing": {"daily_budget": 5, "per_project_budget": 3, "automation_budget": 2}}, ensure_ascii=False),
                    encoding="utf-8",
                )

                usage_path = project_path / ".amon" / "billing" / "usage.jsonl"
                usage_path.parent.mkdir(parents=True, exist_ok=True)
                usage_path.write_text(
                    "\n".join(
                        [
                            json.dumps({"ts": "2026-01-03T00:00:00+00:00", "project_id": project.project_id, "provider": "openai", "model": "gpt-5.2", "node_id": "n1", "mode": "interactive", "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost": 1.2}, ensure_ascii=False),
                            json.dumps({"ts": "2026-01-03T01:00:00+00:00", "project_id": project.project_id, "provider": "openai", "model": "gpt-5.2", "node_id": "n2", "mode": "automation", "prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200, "cost": 0.8}, ensure_ascii=False),
                        ]
                    ) + "\n",
                    encoding="utf-8",
                )
                logs_dir = data_dir / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                (logs_dir / "amon.log").write_text(
                    json.dumps({"ts": "2026-01-03T02:00:00+00:00", "event": "budget_exceeded", "project_id": project.project_id, "daily_usage": 5.6}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                encoded_project = quote(project.project_id)
                conn.request("GET", f"/v1/billing/summary?project_id={encoded_project}")
                resp = conn.getresponse()
                payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(resp.status, 200)
                self.assertIn("openai", payload["breakdown"]["provider"])
                self.assertAlmostEqual(payload["mode_breakdown"]["automation"]["cost"], 0.8)
                self.assertEqual(payload["project_total"]["tokens"], 350)
                self.assertEqual(payload["budgets"]["automation_budget"], 2.0)
                self.assertEqual(len(payload["exceeded_events"]), 1)
                self.assertIn("run_trend", payload)
                self.assertIn("current_run", payload)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


    def test_billing_summary_api_requires_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port)
                conn.request("GET", "/v1/billing/summary")
                resp = conn.getresponse()
                self.assertEqual(resp.status, 400)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_run_artifacts_api_lists_and_downloads_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("artifacts-api")
                project_path = Path(project.path)
                run_id = "run_art_001"
                run_dir = project_path / ".amon" / "runs" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (project_path / "docs" / "artifacts" / run_id).mkdir(parents=True, exist_ok=True)
                artifact_path = project_path / "docs" / "artifacts" / run_id / "result.txt"
                artifact_path.write_text("hello artifact", encoding="utf-8")
                (run_dir / "events.jsonl").write_text(
                    json.dumps({"event": "artifact_written", "artifact_path": f"docs/artifacts/{run_id}/result.txt"}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", f"/v1/runs/{run_id}/artifacts?project_id={quote(project.project_id)}")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertEqual(len(payload["artifacts"]), 1)
                artifact = payload["artifacts"][0]
                self.assertEqual(artifact["name"], "result.txt")

                conn.request("GET", artifact["download_url"])
                download = conn.getresponse()
                self.assertEqual(download.status, 200)
                self.assertIn("attachment", download.getheader("Content-Disposition", ""))
                self.assertEqual(download.read().decode("utf-8"), "hello artifact")
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_run_artifacts_api_supports_workspace_html_inline_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("artifacts-workspace-html")
                project_path = Path(project.path)
                run_id = "run_art_html_001"
                run_dir = project_path / ".amon" / "runs" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (project_path / "workspace").mkdir(parents=True, exist_ok=True)
                html_path = project_path / "workspace" / "index.html"
                html_path.write_text("<html><body><h1>preview ok</h1></body></html>", encoding="utf-8")
                (run_dir / "events.jsonl").write_text(
                    json.dumps({"event": "artifact_written", "artifact_path": "workspace/index.html"}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", f"/v1/runs/{run_id}/artifacts?project_id={quote(project.project_id)}")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertEqual(len(payload["artifacts"]), 1)
                artifact = payload["artifacts"][0]
                self.assertEqual(artifact["path"], "workspace/index.html")

                conn.request("GET", artifact["download_url"])
                rendered = conn.getresponse()
                self.assertEqual(rendered.status, 200)
                self.assertIn("inline", rendered.getheader("Content-Disposition", ""))
                self.assertEqual(rendered.getheader("X-Frame-Options"), "SAMEORIGIN")
                self.assertEqual(rendered.getheader("Content-Type"), "text/html; charset=utf-8")
                self.assertIn("preview ok", rendered.read().decode("utf-8"))
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_run_artifacts_api_includes_workspace_html_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("artifacts-manifest-workspace-html")
                project_path = Path(project.path)
                run_id = "run_art_manifest_001"
                run_dir = project_path / ".amon" / "runs" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "events.jsonl").write_text("", encoding="utf-8")
                html_path = project_path / "workspace" / "index.html"
                html_path.write_text("<html><body><h1>manifest preview</h1></body></html>", encoding="utf-8")
                manifest_path = project_path / ".amon" / "artifacts" / "manifest.json"
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(
                    json.dumps({"artifacts": [{"path": "workspace/index.html"}]}, ensure_ascii=False),
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", f"/v1/runs/{run_id}/artifacts?project_id={quote(project.project_id)}")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertTrue(any(item.get("path") == "workspace/index.html" for item in payload.get("artifacts", [])))
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_project_artifacts_file_api_supports_inline_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("project-artifact-file-api")
                project_path = Path(project.path)
                html_path = project_path / "workspace" / "index.html"
                html_path.write_text("<html><body><h1>project endpoint preview</h1></body></html>", encoding="utf-8")

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                encoded_project = quote(project.project_id)
                encoded_path = quote("workspace/index.html", safe="")
                conn.request("GET", f"/v1/projects/{encoded_project}/artifacts/file?path={encoded_path}")
                response = conn.getresponse()
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")
                self.assertIn("inline", response.getheader("Content-Disposition", ""))
                self.assertEqual(response.getheader("X-Frame-Options"), "SAMEORIGIN")
                self.assertIn("project endpoint preview", body)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_run_artifacts_api_blocks_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("artifacts-traversal")
                project_path = Path(project.path)
                run_id = "run_art_bad"
                run_dir = project_path / ".amon" / "runs" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (project_path / "docs").mkdir(parents=True, exist_ok=True)
                (run_dir / "events.jsonl").write_text(
                    json.dumps({"event": "artifact_written", "artifact_path": "../../secret.txt"}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", f"/v1/runs/{run_id}/artifacts?project_id={quote(project.project_id)}")
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["artifacts"], [])

                encoded = quote("..%2F..%2Fsecret.txt")
                conn.request("GET", f"/v1/runs/{run_id}/artifacts/{encoded}?project_id={quote(project.project_id)}")
                blocked = conn.getresponse()
                self.assertEqual(blocked.status, 404)
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)

    def test_ui_toast_logging_endpoint_writes_detailed_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            os.environ["AMON_HOME"] = str(data_dir)
            server = None
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("toast-log")

                handler = partial(AmonUIHandler, directory=str(Path(__file__).resolve().parents[1] / "src" / "amon" / "ui"), core=core)
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                body = {
                    "type": "warning",
                    "level": "WARNING",
                    "message": "UI 測試 toast 訊息",
                    "duration_ms": 18000,
                    "project_id": project.project_id,
                    "chat_id": "chat_test_1",
                    "route": "#/logs",
                    "source": "ui",
                    "metadata": {"view": "logs-events", "error_code": "E_TOAST"},
                }

                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request(
                    "POST",
                    "/v1/ui/toasts",
                    body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
                response = conn.getresponse()
                payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(response.status, 202)
                self.assertEqual(payload["status"], "ok")

                log_path = data_dir / "logs" / "amon.log"
                self.assertTrue(log_path.exists())
                records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertTrue(any(item.get("event") == "ui_toast_displayed" for item in records))
                toast_record = next(item for item in records if item.get("event") == "ui_toast_displayed")
                self.assertEqual(toast_record["project_id"], project.project_id)
                self.assertEqual(toast_record["chat_id"], "chat_test_1")
                self.assertEqual(toast_record["level"], "WARNING")
                self.assertEqual(toast_record["metadata"]["error_code"], "E_TOAST")
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
