import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.ui_server import AmonUIHandler


class UiRunBundleSelectionTests(unittest.TestCase):
    def test_load_latest_graph_prefers_newer_planner_snapshot_over_older_run_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            old_run_dir = project_path / ".amon" / "runs" / "run-old"
            old_run_dir.mkdir(parents=True)
            (old_run_dir / "graph.resolved.json").write_text(
                json.dumps({"nodes": [{"id": "OLD"}], "edges": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            planner_graph_path = project_path / ".amon" / "graphs" / "taskgraph.v3_graph.resolved.json"
            planner_graph_path.parent.mkdir(parents=True, exist_ok=True)
            planner_graph_path.write_text(
                json.dumps({"version": "taskgraph.v3", "nodes": [{"id": "NEW"}], "edges": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            docs_plan_path = project_path / "docs" / "plan.json"
            docs_plan_path.parent.mkdir(parents=True, exist_ok=True)
            docs_plan_path.write_text(
                json.dumps({"version": "taskgraph.v3", "nodes": [{"id": "PLAN"}], "edges": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            os.utime(planner_graph_path, (docs_plan_path.stat().st_mtime + 2, docs_plan_path.stat().st_mtime + 2))

            handler = AmonUIHandler.__new__(AmonUIHandler)

            payload = handler._load_latest_graph(project_path)

            self.assertEqual(payload["nodes"][0]["id"], "NEW")

    def test_load_latest_graph_falls_back_to_docs_plan_when_no_run_graph_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            docs_plan_path = project_path / "docs" / "plan.json"
            docs_plan_path.parent.mkdir(parents=True, exist_ok=True)
            docs_plan_path.write_text(
                json.dumps({"version": "taskgraph.v3", "nodes": [{"id": "PLAN"}], "edges": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            handler = AmonUIHandler.__new__(AmonUIHandler)

            payload = handler._load_latest_graph(project_path)

            self.assertEqual(payload["nodes"][0]["id"], "PLAN")

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

    def test_resolve_project_path_from_run_id_returns_matched_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "project-a"
            run_id = "run-123"
            (project_path / ".amon" / "runs" / run_id).mkdir(parents=True)

            handler = AmonUIHandler.__new__(AmonUIHandler)
            handler.core = type(
                "StubCore",
                (),
                {
                    "list_projects": staticmethod(
                        lambda include_deleted=False: [
                            type("ProjectRecord", (), {"path": str(project_path)})(),
                        ]
                    )
                },
            )()

            resolved = handler._resolve_project_path_from_run_id(run_id)
            self.assertEqual(resolved, project_path)

    def test_resolve_project_path_from_run_id_rejects_ambiguous_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_id = "run-123"
            project_a = base / "project-a"
            project_b = base / "project-b"
            (project_a / ".amon" / "runs" / run_id).mkdir(parents=True)
            (project_b / ".amon" / "runs" / run_id).mkdir(parents=True)

            handler = AmonUIHandler.__new__(AmonUIHandler)
            handler.core = type(
                "StubCore",
                (),
                {
                    "list_projects": staticmethod(
                        lambda include_deleted=False: [
                            type("ProjectRecord", (), {"path": str(project_a)})(),
                            type("ProjectRecord", (), {"path": str(project_b)})(),
                        ]
                    )
                },
            )()

            with self.assertRaisesRegex(ValueError, "run_id 對應多個專案"):
                handler._resolve_project_path_from_run_id(run_id)


if __name__ == "__main__":
    unittest.main()
