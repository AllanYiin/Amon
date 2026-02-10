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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class UIAsyncAPITests(unittest.TestCase):
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



if __name__ == "__main__":
    unittest.main()
