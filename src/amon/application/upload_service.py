"""Upload orchestration for Stage 5."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from amon.domain import UploadAsset
from amon.storage import UploadRepository

from .preview_service import PreviewService


class UploadService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.upload_repo = UploadRepository(self.project_root)
        self.preview_service = PreviewService(self.project_root)

    def create_upload(
        self,
        source_path: Path,
        *,
        asset_id: str | None = None,
        media_type: str | None = None,
        notes: str | None = None,
    ) -> UploadAsset:
        source = Path(source_path)
        guessed_media_type = media_type or mimetypes.guess_type(str(source))[0] or "application/octet-stream"
        asset = UploadAsset.create(
            asset_id=asset_id or f"asset-{uuid.uuid4().hex}",
            source_path=str(source),
            media_type=guessed_media_type,
            size_bytes=source.stat().st_size,
            notes=notes,
        )
        self.upload_repo.create(asset)
        return self.preview_service.generate_preview(asset.id)

