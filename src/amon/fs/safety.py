"""Safety helpers for filesystem operations."""

from __future__ import annotations

from pathlib import Path
import os

DEFAULT_DENYLIST = {
    ".ssh",
    ".gnupg",
    ".aws",
    ".kube",
    ".docker",
}

_MAX_IDENTIFIER_LENGTH = 128


def make_change_plan(ops: list[dict[str, str]]) -> str:
    lines = ["# 變更計畫", ""]
    for op in ops:
        action = op.get("action", "unknown")
        target = op.get("target", "")
        detail = op.get("detail", "")
        if detail:
            lines.append(f"- {action}: {target}（{detail}）")
        else:
            lines.append(f"- {action}: {target}")
    return "\n".join(lines)


def require_confirm(plan_text: str) -> bool:
    print(plan_text)
    response = input("請確認是否繼續？(y/N)：").strip().lower()
    return response == "y"


def canonicalize_path(path: Path, allowed_paths: list[Path]) -> Path:
    resolved = path.expanduser().resolve()
    if _contains_denied_segment(resolved):
        raise PermissionError("路徑包含敏感資料，已拒絕操作")
    allowed = [allowed_path.expanduser().resolve() for allowed_path in allowed_paths]
    if not any(_is_within(resolved, base) for base in allowed):
        raise ValueError("路徑不允許操作")
    return resolved


def _is_within(target: Path, base: Path) -> bool:
    try:
        target.relative_to(base)
    except ValueError:
        return False
    return True


def _contains_denied_segment(path: Path) -> bool:
    return any(part in DEFAULT_DENYLIST for part in path.parts)


def validate_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不可為空")
    if value.strip() != value or any(ch.isspace() for ch in value):
        raise ValueError(f"{field_name} 格式不正確")
    if value in {".", ".."} or ".." in value:
        raise ValueError(f"{field_name} 格式不正確")
    if len(value) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{field_name} 格式不正確")
    if any(ord(ch) < 32 for ch in value):
        raise ValueError(f"{field_name} 格式不正確")
    separators = {"/", "\\"}
    if os.sep:
        separators.add(os.sep)
    if os.altsep:
        separators.add(os.altsep)
    if any(sep in value for sep in separators):
        raise ValueError(f"{field_name} 格式不正確")


def validate_project_id(project_id: str) -> None:
    validate_identifier(project_id, "project_id")


def validate_run_id(run_id: str) -> None:
    validate_identifier(run_id, "run_id")
