"""Path safety for artifacts ingest writes."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


def resolve_workspace_target(project_path: Path, declared_path: str) -> Path:
    """Resolve and validate target file path under `<project>/workspace/**`."""

    if not isinstance(declared_path, str) or not declared_path.strip():
        raise ValueError("file 路徑不可為空")

    raw = declared_path.strip()
    if "\\" in raw:
        raise ValueError("file 路徑不可包含反斜線")
    if raw.startswith("/"):
        raise ValueError("file 路徑不可為絕對路徑")
    if len(raw) >= 2 and raw[1] == ":":
        raise ValueError("file 路徑不可為絕對路徑")

    rel = PurePosixPath(raw)
    if rel.parts and rel.parts[0] == "workspace":
        rel = PurePosixPath(*rel.parts[1:])
    if not rel.parts:
        raise ValueError("file 路徑不可為空")
    if any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError("file 路徑包含不安全片段")

    workspace_root = (project_path / "workspace").resolve()
    target = (workspace_root / Path(*rel.parts)).resolve()
    try:
        target.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("file 路徑超出 workspace 目錄") from exc
    return target
