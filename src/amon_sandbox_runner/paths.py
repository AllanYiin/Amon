"""Path safety guards for sandbox file declarations."""

from __future__ import annotations

from pathlib import Path, PurePosixPath



def validate_relative_path(path: str) -> str:
    raw = (path or "").strip()
    if not raw:
        raise ValueError("path 不可為空")
    if "\x00" in raw:
        raise ValueError("path 不可包含 NUL")

    normalized = raw.replace("\\", "/")
    pure = PurePosixPath(normalized)
    parts = pure.parts

    if pure.is_absolute():
        raise ValueError("不允許絕對路徑")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("path 包含不合法 segment")

    return pure.as_posix()


def safe_join(base: Path, rel_path: str) -> Path:
    rel = validate_relative_path(rel_path)
    base_resolved = base.resolve()
    candidate = (base_resolved / rel).resolve(strict=False)
    candidate.relative_to(base_resolved)
    return candidate
