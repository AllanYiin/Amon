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


class ChatContinuationFlowTests(unittest.TestCase):
    def test_stream_without_chat_id_reuses_latest_session_and_persists_assistant(self) -> None:
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
                    run_calls.append((run_id, conversation_history))
                    if stream_handler:
                        stream_handler("tok")
                    reply = "先選前端或後端" if call_count == 1 else "收到，延續剛剛的任務。"
                    return SimpleNamespace(run_id=run_id or "run-keep"), reply

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
                ), patch.object(core, "run_single_stream", side_effect=fake_run_single_stream):
                    conn1 = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn1.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&message={quote('幫我規劃上線')}",
                    )
                    resp1 = conn1.getresponse()
                    self.assertEqual(resp1.status, 200)
                    first_done = _read_done_payload(resp1)
                    self.assertIsNotNone(first_done)
                    first_chat_id = first_done["chat_id"]

                    conn2 = HTTPConnection("127.0.0.1", port, timeout=5)
                    conn2.request(
                        "GET",
                        f"/v1/chat/stream?project_id={quote(project.project_id)}&message={quote('後端')}",
                    )
                    resp2 = conn2.getresponse()
                    self.assertEqual(resp2.status, 200)
                    second_done = _read_done_payload(resp2)
                    self.assertIsNotNone(second_done)
                    self.assertEqual(second_done["chat_id"], first_chat_id)

                self.assertEqual(run_calls[0][1], [])
                self.assertEqual(
                    run_calls[1][1],
                    [
                        {"role": "user", "content": "幫我規劃上線"},
                        {"role": "assistant", "content": "先選前端或後端"},
                    ],
                )

                session_file = data_dir / "projects" / project.project_id / "sessions" / "chat" / f"{first_chat_id}.jsonl"
                payloads = [json.loads(line) for line in session_file.read_text(encoding="utf-8").splitlines() if line.strip()]
                assistant_events = [item for item in payloads if item.get("type") == "assistant"]
                self.assertGreaterEqual(len(assistant_events), 2)
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


if __name__ == "__main__":
    unittest.main()
