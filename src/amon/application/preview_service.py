"""Upload preview generation and aspect-ratio policy."""

from __future__ import annotations

import json
import mimetypes
import shutil
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from amon.domain import UploadAsset
from amon.storage import UploadRepository
from amon.storage.common import write_json


TEXT_MEDIA_TYPES = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-yaml",
    "application/yaml",
}
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".tsx", ".css", ".html"}
IMAGE_MEDIA_TYPES = {"image/png", "image/jpeg", "image/gif", "image/svg+xml", "image/webp"}


class PreviewService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.upload_repo = UploadRepository(self.project_root)

    def generate_preview(self, asset_id: str, *, max_lines: int = 40) -> UploadAsset:
        asset = self.upload_repo.get(asset_id)
        source_path = Path(asset.source_path)
        media_type = asset.media_type or _guess_media_type(source_path)

        if _is_text_preview(media_type, source_path):
            preview_path, metadata = self._write_text_preview(asset, source_path, max_lines=max_lines)
            asset.update(preview_ref=str(preview_path), status="preview_ready", metadata=metadata)
            return self.upload_repo.save(asset)

        if media_type == "image/svg+xml":
            preview_path = self._copy_preview_file(asset, source_path)
            width, height = _read_svg_dimensions(source_path)
            metadata = {
                "preview_kind": "image",
                "preview_available": True,
                "media_type": media_type,
            }
            asset.update(preview_ref=str(preview_path), width=width, height=height, status="preview_ready", metadata=metadata)
            return self.upload_repo.save(asset)

        if media_type in IMAGE_MEDIA_TYPES:
            preview_path = self._copy_preview_file(asset, source_path)
            width, height = _read_raster_dimensions(source_path)
            metadata = {
                "preview_kind": "image",
                "preview_available": True,
                "media_type": media_type,
            }
            asset.update(preview_ref=str(preview_path), width=width, height=height, status="preview_ready", metadata=metadata)
            return self.upload_repo.save(asset)

        fallback = {
            "preview_kind": "metadata_only",
            "preview_available": False,
            "media_type": media_type,
            "fallback_reason": _fallback_reason(media_type),
        }
        asset.update(status="preview_ready", metadata=fallback)
        return self.upload_repo.save(asset)

    def build_preview_payload(self, asset_id: str) -> dict[str, Any]:
        asset = self.upload_repo.get(asset_id)
        payload = asset.to_dict()
        payload["preview"] = dict(asset.metadata)
        return payload

    def _write_text_preview(self, asset: UploadAsset, source_path: Path, *, max_lines: int) -> tuple[Path, dict[str, Any]]:
        content = source_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        excerpt = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            excerpt = f"{excerpt}\n…"
        preview_path = self.upload_repo.previews_dir / f"{asset.id}.preview.txt"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(excerpt, encoding="utf-8")
        metadata = {
            "preview_kind": "inline_text",
            "preview_available": True,
            "line_count": len(lines),
            "truncated": len(lines) > max_lines,
            "preview_manifest": str(preview_path.with_suffix(".json")),
        }
        write_json(
            preview_path.with_suffix(".json"),
            {
                "asset_id": asset.id,
                "preview_path": str(preview_path),
                "line_count": len(lines),
                "truncated": len(lines) > max_lines,
            },
        )
        return preview_path, metadata

    def _copy_preview_file(self, asset: UploadAsset, source_path: Path) -> Path:
        target = self.upload_repo.previews_dir / f"{asset.id}{source_path.suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        return target


def calculate_aspect_ratio_fit(
    width: int,
    height: int,
    *,
    mode: str,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
) -> dict[str, float]:
    if width <= 0 or height <= 0:
        raise ValueError("原始尺寸必須大於 0")

    normalized_mode = str(mode).strip().lower()
    if normalized_mode == "fit_width":
        if not viewport_width:
            raise ValueError("fit_width 需要 viewport_width")
        scale = viewport_width / width
    elif normalized_mode == "fit_height":
        if not viewport_height:
            raise ValueError("fit_height 需要 viewport_height")
        scale = viewport_height / height
    elif normalized_mode.endswith("%"):
        scale = float(normalized_mode[:-1]) / 100.0
    else:
        raise ValueError(f"不支援的 zoom mode：{mode}")

    scaled_width = width * scale
    scaled_height = height * scale
    return {
        "width": round(scaled_width, 4),
        "height": round(scaled_height, 4),
        "scale": round(scale, 6),
        "aspect_ratio": round(width / height, 6),
    }


def _guess_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _is_text_preview(media_type: str, path: Path) -> bool:
    return media_type.startswith("text/") or media_type in TEXT_MEDIA_TYPES or path.suffix.lower() in TEXT_SUFFIXES


def _fallback_reason(media_type: str) -> str:
    if media_type == "application/pdf":
        return "pdf 首頁預覽尚未接入，先保留 metadata fallback"
    return "目前格式僅提供 metadata preview"


def _read_svg_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None, None
    width = _parse_dimension(root.attrib.get("width"))
    height = _parse_dimension(root.attrib.get("height"))
    if width is not None and height is not None:
        return width, height
    view_box = root.attrib.get("viewBox")
    if isinstance(view_box, str):
        parts = [item for item in view_box.replace(",", " ").split() if item]
        if len(parts) == 4:
            try:
                return int(float(parts[2])), int(float(parts[3]))
            except ValueError:
                return None, None
    return width, height


def _parse_dimension(raw: str | None) -> int | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    if not digits:
        return None
    try:
        return int(float(digits))
    except ValueError:
        return None


def _read_raster_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                return struct.unpack(">II", header[16:24])
            if header[:6] in {b"GIF87a", b"GIF89a"} and len(header) >= 10:
                return struct.unpack("<HH", header[6:10])
            if header.startswith(b"\xff\xd8"):
                handle.seek(0)
                return _read_jpeg_dimensions(handle)
    except OSError:
        return None, None
    return None, None


def _read_jpeg_dimensions(handle) -> tuple[int | None, int | None]:
    while True:
        marker_prefix = handle.read(1)
        if not marker_prefix:
            return None, None
        if marker_prefix != b"\xff":
            continue
        marker = handle.read(1)
        while marker == b"\xff":
            marker = handle.read(1)
        if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
            segment_length = struct.unpack(">H", handle.read(2))[0]
            _ = handle.read(1)
            height, width = struct.unpack(">HH", handle.read(4))
            return width, height
        if marker in {b"\xd8", b"\xd9"}:
            continue
        segment_length_bytes = handle.read(2)
        if len(segment_length_bytes) != 2:
            return None, None
        segment_length = struct.unpack(">H", segment_length_bytes)[0]
        handle.seek(segment_length - 2, 1)

