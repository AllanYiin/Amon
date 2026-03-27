"""Durable control plane for long-running graph tasks."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from amon.domain import RunRecord
from amon.storage import RunRepository
from amon.storage.common import write_json
from amon.taskgraph3.runtime import TaskGraph3RunResult


CONTROL_METADATA_KEY = "control"
TERMINAL_RUN_STATUSES = {"succeeded", "failed", "failed_terminal", "cancelled", "rolled_back", "archived", "abandoned"}
ACTIVE_RUN_STATUSES = {"dispatching", "running", "repairing", "replanning"}
WAKEABLE_RUN_STATUSES = {"queued", "retry_wait"}
TRANSIENT_ERROR_TOKENS = (
    "timeout",
    "temporarily",
    "temporary",
    "connection reset",
    "connection aborted",
    "connection refused",
    "unavailable",
    "busy",
    "rate limit",
    "too many requests",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_to_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def get_run_control(run: RunRecord) -> dict[str, Any]:
    if not isinstance(run.metadata, dict):
        return {}
    control = run.metadata.get(CONTROL_METADATA_KEY)
    return dict(control) if isinstance(control, dict) else {}


def set_run_control(run: RunRecord, control: dict[str, Any]) -> RunRecord:
    metadata = dict(run.metadata or {})
    metadata[CONTROL_METADATA_KEY] = dict(control or {})
    run.update_metadata(metadata=metadata)
    return run


def map_run_status_to_request_status(run_status: str) -> str:
    normalized = str(run_status or "").strip().lower()
    if normalized in {"pending", "running", "completed", "failed", "canceled", "not_found"}:
        return normalized
    if normalized in {"queued", "retry_wait", "waiting_confirmation", "waiting_external", "paused"}:
        return "pending"
    if normalized in {"dispatching", "running", "repairing", "replanning", "retrying"}:
        return "running"
    if normalized == "cancelled":
        return "canceled"
    if normalized == "succeeded":
        return "completed"
    if normalized in {"failed", "failed_terminal", "abandoned"}:
        return "failed"
    return "not_found"


@dataclass
class _ActiveWorker:
    thread: threading.Thread
    project_path: Path
    stop_event: threading.Event


class RunControlPlane:
    def __init__(
        self,
        core,
        *,
        worker_id: str | None = None,
        lease_ttl_seconds: int = 30,
        heartbeat_interval_seconds: int = 5,
        reconcile_interval_seconds: float = 1.0,
        max_workers: int = 2,
    ) -> None:
        self.core = core
        self.worker_id = str(worker_id or f"worker-{uuid.uuid4().hex}")
        self.lease_ttl_seconds = max(heartbeat_interval_seconds + 1, lease_ttl_seconds)
        self.heartbeat_interval_seconds = max(1, heartbeat_interval_seconds)
        self.reconcile_interval_seconds = max(0.2, float(reconcile_interval_seconds))
        self.max_workers = max(1, int(max_workers))
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_workers: dict[str, _ActiveWorker] = {}
        self._request_index: dict[str, dict[str, Any]] = {}

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._reconcile_loop, name=f"amon-run-controller-{self.worker_id}", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = None
        with self._lock:
            thread = self._thread
        if thread:
            thread.join(timeout=5)

    def wait_for_idle(self, timeout: float | None = None) -> bool:
        started = time.monotonic()
        while True:
            self._cleanup_finished_workers()
            with self._lock:
                busy = bool(self._active_workers)
            if not busy:
                return True
            if timeout is not None and (time.monotonic() - started) > timeout:
                return False
            time.sleep(0.05)

    def wake(self) -> None:
        self._wake_event.set()

    def submit_run(
        self,
        *,
        project_path: Path,
        graph_path: str | Path,
        variables: dict[str, Any],
        run_id: str,
        request_id: str | None = None,
    ) -> str:
        selected_request_id = str(request_id or uuid.uuid4().hex)
        resolved_project_path = Path(project_path)
        resolved_graph_path = Path(graph_path)
        if not resolved_graph_path.is_absolute():
            resolved_graph_path = resolved_project_path / resolved_graph_path
        graph_payload = json.loads(resolved_graph_path.read_text(encoding="utf-8"))
        if not isinstance(graph_payload, dict):
            raise ValueError("graph payload 必須是物件")

        repo = RunRepository(resolved_project_path)
        run_dir = resolved_project_path / ".amon" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        compiled_graph_path = run_dir / "compiled.taskgraph.v3.json"
        write_json(compiled_graph_path, graph_payload)

        run_file = run_dir / "run.json"
        if run_file.exists():
            run = repo.get(run_id)
            exists = True
        else:
            run = RunRecord.create(run_id=run_id, status="created")
            exists = False

        control = self._build_control_payload(
            existing=get_run_control(run),
            request_id=selected_request_id,
            graph_path=compiled_graph_path,
        )
        run.mark_status("queued")
        run.update_metadata(metadata=self._merge_run_metadata(run, variables=variables, control=control))
        if exists:
            repo.save(run)
        else:
            repo.create(run, snapshot_manifest={}, compiled_graph=graph_payload)

        with self._lock:
            self._request_index[selected_request_id] = {
                "request_id": selected_request_id,
                "run_id": run_id,
                "project_path": str(resolved_project_path),
                "status": "queued",
                "type": "run",
            }
        self.wake()
        return selected_request_id

    def cancel_run(self, *, project_path: Path, run_id: str) -> None:
        repo = RunRepository(Path(project_path))
        run = repo.get(run_id)
        control = get_run_control(run)
        control["desired_status"] = "cancelled"
        control["request_status"] = "canceled"
        control["terminal_reason"] = control.get("terminal_reason") or "cancel requested"
        run.mark_status("cancelled")
        set_run_control(run, control)
        repo.save(run)
        self.wake()

    def get_request_status(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            payload = dict(self._request_index.get(request_id) or {})
        if not payload:
            return None
        if str(payload.get("type") or "") != "run":
            return payload
        project_path = Path(str(payload.get("project_path") or ""))
        run_id = str(payload.get("run_id") or "")
        if not project_path or not run_id:
            return payload
        run_file = project_path / ".amon" / "runs" / run_id / "run.json"
        if not run_file.exists():
            payload["status"] = "not_found"
            return payload
        repo = RunRepository(project_path)
        run = repo.get(run_id)
        control = get_run_control(run)
        payload["status"] = map_run_status_to_request_status(str(control.get("request_status") or run.status))
        payload["run_status"] = run.status
        if control.get("failure_class"):
            payload["failure_class"] = control.get("failure_class")
        return payload

    def reconcile_once(self) -> None:
        self._cleanup_finished_workers()
        for record in self.core.list_projects(include_deleted=False):
            self._reconcile_project(Path(record.path))

    def _reconcile_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.reconcile_once()
            except Exception:  # noqa: BLE001
                # The caller owns logging policy; keep the loop alive.
                pass
            self._wake_event.wait(self.reconcile_interval_seconds)
            self._wake_event.clear()

    def _reconcile_project(self, project_path: Path) -> None:
        repo = RunRepository(project_path)
        runs = sorted(repo.list(), key=lambda item: item.updated_at)
        for run in runs:
            self._refresh_request_index(run=run, project_path=project_path)
            if run.status in TERMINAL_RUN_STATUSES:
                continue
            control = get_run_control(run)
            if not control:
                continue
            desired_status = str(control.get("desired_status") or "active").strip().lower()
            if desired_status == "cancelled":
                if run.status != "cancelled":
                    run.mark_status("cancelled")
                    control["terminal_reason"] = control.get("terminal_reason") or "cancel requested"
                    control["request_status"] = "canceled"
                    self._clear_lease(control)
                    set_run_control(run, control)
                    repo.save(run)
                continue

            if run.status == "waiting_confirmation":
                if not repo.load_pending_confirmations(run.id):
                    run.mark_status("queued")
                    control["next_wake_at"] = _utc_now_iso()
                    control["request_status"] = "queued"
                    set_run_control(run, control)
                    repo.save(run)
                continue

            if run.status in ACTIVE_RUN_STATUSES and self._lease_expired(control) and not self._is_local_worker_alive(run.id):
                run.mark_status("queued")
                control["failure_class"] = control.get("failure_class") or "lease_expired"
                control["next_wake_at"] = _utc_now_iso()
                control["request_status"] = "queued"
                self._clear_lease(control)
                set_run_control(run, control)
                repo.save(run)
                continue

            if run.status not in WAKEABLE_RUN_STATUSES:
                continue
            if not self._wake_due(control):
                continue
            if self._active_worker_count() >= self.max_workers:
                return
            if not self._claim_run(project_path=project_path, run_id=run.id):
                continue
            self._start_worker(project_path=project_path, run_id=run.id)

    def _start_worker(self, *, project_path: Path, run_id: str) -> None:
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._execute_run,
            name=f"amon-run-worker-{run_id}",
            args=(Path(project_path), run_id, stop_event),
            daemon=True,
        )
        with self._lock:
            self._active_workers[run_id] = _ActiveWorker(thread=thread, project_path=Path(project_path), stop_event=stop_event)
        thread.start()

    def _execute_run(self, project_path: Path, run_id: str, stop_event: threading.Event) -> None:
        repo = RunRepository(project_path)
        run = repo.get(run_id)
        control = get_run_control(run)
        graph_path = Path(str(control.get("graph_path") or ""))
        variables = dict(run.metadata.get("variables") or {}) if isinstance(run.metadata, dict) else {}
        request_id = str(control.get("request_id") or "").strip() or None

        heartbeat_stop = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(project_path, run_id, heartbeat_stop),
            name=f"amon-run-heartbeat-{run_id}",
            daemon=True,
        )
        heartbeat_thread.start()

        def _record_progress(_: str) -> None:
            self._touch_progress(project_path, run_id)

        try:
            result = self.core.run_graph(
                project_path=project_path,
                graph_path=graph_path,
                variables=variables,
                run_id=run_id,
                request_id=request_id,
                stream_handler=_record_progress,
            )
            self._finalize_success(project_path=project_path, run_id=run_id, result=result)
        except Exception as exc:  # noqa: BLE001
            self._finalize_failure(project_path=project_path, run_id=run_id, error_text=str(exc))
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2)
            stop_event.set()
            with self._lock:
                self._active_workers.pop(run_id, None)

    def _finalize_success(self, *, project_path: Path, run_id: str, result: TaskGraph3RunResult) -> None:
        repo = RunRepository(project_path)
        run = repo.get(run_id)
        control = get_run_control(run)
        pending_confirmations = repo.load_pending_confirmations(run_id)
        if pending_confirmations or self._state_waiting_confirmation(result.state):
            run.mark_status("waiting_confirmation")
            control["request_status"] = "pending"
        elif str(control.get("desired_status") or "").strip().lower() == "cancelled":
            run.mark_status("cancelled")
            control["request_status"] = "canceled"
        elif str(result.state.get("status") or "").strip().lower() == "succeeded":
            run.mark_status("succeeded")
            control["request_status"] = "completed"
            control["terminal_reason"] = None
            control["failure_class"] = None
        else:
            error_text = self._extract_failure_text(result.state)
            self._apply_failure_transition(run=run, repo=repo, control=control, error_text=error_text)
            return
        control["last_progress_at"] = _utc_now_iso()
        self._clear_lease(control)
        set_run_control(run, control)
        repo.save(run)

    def _finalize_failure(self, *, project_path: Path, run_id: str, error_text: str) -> None:
        repo = RunRepository(project_path)
        run = repo.get(run_id)
        control = get_run_control(run)
        self._apply_failure_transition(run=run, repo=repo, control=control, error_text=error_text)

    def _apply_failure_transition(self, *, run: RunRecord, repo: RunRepository, control: dict[str, Any], error_text: str) -> None:
        normalized_error = str(error_text or "").strip() or "unknown run failure"
        failure_class = self._classify_failure(normalized_error)
        control["failure_class"] = failure_class
        control["last_error"] = normalized_error
        control["last_progress_at"] = _utc_now_iso()
        if failure_class == "transient" and int(control.get("retry_budget") or 0) > 0:
            control["retry_budget"] = int(control.get("retry_budget") or 0) - 1
            control["next_wake_at"] = (_utc_now() + timedelta(seconds=5)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            control["request_status"] = "pending"
            self._clear_lease(control)
            run.mark_status("retry_wait")
            set_run_control(run, control)
            repo.save(run)
            return
        run.mark_status("failed_terminal")
        control["terminal_reason"] = normalized_error
        control["request_status"] = "failed"
        self._clear_lease(control)
        set_run_control(run, control)
        repo.save(run)

    def _heartbeat_loop(self, project_path: Path, run_id: str, stop_event: threading.Event) -> None:
        while not stop_event.wait(self.heartbeat_interval_seconds):
            self._touch_progress(project_path, run_id, heartbeat_only=True)

    def _touch_progress(self, project_path: Path, run_id: str, *, heartbeat_only: bool = False) -> None:
        repo = RunRepository(project_path)
        try:
            run = repo.get(run_id)
        except Exception:  # noqa: BLE001
            return
        control = get_run_control(run)
        if str(control.get("lease_owner") or "") != self.worker_id:
            return
        now_iso = _utc_now_iso()
        control["last_heartbeat_ts"] = now_iso
        control["lease_expires_at"] = (_utc_now() + timedelta(seconds=self.lease_ttl_seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if not heartbeat_only:
            control["last_progress_at"] = now_iso
        set_run_control(run, control)
        repo.save(run)

    def _claim_run(self, *, project_path: Path, run_id: str) -> bool:
        repo = RunRepository(project_path)
        run_dir = project_path / ".amon" / "runs" / run_id
        try:
            with self._claim_lock(run_dir):
                run = repo.get(run_id)
                control = get_run_control(run)
                if run.status not in WAKEABLE_RUN_STATUSES:
                    return False
                if not self._wake_due(control):
                    return False
                if self._lease_active(control) and str(control.get("lease_owner") or "") != self.worker_id:
                    return False
                now_iso = _utc_now_iso()
                control["lease_owner"] = self.worker_id
                control["lease_expires_at"] = (_utc_now() + timedelta(seconds=self.lease_ttl_seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                control["last_heartbeat_ts"] = now_iso
                control["last_progress_at"] = control.get("last_progress_at") or now_iso
                control["request_status"] = "running"
                control["attempt_count"] = int(control.get("attempt_count") or 0) + 1
                run.mark_status("running")
                set_run_control(run, control)
                repo.save(run)
                return True
        except RuntimeError:
            return False

    @contextmanager
    def _claim_lock(self, run_dir: Path) -> Iterator[None]:
        lock_path = run_dir / "control.claim.lock"
        run_dir.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if lock_path.exists() and (_utc_now().timestamp() - lock_path.stat().st_mtime) > 30:
                    try:
                        lock_path.unlink()
                    except OSError:
                        pass
                    continue
                raise RuntimeError("claim lock busy")
            try:
                os.write(fd, self.worker_id.encode("utf-8"))
                os.close(fd)
                yield
                return
            finally:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
        raise RuntimeError("claim lock busy")

    def _build_control_payload(self, *, existing: dict[str, Any], request_id: str, graph_path: Path) -> dict[str, Any]:
        now_iso = _utc_now_iso()
        control = dict(existing or {})
        control.setdefault("desired_status", "active")
        control["request_id"] = request_id
        control["request_status"] = "queued"
        control["graph_path"] = str(graph_path)
        control.setdefault("retry_budget", 1)
        control.setdefault("repair_budget", 0)
        control.setdefault("attempt_count", 0)
        control.setdefault("last_progress_at", now_iso)
        control["next_wake_at"] = now_iso
        control["failure_class"] = None
        control["terminal_reason"] = None
        self._clear_lease(control)
        return control

    def _merge_run_metadata(self, run: RunRecord, *, variables: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(run.metadata or {})
        metadata["variables"] = dict(variables or {})
        metadata[CONTROL_METADATA_KEY] = dict(control or {})
        return metadata

    def _refresh_request_index(self, *, run: RunRecord, project_path: Path) -> None:
        control = get_run_control(run)
        request_id = str(control.get("request_id") or "").strip()
        if not request_id:
            return
        with self._lock:
            self._request_index[request_id] = {
                "request_id": request_id,
                "run_id": run.id,
                "project_path": str(project_path),
                "status": map_run_status_to_request_status(str(control.get("request_status") or run.status)),
                "type": "run",
            }

    def _cleanup_finished_workers(self) -> None:
        with self._lock:
            stale = [run_id for run_id, item in self._active_workers.items() if not item.thread.is_alive()]
            for run_id in stale:
                self._active_workers.pop(run_id, None)

    def _active_worker_count(self) -> int:
        self._cleanup_finished_workers()
        with self._lock:
            return len(self._active_workers)

    def _is_local_worker_alive(self, run_id: str) -> bool:
        self._cleanup_finished_workers()
        with self._lock:
            item = self._active_workers.get(run_id)
            return bool(item and item.thread.is_alive())

    @staticmethod
    def _clear_lease(control: dict[str, Any]) -> None:
        control["lease_owner"] = None
        control["lease_expires_at"] = None
        control["last_heartbeat_ts"] = control.get("last_heartbeat_ts")

    @staticmethod
    def _wake_due(control: dict[str, Any]) -> bool:
        next_wake_at = _iso_to_datetime(control.get("next_wake_at"))
        return next_wake_at is None or _utc_now() >= next_wake_at

    @staticmethod
    def _lease_active(control: dict[str, Any]) -> bool:
        owner = str(control.get("lease_owner") or "").strip()
        expires_at = _iso_to_datetime(control.get("lease_expires_at"))
        return bool(owner and expires_at and expires_at > _utc_now())

    @staticmethod
    def _lease_expired(control: dict[str, Any]) -> bool:
        owner = str(control.get("lease_owner") or "").strip()
        expires_at = _iso_to_datetime(control.get("lease_expires_at"))
        return bool(owner and expires_at and expires_at <= _utc_now())

    @staticmethod
    def _classify_failure(error_text: str) -> str:
        lowered = str(error_text or "").strip().lower()
        for token in TRANSIENT_ERROR_TOKENS:
            if token in lowered:
                return "transient"
        return "internal_bug"

    @staticmethod
    def _state_waiting_confirmation(state: dict[str, Any]) -> bool:
        nodes = state.get("nodes")
        if not isinstance(nodes, dict):
            return False
        for node_state in nodes.values():
            if not isinstance(node_state, dict):
                continue
            output = node_state.get("output")
            if isinstance(output, dict) and str(output.get("status") or "").strip().lower() == "waiting_confirmation":
                return True
        return False

    @staticmethod
    def _extract_failure_text(state: dict[str, Any]) -> str:
        nodes = state.get("nodes")
        if isinstance(nodes, dict):
            for node_state in nodes.values():
                if not isinstance(node_state, dict):
                    continue
                error_text = str(node_state.get("error") or "").strip()
                if error_text:
                    return error_text
        return str(state.get("status") or "run failed")
