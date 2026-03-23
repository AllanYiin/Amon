from __future__ import annotations

import shutil
from pathlib import Path

from ...domain.entities import UploadAsset
from ..common import read_json, write_json
from ..migrations import bootstrap_manifest_storage


class UploadRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.uploads_dir = self.project_root / ".amon" / "uploads"
        self.originals_dir = self.uploads_dir / "originals"
        self.previews_dir = self.uploads_dir / "previews"
        self.metadata_dir = self.uploads_dir / "metadata"
        bootstrap_manifest_storage(project_root)

    def _metadata_path(self, asset_id: str) -> Path:
        return self.metadata_dir / f"{asset_id}.json"

    def create(self, asset: UploadAsset) -> UploadAsset:
        source = Path(asset.source_path)
        if source.exists():
            target = self.originals_dir / f"{asset.id}{source.suffix}"
            shutil.copy2(source, target)
            asset.source_path = str(target)
        write_json(self._metadata_path(asset.id), asset.to_dict())
        return asset

    def save(self, asset: UploadAsset) -> UploadAsset:
        write_json(self._metadata_path(asset.id), asset.to_dict())
        return asset

    def get(self, asset_id: str) -> UploadAsset:
        return UploadAsset.from_dict(read_json(self._metadata_path(asset_id), default={}))

    def list(self) -> list[UploadAsset]:
        results: list[UploadAsset] = []
        for path in sorted(self.metadata_dir.glob("*.json")):
            results.append(UploadAsset.from_dict(read_json(path, default={})))
        return results

    def save_preview(self, asset_id: str, preview_name: str, content: str) -> UploadAsset:
        preview_path = self.previews_dir / preview_name
        preview_path.write_text(content, encoding="utf-8")
        asset = self.get(asset_id)
        asset.update(preview_ref=str(preview_path), status="preview_ready")
        return self.save(asset)

    def soft_delete(self, asset_id: str) -> UploadAsset:
        asset = self.get(asset_id).soft_delete()
        return self.save(asset)

    def restore(self, asset_id: str) -> UploadAsset:
        asset = self.get(asset_id).restore()
        return self.save(asset)
