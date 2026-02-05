"""Resident job runner for Amon."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from amon.config import read_yaml
from amon.events import emit_event
from amon.fs.atomic import atomic_write_text
from amon.logging_utils import setup_logger


logger = logging.getLogger("amon.jobs")

JobCallback = Callable[[dict[str, Any]], dict[str, Any] | None]
EventEmitter = Callable[[dict[str, Any]], str]


@dataclass
class JobStatus:
    job_id: str
    status: str
    last_heartbeat_ts: str | None
    last_error: str | None


@dataclass
class _JobHandle:
    job_id: str
    stop_event: threading.Event
    threads: list[threading.Thread]
    status: str
    last_error: str | None
    heartbeat_interval_seconds: int
    data_dir: Path
    event_emitter: EventEmitter


_JOB_REGISTRY: dict[str, _JobHandle] = {}


def start_job(
    job_id: str,
    *,
    data_dir: Path | None = None,
    heartbeat_interval_seconds: int = 5,
    polling_callback: JobCallback | None = None,
    event_emitter: EventEmitter | None = None,
) -> JobStatus:
    if not job_id.strip():
        raise ValueError("job_id 不可為空")
    if job_id in _JOB_REGISTRY:
        raise RuntimeError(f"job 已啟動：{job_id}")

    resolved_data_dir = _resolve_data_dir(data_dir)
    logs_dir = resolved_data_dir / "logs"
    setup_logger("amon.jobs", logs_dir)

    config = _load_job_config(job_id, resolved_data_dir)
    stop_event = threading.Event()
    handle = _JobHandle(
        job_id=job_id,
        stop_event=stop_event,
        threads=[],
        status="running",
        last_error=None,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        data_dir=resolved_data_dir,
        event_emitter=event_emitter or emit_event,
    )
    _JOB_REGISTRY[job_id] = handle

    watcher_paths = _normalize_paths(config.get("watch_paths", []))
    if watcher_paths:
        watcher_thread = threading.Thread(
            target=_filesystem_watcher,
            name=f"amon-job-watcher-{job_id}",
            args=(handle, watcher_paths, config),
            daemon=True,
        )
        handle.threads.append(watcher_thread)
        watcher_thread.start()

    polling_interval = _read_int(config.get("polling_interval_seconds"))
    polling_event_type = str(config.get("polling_event_type") or "job.polling").strip()
    if polling_interval and polling_interval > 0:
        polling_thread = threading.Thread(
            target=_polling_job,
            name=f"amon-job-polling-{job_id}",
            args=(handle, polling_interval, polling_event_type, polling_callback),
            daemon=True,
        )
        handle.threads.append(polling_thread)
        polling_thread.start()

    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        name=f"amon-job-heartbeat-{job_id}",
        args=(handle,),
        daemon=True,
    )
    handle.threads.append(heartbeat_thread)
    heartbeat_thread.start()

    return status_job(job_id, data_dir=resolved_data_dir)


def stop_job(job_id: str, *, data_dir: Path | None = None) -> JobStatus:
    resolved_data_dir = _resolve_data_dir(data_dir)
    handle = _JOB_REGISTRY.get(job_id)
    if not handle:
        return _read_state(job_id, resolved_data_dir)

    handle.status = "stopped"
    handle.stop_event.set()
    for thread in handle.threads:
        thread.join(timeout=5)
    _write_state(handle)
    _JOB_REGISTRY.pop(job_id, None)
    return status_job(job_id, data_dir=resolved_data_dir)


def status_job(job_id: str, *, data_dir: Path | None = None) -> JobStatus:
    resolved_data_dir = _resolve_data_dir(data_dir)
    handle = _JOB_REGISTRY.get(job_id)
    if handle:
        last_heartbeat = _read_state_file(job_id, resolved_data_dir).get("last_heartbeat_ts")
        return JobStatus(
            job_id=job_id,
            status=handle.status,
            last_heartbeat_ts=last_heartbeat,
            last_error=handle.last_error,
        )
    return _read_state(job_id, resolved_data_dir)


def _resolve_data_dir(data_dir: Path | None) -> Path:
    if data_dir:
        return data_dir
    env_dir = os.environ.get("AMON_HOME")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path("~/.amon").expanduser()


def _load_job_config(job_id: str, data_dir: Path) -> dict[str, Any]:
    path = data_dir / "jobs" / f"{job_id}.yaml"
    try:
        config = read_yaml(path)
    except Exception as exc:  # noqa: BLE001
        logger.error("讀取 job 設定失敗：%s", exc, exc_info=True)
        raise RuntimeError("讀取 job 設定失敗") from exc
    return config


def _filesystem_watcher(handle: _JobHandle, paths: Iterable[Path], config: dict[str, Any]) -> None:
    debounce_seconds = _read_int(config.get("debounce_seconds")) or 1
    poll_interval = _read_int(config.get("watch_interval_seconds")) or 1
    last_emitted: dict[tuple[str, str], float] = {}
    snapshot = _scan_paths(paths)

    while not handle.stop_event.is_set():
        try:
            time.sleep(poll_interval)
        except Exception as exc:  # noqa: BLE001
            _record_error(handle, "watcher sleep 失敗", exc)
            continue

        try:
            new_snapshot = _scan_paths(paths)
            _diff_snapshots(handle, snapshot, new_snapshot, last_emitted, debounce_seconds)
            snapshot = new_snapshot
        except Exception as exc:  # noqa: BLE001
            _record_error(handle, "watcher 掃描失敗", exc)


def _polling_job(
    handle: _JobHandle,
    interval_seconds: int,
    event_type: str,
    callback: JobCallback | None,
) -> None:
    payload_base = {"job_id": handle.job_id}
    while not handle.stop_event.is_set():
        try:
            time.sleep(interval_seconds)
        except Exception as exc:  # noqa: BLE001
            _record_error(handle, "polling sleep 失敗", exc)
            continue

        if handle.stop_event.is_set():
            break

        try:
            extra_payload = callback(payload_base) if callback else {"message": "polling stub"}
            payload = {**payload_base, **(extra_payload or {})}
            _emit_job_event(handle.event_emitter, handle.job_id, event_type, payload)
        except Exception as exc:  # noqa: BLE001
            _record_error(handle, "polling callback 失敗", exc)


def _heartbeat_loop(handle: _JobHandle) -> None:
    while not handle.stop_event.is_set():
        _write_state(handle)
        try:
            time.sleep(handle.heartbeat_interval_seconds)
        except Exception as exc:  # noqa: BLE001
            _record_error(handle, "heartbeat sleep 失敗", exc)

    _write_state(handle)


def _scan_paths(paths: Iterable[Path]) -> dict[str, tuple[float, int]]:
    snapshot: dict[str, tuple[float, int]] = {}
    for path in paths:
        if path.is_dir():
            for root, _, files in os.walk(path):
                for name in files:
                    file_path = Path(root) / name
                    try:
                        stat = file_path.stat()
                    except OSError:
                        continue
                    snapshot[str(file_path)] = (stat.st_mtime, stat.st_size)
        elif path.exists():
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path)] = (stat.st_mtime, stat.st_size)
    return snapshot


def _diff_snapshots(
    handle: _JobHandle,
    old: dict[str, tuple[float, int]],
    new: dict[str, tuple[float, int]],
    last_emitted: dict[tuple[str, str], float],
    debounce_seconds: int,
) -> None:
    now = time.monotonic()
    for path, meta in new.items():
        if path not in old:
            _emit_fs_event(handle.event_emitter, handle.job_id, "doc.created", path, last_emitted, now, debounce_seconds)
            continue
        if old[path] != meta:
            _emit_fs_event(handle.event_emitter, handle.job_id, "doc.updated", path, last_emitted, now, debounce_seconds)

    for path in old:
        if path not in new:
            _emit_fs_event(handle.event_emitter, handle.job_id, "doc.deleted", path, last_emitted, now, debounce_seconds)


def _emit_fs_event(
    emitter: EventEmitter,
    job_id: str,
    event_type: str,
    path: str,
    last_emitted: dict[tuple[str, str], float],
    now: float,
    debounce_seconds: int,
) -> None:
    key = (path, event_type)
    last_time = last_emitted.get(key)
    if last_time is not None and (now - last_time) < debounce_seconds:
        return
    last_emitted[key] = now
    _emit_job_event(emitter, job_id, event_type, {"job_id": job_id, "path": path})


def _emit_job_event(emitter: EventEmitter, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
    emitter(
        {
            "type": event_type,
            "scope": "job",
            "actor": f"job:{job_id}",
            "payload": payload,
            "risk": "low",
        }
    )


def _write_state(handle: _JobHandle) -> None:
    state_dir = handle.data_dir / "jobs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "job_id": handle.job_id,
        "status": handle.status,
        "last_heartbeat_ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "last_error": handle.last_error,
    }
    state_path = state_dir / f"{handle.job_id}.json"
    try:
        atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        _record_error(handle, "寫入 heartbeat 狀態失敗", exc)


def _read_state_file(job_id: str, data_dir: Path) -> dict[str, Any]:
    path = data_dir / "jobs" / "state" / f"{job_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("讀取 job 狀態失敗：%s", exc, exc_info=True)
        return {}


def _read_state(job_id: str, data_dir: Path) -> JobStatus:
    state = _read_state_file(job_id, data_dir)
    return JobStatus(
        job_id=job_id,
        status=str(state.get("status") or "stopped"),
        last_heartbeat_ts=state.get("last_heartbeat_ts"),
        last_error=state.get("last_error"),
    )


def _normalize_paths(raw_paths: Iterable[Any]) -> list[Path]:
    normalized: list[Path] = []
    for entry in raw_paths:
        if not entry:
            continue
        path = Path(str(entry)).expanduser()
        normalized.append(path)
    return normalized


def _record_error(handle: _JobHandle, message: str, exc: Exception) -> None:
    handle.last_error = str(exc)
    logger.error("%s：%s", message, exc, exc_info=True)


def _read_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
