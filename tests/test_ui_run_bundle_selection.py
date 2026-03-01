import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.ui_server import AmonUIHandler


class UiRunBundleSelectionTests(unittest.TestCase):
    def test_load_latest_run_bundle_prefers_running_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            runs_dir = project_path / ".amon" / "runs"
            running_dir = runs_dir / "run-running"
            completed_dir = runs_dir / "run-completed"
            running_dir.mkdir(parents=True)
            completed_dir.mkdir(parents=True)

            (running_dir / "events.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "run_start", "run_id": "run-running"}, ensure_ascii=False),
                        json.dumps({"event": "node_start", "node_id": "N1"}, ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )
            (running_dir / "graph.resolved.json").write_text(
                json.dumps({"nodes": [{"id": "N1"}], "edges": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            (completed_dir / "events.jsonl").write_text(
                json.dumps({"event": "run_complete", "run_id": "run-completed"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (completed_dir / "state.json").write_text(
                json.dumps({"status": "completed", "nodes": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (completed_dir / "graph.resolved.json").write_text(
                json.dumps({"nodes": [{"id": "N2"}], "edges": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            handler = AmonUIHandler.__new__(AmonUIHandler)
            handler._load_latest_graph = lambda _project_path: {"nodes": [], "edges": []}  # type: ignore[attr-defined]

            payload = handler._load_latest_run_bundle(project_path)

            self.assertEqual(payload["run_id"], "run-running")
            self.assertEqual(payload["run_status"], "running")


if __name__ == "__main__":
    unittest.main()
