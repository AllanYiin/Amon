"""Pure path validation rules for sandbox file I/O declarations."""

from __future__ import annotations

from pathlib import PurePath


def validate_relative_path(path: str) -> str:
    """Validate and normalize a relative workspace path declaration."""
    raw = (path or "").strip()
    if not raw:
        raise ValueError("path 不可為空")
    if "\x00" in raw:
        raise ValueError("path 不可包含 NUL")

    normalized = raw.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("path 包含不合法 segment")

    pure = PurePath(normalized)
    if pure.is_absolute():
        raise ValueError("僅允許相對路徑")
    if parts and parts[0].endswith(":"):
        raise ValueError("不允許磁碟機路徑前綴")

    return pure.as_posix()
