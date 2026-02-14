"""Core execution engine for shared sandbox runner."""

from __future__ import annotations

import base64
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any

from .config import RunnerSettings
from .models import RunRequest, RunResponse
from .paths import safe_join


class SandboxRunner:
    def __init__(self, settings: RunnerSettings) -> None:
        self.settings = settings
        self._semaphore = BoundedSemaphore(value=max(1, settings.max_concurrency))

    def run(self, request: RunRequest) -> RunResponse:
        if not self._semaphore.acquire(blocking=False):
            raise RuntimeError("runner busy, please retry")
        try:
            return self._run_locked(request)
        finally:
            self._semaphore.release()

    def _run_locked(self, request: RunRequest) -> RunResponse:
        language = str(request.get("language", "")).strip().lower()
        if language != "python":
            raise ValueError("目前僅支援 language=python")

        timeout_s = int(request.get("timeout_s", 10))
        if timeout_s <= 0 or timeout_s > 120:
            raise ValueError("timeout_s 必須介於 1~120")

        code = str(request.get("code", ""))
        code_bytes = code.encode("utf-8")
        if len(code_bytes) > self.settings.limits.max_code_bytes:
            raise ValueError("code 大小超過上限")

        job_id = uuid.uuid4().hex
        root = self.settings.jobs_dir / job_id
        input_dir = root / "input"
        output_dir = root / "output"
        root.mkdir(parents=True, exist_ok=True)
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._materialize_inputs(input_dir, request.get("input_files", []))
            start = time.monotonic()
            exit_code, stdout, stderr, timed_out = self._execute_container(job_id, input_dir, output_dir, code_bytes, timeout_s)
            duration_ms = int((time.monotonic() - start) * 1000)
            output_files = self._collect_outputs(output_dir)
            return {
                "id": job_id,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "output_files": output_files,
            }
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def _materialize_inputs(self, input_dir: Path, input_files: list[dict[str, Any]]) -> None:
        if len(input_files) > self.settings.limits.max_file_count:
            raise ValueError("input_files 數量超過上限")

        total = 0
        for item in input_files:
            rel = str(item.get("path", ""))
            encoded = str(item.get("content_b64", ""))
            try:
                data = base64.b64decode(encoded, validate=True)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"input file 非法 base64: {rel}") from exc

            size = len(data)
            if size > self.settings.limits.max_single_file_bytes:
                raise ValueError(f"input file 超過單檔上限: {rel}")
            total += size
            if total > self.settings.limits.max_input_total_bytes:
                raise ValueError("input_files 總大小超過上限")

            target = safe_join(input_dir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.parent.is_symlink():
                raise ValueError("不允許 symlink path")
            target.write_bytes(data)

    def _docker_command(self, job_id: str, input_dir: Path, output_dir: Path, timeout_s: int) -> list[str]:
        dcfg = self.settings.docker
        tmpfs_opt = f"rw,nosuid,nodev,noexec,size={dcfg.tmpfs_size}"
        return [
            "docker",
            "run",
            "--rm",
            "--name",
            f"amon-sandbox-{job_id[:12]}",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(dcfg.pids_limit),
            "--cpus",
            str(dcfg.cpus),
            "--memory",
            dcfg.memory,
            "--memory-swap",
            dcfg.memory_swap,
            "--tmpfs",
            f"/tmp:{tmpfs_opt}",
            "--tmpfs",
            f"/work:{tmpfs_opt}",
            "-v",
            f"{input_dir.resolve()}:/input:ro",
            "-v",
            f"{output_dir.resolve()}:/output:rw",
            dcfg.image,
            str(timeout_s),
        ]

    def _execute_container(
        self,
        job_id: str,
        input_dir: Path,
        output_dir: Path,
        code_bytes: bytes,
        timeout_s: int,
    ) -> tuple[int, str, str, bool]:
        cmd = self._docker_command(job_id, input_dir, output_dir, timeout_s)
        container_name = f"amon-sandbox-{job_id[:12]}"
        try:
            completed = subprocess.run(
                cmd,
                input=code_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s + 5,
                check=False,
            )
            return (
                int(completed.returncode),
                completed.stdout.decode("utf-8", errors="replace"),
                completed.stderr.decode("utf-8", errors="replace"),
                False,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            return (124, "", "sandbox timeout", True)

    def _collect_outputs(self, output_dir: Path) -> list[dict[str, Any]]:
        files = [path for path in output_dir.rglob("*") if path.is_file()]
        if len(files) > self.settings.limits.max_file_count:
            raise ValueError("output files 數量超過上限")

        payload: list[dict[str, Any]] = []
        total = 0
        base = output_dir.resolve()

        for path in sorted(files):
            resolved = path.resolve()
            resolved.relative_to(base)
            if resolved.is_symlink():
                raise ValueError("不允許 symlink output")
            data = resolved.read_bytes()
            size = len(data)
            if size > self.settings.limits.max_single_file_bytes:
                raise ValueError("output file 超過單檔上限")
            total += size
            if total > self.settings.limits.max_output_total_bytes:
                raise ValueError("output files 總大小超過上限")
            payload.append(
                {
                    "path": resolved.relative_to(base).as_posix(),
                    "content_b64": base64.b64encode(data).decode("ascii"),
                    "size": size,
                }
            )
        return payload
