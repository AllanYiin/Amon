import json
import os
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.core import AmonCore
from amon.runtime_vnext import ConfirmationQueue
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class VNextRoutesIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["AMON_HOME"] = str(Path(self.temp_dir.name) / "data")
        self.core = AmonCore()
        self.core.initialize()
        self.project = self.core.create_project("stage6-routes")
        handler = partial(
            AmonUIHandler,
            directory=str(Path(__file__).resolve().parents[3] / "src" / "amon" / "ui"),
            core=self.core,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        os.environ.pop("AMON_HOME", None)
        self.temp_dir.cleanup()

    def test_project_summary_and_definition_crud_routes(self) -> None:
        summary = self._request_json("GET", f"/v1/projects/{self.project.project_id}")
        self.assertEqual(summary["project"]["id"], self.project.project_id)
        self.assertIn("definition_counts", summary)

        created = self._request_json(
            "POST",
            f"/v1/projects/{self.project.project_id}/tasks",
            {"id": "task.demo", "title": "Demo", "goal": "route smoke", "status": "active"},
            expected_status=201,
        )
        self.assertEqual(created["definition"]["id"], "task.demo")

        listed = self._request_json("GET", f"/v1/projects/{self.project.project_id}/tasks")
        self.assertTrue(any(item["id"] == "task.demo" for item in listed["tasks"]))

        updated = self._request_json(
            "PATCH",
            f"/v1/projects/{self.project.project_id}/tasks/task.demo",
            {"goal": "route smoke updated"},
        )
        self.assertEqual(updated["definition"]["goal"], "route smoke updated")

        deleted = self._request_json("DELETE", f"/v1/projects/{self.project.project_id}/tasks/task.demo")
        self.assertEqual(deleted["definition"]["status"], "archived")

    def test_run_upload_and_confirmation_routes(self) -> None:
        run_created = self._request_json(
            "POST",
            f"/v1/projects/{self.project.project_id}/runs",
            {"template_ref": "single", "execute": False},
            expected_status=201,
        )
        run_id = run_created["run"]["id"]
        self.assertEqual(run_created["run"]["status"], "compiled")

        run_payload = self._request_json("GET", f"/v1/projects/{self.project.project_id}/runs/{run_id}")
        self.assertEqual(run_payload["run"]["id"], run_id)
        self.assertIn("compiled_graph", run_payload)

        events = self._request_json("GET", f"/v1/projects/{self.project.project_id}/runs/{run_id}/events")
        self.assertEqual(events["events"], [])

        source_file = Path(self.temp_dir.name) / "demo.md"
        source_file.write_text("# demo\nhello", encoding="utf-8")
        upload_payload = self._request_json(
            "POST",
            f"/v1/projects/{self.project.project_id}/uploads",
            {"source_path": str(source_file), "notes": "demo upload"},
            expected_status=201,
        )
        asset_id = upload_payload["upload"]["id"]

        preview_payload = self._request_json(
            "GET",
            f"/v1/projects/{self.project.project_id}/uploads/{asset_id}/preview",
        )
        self.assertEqual(preview_payload["preview"]["preview_kind"], "inline_text")
        self.assertIn("hello", preview_payload["preview"]["text"])

        queue = ConfirmationQueue(Path(self.project.path))
        queue.enqueue(run_id, tool_name="filesystem.write", reason="needs approval")
        confirmations = self._request_json("GET", f"/v1/projects/{self.project.project_id}/confirmations")
        self.assertEqual(len(confirmations["confirmations"]), 1)
        confirmation_id = confirmations["confirmations"][0]["id"]

        approved = self._request_json(
            "POST",
            f"/v1/projects/{self.project.project_id}/confirmations/{confirmation_id}/approve",
            {},
        )
        self.assertEqual(approved["confirmation"]["status"], "approved")

    def _request_json(self, method: str, path: str, payload: dict | None = None, *, expected_status: int = 200) -> dict:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = None if payload is None else json.dumps(payload)
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        self.assertEqual(response.status, expected_status, raw)
        return json.loads(raw or "{}")
