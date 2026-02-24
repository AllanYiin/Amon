"""Store parsed artifacts under project workspace with history backups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .parser import parse_artifact_blocks
from .safety import resolve_workspace_target


@dataclass(frozen=True)
class ArtifactWriteResult:
    index: int
    declared_path: str
    target_path: str
    status: str
    backup_path: str
    error: str


def _history_backup_path(project_path: Path, target_path: Path) -> Path:
    workspace_root = (project_path / "workspace").resolve()
    relative = target_path.resolve().relative_to(workspace_root)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    history_root = project_path / ".amon" / "artifacts" / "history"
    return history_root / relative.parent / f"{relative.name}.{stamp}.bak"


def ingest_response_artifacts(response_text: str, project_path: Path) -> list[ArtifactWriteResult]:
    """Parse fenced artifacts from response and write under workspace."""

    results: list[ArtifactWriteResult] = []
    blocks = parse_artifact_blocks(response_text)

    for block in blocks:
        backup_path = ""
        target_str = ""
        try:
            target = resolve_workspace_target(project_path, block.file_path)
            target_str = str(target.relative_to(project_path).as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.is_file():
                backup = _history_backup_path(project_path, target)
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(target.read_bytes())
                backup_path = backup.relative_to(project_path).as_posix()
                status = "updated"
            else:
                status = "created"
            target.write_text(block.content, encoding="utf-8")
            results.append(
                ArtifactWriteResult(
                    index=block.index,
                    declared_path=block.file_path,
                    target_path=target_str,
                    status=status,
                    backup_path=backup_path,
                    error="",
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                ArtifactWriteResult(
                    index=block.index,
                    declared_path=block.file_path,
                    target_path=target_str,
                    status="error",
                    backup_path=backup_path,
                    error=str(exc),
                )
            )
    return results
