import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.application import RunControlPlane
from amon.core import AmonCore
from amon.storage import RunRepository
from amon.taskgraph3.runtime import TaskGraph3RunResult


class RunControlPlaneTests(unittest.TestCase):
    def test_reconcile_executes_queued_run_and_updates_request_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("control-plane-demo")
                project_path = Path(project.path)
                graph_path = project_path / "graph.json"
                graph_path.write_text(
                    json.dumps({"version": "taskgraph.v3", "nodes": [], "edges": []}, ensure_ascii=False),
                    encoding="utf-8",
                )

                def fake_run_graph(*, project_path, graph_path, variables=None, run_id=None, request_id=None, stream_handler=None, **kwargs):
                    run_dir = Path(project_path) / ".amon" / "runs" / str(run_id)
                    run_dir.mkdir(parents=True, exist_ok=True)
                    state = {"run_id": run_id, "status": "succeeded", "nodes": {}, "variables": variables or {}}
                    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    (run_dir / "events.jsonl").write_text(
                        "\n".join(
                            [
                                json.dumps({"event": "run_start", "run_id": run_id}, ensure_ascii=False),
                                json.dumps({"event": "run_end", "run_id": run_id, "status": "succeeded"}, ensure_ascii=False),
                            ]
                        ),
                        encoding="utf-8",
                    )
                    if callable(stream_handler):
                        stream_handler("progress")
                    return TaskGraph3RunResult(run_id=str(run_id), run_dir=run_dir, state=state)

                controller = RunControlPlane(core, max_workers=1)
                with patch.object(core, "run_graph", side_effect=fake_run_graph):
                    request_id = controller.submit_run(
                        project_path=project_path,
                        graph_path=graph_path,
                        variables={"answer": 42},
                        run_id="run-control-001",
                    )
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                repo = RunRepository(project_path)
                run = repo.get("run-control-001")
                control = dict(run.metadata.get("control") or {})
                self.assertEqual(run.status, "succeeded")
                self.assertEqual(control.get("request_status"), "completed")
                self.assertEqual(control.get("lease_owner"), None)
                self.assertEqual(control.get("graph_path"), str(project_path / ".amon" / "runs" / "run-control-001" / "compiled.taskgraph.v3.json"))
                request_status = controller.get_request_status(request_id)
                self.assertIsNotNone(request_status)
                self.assertEqual(request_status["status"], "completed")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_waiting_confirmation_result_keeps_run_alive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("control-plane-confirm")
                project_path = Path(project.path)
                graph_path = project_path / "graph.json"
                graph_path.write_text(
                    json.dumps({"version": "taskgraph.v3", "nodes": [], "edges": []}, ensure_ascii=False),
                    encoding="utf-8",
                )

                def fake_run_graph(*, project_path, graph_path, variables=None, run_id=None, request_id=None, stream_handler=None, **kwargs):
                    run_dir = Path(project_path) / ".amon" / "runs" / str(run_id)
                    run_dir.mkdir(parents=True, exist_ok=True)
                    state = {
                        "run_id": run_id,
                        "status": "succeeded",
                        "nodes": {
                            "approve": {
                                "status": "succeeded",
                                "output": {"status": "waiting_confirmation", "confirmation": {"id": "confirm-001"}},
                            }
                        },
                    }
                    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    (run_dir / "events.jsonl").write_text(json.dumps({"event": "run_end", "run_id": run_id}, ensure_ascii=False), encoding="utf-8")
                    RunRepository(Path(project_path)).enqueue_confirmation(
                        str(run_id),
                        "confirm-001",
                        {"id": "confirm-001", "action": "approve"},
                    )
                    return TaskGraph3RunResult(run_id=str(run_id), run_dir=run_dir, state=state)

                controller = RunControlPlane(core, max_workers=1)
                with patch.object(core, "run_graph", side_effect=fake_run_graph):
                    request_id = controller.submit_run(
                        project_path=project_path,
                        graph_path=graph_path,
                        variables={},
                        run_id="run-control-confirm",
                    )
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                run = RunRepository(project_path).get("run-control-confirm")
                control = dict(run.metadata.get("control") or {})
                self.assertEqual(run.status, "waiting_confirmation")
                self.assertEqual(control.get("request_status"), "pending")
                request_status = controller.get_request_status(request_id)
                self.assertIsNotNone(request_status)
                self.assertEqual(request_status["status"], "pending")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_transient_failure_retries_and_records_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("control-plane-retry")
                project_path = Path(project.path)
                graph_path = project_path / "graph.json"
                graph_path.write_text(
                    json.dumps({"version": "taskgraph.v3", "nodes": [], "edges": []}, ensure_ascii=False),
                    encoding="utf-8",
                )
                calls = {"count": 0}

                def fake_run_graph(*, project_path, graph_path, variables=None, run_id=None, request_id=None, stream_handler=None, **kwargs):
                    calls["count"] += 1
                    if calls["count"] == 1:
                        raise RuntimeError("timeout contacting upstream service")
                    run_dir = Path(project_path) / ".amon" / "runs" / str(run_id)
                    run_dir.mkdir(parents=True, exist_ok=True)
                    state = {"run_id": run_id, "status": "succeeded", "nodes": {}, "variables": variables or {}}
                    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    return TaskGraph3RunResult(run_id=str(run_id), run_dir=run_dir, state=state)

                controller = RunControlPlane(core, max_workers=1, retry_cooldown_seconds=1)
                with patch.object(core, "run_graph", side_effect=fake_run_graph):
                    request_id = controller.submit_run(
                        project_path=project_path,
                        graph_path=graph_path,
                        variables={},
                        run_id="run-control-retry",
                    )
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                    repo = RunRepository(project_path)
                    run = repo.get("run-control-retry")
                    self.assertEqual(run.status, "retry_wait")

                    run = repo.get("run-control-retry")
                    control = dict(run.metadata.get("control") or {})
                    control["next_wake_at"] = "1970-01-01T00:00:00Z"
                    run.update_metadata(metadata={**dict(run.metadata), "control": control})
                    repo.save(run)

                    controller.reconcile_once()
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                run = RunRepository(project_path).get("run-control-retry")
                control = dict(run.metadata.get("control") or {})
                attempts_path = project_path / ".amon" / "runs" / "run-control-retry" / "control.attempts.jsonl"
                attempts = [json.loads(line) for line in attempts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(run.status, "succeeded")
                self.assertEqual(control.get("request_status"), "completed")
                self.assertEqual(len(attempts), 2)
                self.assertEqual(attempts[0]["attempt_type"], "execute")
                self.assertEqual(attempts[1]["attempt_type"], "retry")
                request_status = controller.get_request_status(request_id)
                self.assertIsNotNone(request_status)
                self.assertEqual(request_status["status"], "completed")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_repairable_failure_transitions_through_repairing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("control-plane-repair")
                project_path = Path(project.path)
                graph_path = project_path / "graph.json"
                graph_path.write_text(
                    json.dumps({"version": "taskgraph.v3", "nodes": [], "edges": []}, ensure_ascii=False),
                    encoding="utf-8",
                )
                calls = {"count": 0}

                def fake_run_graph(*, project_path, graph_path, variables=None, run_id=None, request_id=None, stream_handler=None, **kwargs):
                    calls["count"] += 1
                    if calls["count"] == 1:
                        raise ValueError("task.task_spec.executor 不合法：node_id=n1")
                    run_dir = Path(project_path) / ".amon" / "runs" / str(run_id)
                    run_dir.mkdir(parents=True, exist_ok=True)
                    state = {"run_id": run_id, "status": "succeeded", "nodes": {}}
                    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    return TaskGraph3RunResult(run_id=str(run_id), run_dir=run_dir, state=state)

                controller = RunControlPlane(core, max_workers=1)
                with patch.object(core, "run_graph", side_effect=fake_run_graph):
                    controller.submit_run(
                        project_path=project_path,
                        graph_path=graph_path,
                        variables={},
                        run_id="run-control-repair",
                    )
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                    run = RunRepository(project_path).get("run-control-repair")
                    self.assertEqual(run.status, "repairing")

                    controller.reconcile_once()
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                run = RunRepository(project_path).get("run-control-repair")
                attempts_path = project_path / ".amon" / "runs" / "run-control-repair" / "control.attempts.jsonl"
                attempts = [json.loads(line) for line in attempts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(run.status, "succeeded")
                self.assertEqual([item["attempt_type"] for item in attempts], ["execute", "repair", "execute"])
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_replan_rebuilds_compiled_graph_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("control-plane-replan")
                project_path = Path(project.path)
                graph_path = project_path / "graph.json"
                graph_path.write_text(
                    json.dumps({"version": "taskgraph.v3", "name": "source-v1", "nodes": [], "edges": []}, ensure_ascii=False),
                    encoding="utf-8",
                )
                calls = {"count": 0}

                def fake_run_graph(*, project_path, graph_path, variables=None, run_id=None, request_id=None, stream_handler=None, **kwargs):
                    calls["count"] += 1
                    if calls["count"] == 1:
                        raise ValueError("Unsupported graph format: only taskgraph.v3 is supported.")
                    run_dir = Path(project_path) / ".amon" / "runs" / str(run_id)
                    run_dir.mkdir(parents=True, exist_ok=True)
                    state = {"run_id": run_id, "status": "succeeded", "nodes": {}}
                    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    return TaskGraph3RunResult(run_id=str(run_id), run_dir=run_dir, state=state)

                controller = RunControlPlane(core, max_workers=1)
                with patch.object(core, "run_graph", side_effect=fake_run_graph):
                    controller.submit_run(
                        project_path=project_path,
                        graph_path=graph_path,
                        variables={},
                        run_id="run-control-replan",
                    )
                    compiled_path = project_path / ".amon" / "runs" / "run-control-replan" / "compiled.taskgraph.v3.json"
                    compiled_path.write_text(json.dumps({"version": "broken.v0"}, ensure_ascii=False), encoding="utf-8")
                    graph_path.write_text(
                        json.dumps({"version": "taskgraph.v3", "name": "source-v2", "nodes": [], "edges": []}, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))
                    run = RunRepository(project_path).get("run-control-replan")
                    self.assertEqual(run.status, "replanning")

                    controller.reconcile_once()
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                run = RunRepository(project_path).get("run-control-replan")
                compiled_payload = json.loads(compiled_path.read_text(encoding="utf-8"))
                self.assertEqual(run.status, "succeeded")
                self.assertEqual(compiled_payload["name"], "source-v2")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_waiting_external_result_keeps_run_alive_until_state_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("control-plane-waiting-external")
                project_path = Path(project.path)
                graph_path = project_path / "graph.json"
                graph_path.write_text(
                    json.dumps({"version": "taskgraph.v3", "nodes": [], "edges": []}, ensure_ascii=False),
                    encoding="utf-8",
                )

                calls = {"count": 0}

                def fake_run_graph(*, project_path, graph_path, variables=None, run_id=None, request_id=None, stream_handler=None, **kwargs):
                    calls["count"] += 1
                    run_dir = Path(project_path) / ".amon" / "runs" / str(run_id)
                    run_dir.mkdir(parents=True, exist_ok=True)
                    if calls["count"] == 1:
                        state = {
                            "run_id": run_id,
                            "status": "succeeded",
                            "nodes": {
                                "fetch": {
                                    "status": "succeeded",
                                    "output": {"status": "waiting_external", "reason": "awaiting webhook"},
                                }
                            },
                        }
                    else:
                        state = {"run_id": run_id, "status": "succeeded", "nodes": {}}
                    (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                    return TaskGraph3RunResult(run_id=str(run_id), run_dir=run_dir, state=state)

                controller = RunControlPlane(core, max_workers=1)
                with patch.object(core, "run_graph", side_effect=fake_run_graph):
                    controller.submit_run(
                        project_path=project_path,
                        graph_path=graph_path,
                        variables={},
                        run_id="run-control-wait-ext",
                    )
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))
                    repo = RunRepository(project_path)
                    run = repo.get("run-control-wait-ext")
                    self.assertEqual(run.status, "waiting_external")

                    state_path = project_path / ".amon" / "runs" / "run-control-wait-ext" / "state.json"
                    state_path.write_text(
                        json.dumps({"run_id": "run-control-wait-ext", "status": "succeeded", "nodes": {}}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    control = dict(run.metadata.get("control") or {})
                    control["next_wake_at"] = "1970-01-01T00:00:00Z"
                    run.update_metadata(metadata={**dict(run.metadata), "control": control})
                    repo.save(run)

                    controller.reconcile_once()
                    controller.reconcile_once()
                    self.assertTrue(controller.wait_for_idle(timeout=5))

                run = RunRepository(project_path).get("run-control-wait-ext")
                self.assertEqual(run.status, "succeeded")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
