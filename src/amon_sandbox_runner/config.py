"""Runtime settings for the shared sandbox runner."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunnerLimits:
    max_code_bytes: int = 128 * 1024
    max_file_count: int = 32
    max_single_file_bytes: int = 2 * 1024 * 1024
    max_input_total_bytes: int = 8 * 1024 * 1024
    max_output_total_bytes: int = 8 * 1024 * 1024


@dataclass(frozen=True)
class DockerPolicy:
    image: str = "amon-sandbox-python:latest"
    pids_limit: int = 128
    cpus: float = 1.0
    memory: str = "512m"
    memory_swap: str = "512m"
    tmpfs_size: str = "64m"


@dataclass(frozen=True)
class RunnerSettings:
    host: str = "127.0.0.1"
    port: int = 8088
    max_concurrency: int = 4
    jobs_dir: Path = Path(".sandbox_jobs")
    limits: RunnerLimits = RunnerLimits()
    docker: DockerPolicy = DockerPolicy()



def load_settings() -> RunnerSettings:
    jobs_dir = Path(os.environ.get("AMON_SANDBOX_JOBS_DIR", ".sandbox_jobs"))
    return RunnerSettings(
        host=os.environ.get("AMON_SANDBOX_HOST", "127.0.0.1"),
        port=int(os.environ.get("AMON_SANDBOX_PORT", "8088")),
        max_concurrency=int(os.environ.get("AMON_SANDBOX_MAX_CONCURRENCY", "4")),
        jobs_dir=jobs_dir,
        limits=RunnerLimits(
            max_code_bytes=int(os.environ.get("AMON_SANDBOX_MAX_CODE_BYTES", str(128 * 1024))),
            max_file_count=int(os.environ.get("AMON_SANDBOX_MAX_FILE_COUNT", "32")),
            max_single_file_bytes=int(os.environ.get("AMON_SANDBOX_MAX_SINGLE_FILE_BYTES", str(2 * 1024 * 1024))),
            max_input_total_bytes=int(os.environ.get("AMON_SANDBOX_MAX_INPUT_TOTAL_BYTES", str(8 * 1024 * 1024))),
            max_output_total_bytes=int(
                os.environ.get("AMON_SANDBOX_MAX_OUTPUT_TOTAL_BYTES", str(8 * 1024 * 1024))
            ),
        ),
        docker=DockerPolicy(
            image=os.environ.get("AMON_SANDBOX_IMAGE", "amon-sandbox-python:latest"),
            pids_limit=int(os.environ.get("AMON_SANDBOX_PIDS_LIMIT", "128")),
            cpus=float(os.environ.get("AMON_SANDBOX_CPUS", "1.0")),
            memory=os.environ.get("AMON_SANDBOX_MEMORY", "512m"),
            memory_swap=os.environ.get("AMON_SANDBOX_MEMORY_SWAP", "512m"),
            tmpfs_size=os.environ.get("AMON_SANDBOX_TMPFS_SIZE", "64m"),
        ),
    )
