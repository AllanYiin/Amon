"""Bootstrap manifest v1 project storage layout."""

from __future__ import annotations

from pathlib import Path

from ...domain.entities import Project
from ..common import write_json


def bootstrap_manifest_storage(project_root: Path, *, project: Project | None = None) -> dict[str, Path]:
    amon_dir = project_root / ".amon"
    directories = {
        "root": amon_dir,
        "definitions": amon_dir / "definitions",
        "tasks": amon_dir / "definitions" / "tasks",
        "agents": amon_dir / "definitions" / "agents",
        "executors": amon_dir / "definitions" / "executors",
        "workflows": amon_dir / "definitions" / "workflows",
        "templates": amon_dir / "definitions" / "templates",
        "tool_policies": amon_dir / "definitions" / "tool_policies",
        "uploads": amon_dir / "uploads",
        "upload_originals": amon_dir / "uploads" / "originals",
        "upload_previews": amon_dir / "uploads" / "previews",
        "upload_metadata": amon_dir / "uploads" / "metadata",
        "runs": amon_dir / "runs",
        "artifacts": amon_dir / "artifacts",
        "trash": amon_dir / "trash",
        "logs": amon_dir / "logs",
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)

    project_path = amon_dir / "project.json"
    if project is not None:
        write_json(project_path, project.to_dict())
    elif not project_path.exists():
        write_json(project_path, {})

    ui_state_path = amon_dir / "ui_state.json"
    if not ui_state_path.exists():
        write_json(
            ui_state_path,
            {
                "recent_project_id": project.id if project is not None else None,
                "recent_run_id": None,
                "recent_preview_id": None,
                "pending_confirmation_ids": [],
            },
        )

    logs = {
        "amon_log": directories["logs"] / "amon.log",
        "billing_log": directories["logs"] / "billing.log",
    }
    for path in logs.values():
        if not path.exists():
            path.write_text("", encoding="utf-8")

    return {**directories, **logs, "project_file": project_path, "ui_state_file": ui_state_path}
