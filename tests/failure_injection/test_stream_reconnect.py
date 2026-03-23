import json
import os
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.core import AmonCore
from amon.domain import Project, RunRecord
from amon.storage import ProjectRepository, RunRepository
from amon.ui_server import AmonUIHandler
from http.server import ThreadingHTTPServer


class StreamReconnectFailureInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["AMON_HOME"] = str(Path(self.temp_dir.name) / "data")
        self.core = AmonCore()
        self.core.initialize()
        self.project = self.core.create_project("stream-reconnect")
        self.project_root = self.core.get_project_path(self.project.project_id)
        ProjectRepository(self.project_root).create(
            Project.create(project_id=self.project.project_id, name=self.project.name, root_path=str(self.project_root))
        )
        run_repo = RunRepository(self.project_root)
        run_repo.create(
            RunRecord.create(run_id="run-stream", template_ref="single", status="succeeded"),
            snapshot_manifest={"version": "amon.manifest.v1"},
            compiled_graph={"version": "taskgraph.v3", "id": "template.single"},
        )
        events_path = self.project_root / ".amon" / "runs" / "run-stream" / "events.jsonl"
        events_path.write_text(
            "\n".join(
                [
                    json.dumps({"event_id": "evt-1", "event": "node.chunk", "text": "alpha"}, ensure_ascii=False),
                    json.dumps({"event_id": "evt-2", "event": "node.chunk", "text": "beta"}, ensure_ascii=False),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        handler = partial(
            AmonUIHandler,
            directory=str(Path(__file__).resolve().parents[2] / "src" / "amon" / "ui"),
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

    def test_run_stream_reconnect_replays_from_last_event_id(self) -> None:
        first = HTTPConnection("127.0.0.1", self.port, timeout=5)
        first.request("GET", f"/v1/projects/{self.project.project_id}/runs/run-stream/stream")
        response = first.getresponse()
        self.assertEqual(response.status, 200)
        first_chunk = self._read_until_done(response)
        response.close()
        first.close()
        self.assertIn("id: evt-1", first_chunk)
        self.assertIn("alpha", first_chunk)

        second = HTTPConnection("127.0.0.1", self.port, timeout=5)
        second.request(
            "GET",
            f"/v1/projects/{self.project.project_id}/runs/run-stream/stream",
            headers={"Last-Event-ID": "evt-1"},
        )
        second_response = second.getresponse()
        self.assertEqual(second_response.status, 200)
        replay = self._read_until_done(second_response)
        second_response.close()
        second.close()

        self.assertIn("id: evt-2", replay)
        self.assertIn("beta", replay)
        self.assertNotIn("id: evt-1", replay)

    @staticmethod
    def _read_until_done(response) -> str:
        lines: list[str] = []
        seen_done = False
        while True:
            raw = response.fp.readline()
            if not raw:
                break
            text = raw.decode("utf-8")
            lines.append(text)
            if text.startswith("event: done"):
                seen_done = True
            if seen_done and text == "\n":
                break
        return "".join(lines)


if __name__ == "__main__":
    unittest.main()
