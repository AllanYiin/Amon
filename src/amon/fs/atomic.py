"""Atomic write helpers."""

from __future__ import annotations

import errno
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

try:
    import msvcrt  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - POSIX fallback
    msvcrt = None

_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()
_ATOMIC_REPLACE_RETRIES = 5
_ATOMIC_REPLACE_BASE_DELAY_SECONDS = 0.05
_TRANSIENT_REPLACE_ERRNOS = {errno.EACCES, errno.EPERM}
_TRANSIENT_REPLACE_WINERRORS = {5, 32}


def _path_lock(path: Path) -> threading.RLock:
    normalized = str(path.resolve())
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(normalized)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[normalized] = lock
        return lock


def _lock_path(path: Path) -> Path:
    suffix = f"{path.suffix}.lock" if path.suffix else ".lock"
    return path.with_suffix(suffix)


def _is_transient_replace_error(exc: OSError) -> bool:
    winerror = getattr(exc, "winerror", None)
    if winerror in _TRANSIENT_REPLACE_WINERRORS:
        return True
    return exc.errno in _TRANSIENT_REPLACE_ERRNOS


def _replace_with_retry(source: str, destination: Path) -> None:
    delay = _ATOMIC_REPLACE_BASE_DELAY_SECONDS
    for attempt in range(_ATOMIC_REPLACE_RETRIES):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            is_last_attempt = attempt == _ATOMIC_REPLACE_RETRIES - 1
            if is_last_attempt or not os.path.exists(source) or not _is_transient_replace_error(exc):
                raise
            time.sleep(delay)
            delay *= 2


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    with _path_lock(path):
        try:
            with file_lock(_lock_path(path)):
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding=encoding,
                    dir=str(path.parent),
                    prefix=f".{path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as tmp_file:
                    tmp_file.write(content)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                    temp_name = tmp_file.name
                _replace_with_retry(temp_name, path)
        except OSError:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
            raise


@contextmanager
def file_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if fcntl:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif msvcrt:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    lock_path = _lock_path(path)
    with _path_lock(path):
        with file_lock(lock_path):
            with path.open("ab+") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() > 0:
                    handle.seek(-1, os.SEEK_END)
                    if handle.read(1) != b"\n":
                        handle.write(b"\n")
                handle.write(line)
                handle.write(b"\n")
                handle.flush()
                os.fsync(handle.fileno())
