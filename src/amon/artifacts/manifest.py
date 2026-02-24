"""Manifest persistence for artifact ingest results."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from amon.fs.atomic import atomic_write_text

_MANIFEST_REL_PATH = Path(".amon") / "artifacts" / "manifest.json"


def _manifest_path(project_path: Path) -> Path:
    return project_path / _MANIFEST_REL_PATH


def _default_manifest() -> dict[str, Any]:
    return {"version": "1", "updated_at": "", "files": {}}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_manifest(project_path: Path) -> dict[str, Any]:
    manifest_path = _manifest_path(project_path)
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _default_manifest()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _default_manifest()
    payload["updated_at"] = _now_iso()
    atomic_write_text(manifest_path, json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def _status_from_checks(checks: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in checks}
    if "invalid" in statuses:
        return "invalid"
    if "valid" in statuses:
        return "valid"
    return "skipped"


def update_manifest_for_file(
    project_path: Path,
    target_path: Path,
    write_status: str,
    checks: list[dict[str, Any]],
    error: str = "",
) -> dict[str, Any]:
    manifest = ensure_manifest(project_path)
    manifest_path = _manifest_path(project_path)
    target_rel = target_path.resolve().relative_to(project_path.resolve()).as_posix()
    content = target_path.read_bytes() if target_path.exists() and target_path.is_file() else b""
    sha256 = hashlib.sha256(content).hexdigest() if content else ""

    files = manifest.setdefault("files", {})
    files[target_rel] = {
        "path": target_rel,
        "sha256": sha256,
        "updated_at": _now_iso(),
        "write_status": write_status,
        "status": _status_from_checks(checks),
        "checks": checks,
        "error": error,
    }
    manifest["updated_at"] = _now_iso()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    return files[target_rel]
