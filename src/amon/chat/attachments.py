"""Attachment persistence helpers for chat inbox."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.fs.safety import validate_identifier


def save_attachment(
    project_path: str | Path,
    chat_id: str,
    source_file_path: str | Path,
    target_name: str | None = None,
) -> dict[str, Any]:
    """Save an attachment into docs/inbox/<chat_id>/ and update manifest."""
    validate_identifier(chat_id, "chat_id")

    resolved_project = Path(project_path).expanduser().resolve()
    source_path = Path(source_file_path).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError("source_file_path 必須是存在的檔案")

    filename = _validate_filename(target_name or source_path.name)
    inbox_dir = resolved_project / "docs" / "inbox" / chat_id
    inbox_dir.mkdir(parents=True, exist_ok=True)

    target_path = inbox_dir / filename
    shutil.copy2(source_path, target_path)

    file_size = target_path.stat().st_size
    file_sha256 = _sha256_file(target_path)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = {
        "filename": filename,
        "original_name": source_path.name,
        "path": f"docs/inbox/{chat_id}/{filename}",
        "sha256": file_sha256,
        "size": file_size,
        "ts": timestamp,
    }

    manifest_path = inbox_dir / "manifest.json"
    manifest = _load_manifest(manifest_path, chat_id)
    manifest["entries"].append(entry)
    manifest["updated_at"] = timestamp
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _load_manifest(manifest_path: Path, chat_id: str) -> dict[str, Any]:
    if not manifest_path.exists():
        return {
            "chat_id": chat_id,
            "entries": [],
            "updated_at": None,
        }

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest.json 格式錯誤")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("manifest.json entries 格式錯誤")
    payload.setdefault("chat_id", chat_id)
    payload.setdefault("updated_at", None)
    return payload


def _validate_filename(filename: str) -> str:
    cleaned = filename.strip()
    if not cleaned:
        raise ValueError("附件檔名不可為空")
    if cleaned in {".", ".."}:
        raise ValueError("附件檔名格式不正確")
    if Path(cleaned).name != cleaned:
        raise ValueError("附件檔名不可包含路徑")
    if any(sep in cleaned for sep in ("/", "\\")):
        raise ValueError("附件檔名不可包含路徑")
    return cleaned


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
