"""Trash helpers for safe delete/restore."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path

from ..logging import log_event
from ..logging_utils import setup_logger
from .atomic import atomic_write_text


def trash_move(path: Path, trash_root: Path, original_root: Path) -> str:
    logger = setup_logger("amon", trash_root.parent / "logs")
    path = path.expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(3)
    trash_id = f"{timestamp}_{rand}"
    trash_dir = trash_root / trash_id
    trash_dir.mkdir(parents=True, exist_ok=False)
    target = trash_dir / path.name
    try:
        path.rename(target)
    except OSError as exc:
        logger.error("移動檔案到回收桶失敗：%s", exc, exc_info=True)
        raise
    manifest = {
        "trash_id": trash_id,
        "original_path": str(path),
        "original_root": str(original_root.expanduser().resolve()),
        "deleted_at": datetime.now().isoformat(timespec="seconds"),
        "restored_at": None,
        "items": [{"path": str(target)}],
    }
    manifest_path = trash_dir / "manifest.json"
    try:
        atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("寫入回收桶清單失敗：%s", exc, exc_info=True)
        raise
    log_event(
        {
            "level": "INFO",
            "event": "fs_trash_move",
            "trash_id": trash_id,
            "target": str(path),
        }
    )
    return trash_id


def trash_restore(trash_id: str, trash_root: Path) -> Path:
    logger = setup_logger("amon", trash_root.parent / "logs")
    trash_dir = trash_root / trash_id
    manifest_path = trash_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("找不到回收桶項目")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("讀取回收桶清單失敗：%s", exc, exc_info=True)
        raise
    items = manifest.get("items", [])
    if not items:
        raise ValueError("回收桶清單內容異常")
    original_path = Path(manifest.get("original_path", "")).expanduser().resolve()
    if not original_path:
        raise ValueError("回收桶清單缺少 original_path")
    source = Path(items[0]["path"])
    if original_path.exists():
        raise FileExistsError("原始路徑已存在，無法還原")
    try:
        original_path.parent.mkdir(parents=True, exist_ok=True)
        source.rename(original_path)
    except OSError as exc:
        logger.error("還原回收桶項目失敗：%s", exc, exc_info=True)
        raise
    manifest["restored_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("更新回收桶清單失敗：%s", exc, exc_info=True)
        raise
    log_event(
        {
            "level": "INFO",
            "event": "fs_trash_restore",
            "trash_id": trash_id,
            "restored_path": str(original_path),
        }
    )
    return original_path
