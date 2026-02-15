"""Sandbox execution record helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from amon.fs.atomic import atomic_write_text


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write JSON payload to disk."""

    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    atomic_write_text(path, content + "\n")


def ensure_run_step_dirs(project_path: Path, run_id: str, step_id: str) -> tuple[Path, Path]:
    """Create and return run step and artifacts directories."""

    safe_run_id = _sanitize_segment(run_id, "run_id")
    safe_step_id = _sanitize_segment(step_id, "step_id")

    base = project_path.resolve()
    run_step_dir = _resolve_under(base, Path(".amon") / "runs" / safe_run_id / "sandbox" / safe_step_id)
    artifacts_dir = _resolve_under(base, Path("docs") / "artifacts" / safe_run_id / safe_step_id)

    run_step_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return run_step_dir, artifacts_dir


def truncate_text(text: str, max_kb: int) -> str:
    """Truncate UTF-8 text content to max_kb with marker."""

    if max_kb <= 0:
        return ""

    raw = text.encode("utf-8")
    limit = max_kb * 1024
    if len(raw) <= limit:
        return text

    marker = "\n...[truncated]"
    marker_bytes = marker.encode("utf-8")
    if len(marker_bytes) >= limit:
        return marker_bytes[:limit].decode("utf-8", errors="ignore")

    kept = raw[: limit - len(marker_bytes)].decode("utf-8", errors="ignore")
    return kept + marker


def _sanitize_segment(value: str, field_name: str) -> str:
    candidate = (value or "").strip()
    if not candidate or "/" in candidate or "\\" in candidate or ".." in candidate:
        raise ValueError(f"{field_name} 不合法")
    return candidate


def _resolve_under(base: Path, relative: Path) -> Path:
    target = (base / relative).resolve()
    if base not in target.parents and target != base:
        raise ValueError(f"路徑超出專案目錄：{relative.as_posix()}")
    return target
