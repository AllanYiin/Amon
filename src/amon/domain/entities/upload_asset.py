from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import EntityTimestamps, copy_list, copy_mapping, utc_now_iso

UPLOAD_STATUSES = {"uploaded", "preview_ready", "linked", "deleted"}


@dataclass
class UploadAsset(EntityTimestamps):
    id: str = ""
    source_path: str = ""
    media_type: str = "application/octet-stream"
    size_bytes: int = 0
    preview_ref: str | None = None
    width: int | None = None
    height: int | None = None
    page_count: int | None = None
    duration_s: float | None = None
    linked_to: list[str] = field(default_factory=list)
    status: str = "uploaded"
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None

    @classmethod
    def create(
        cls,
        *,
        asset_id: str,
        source_path: str,
        media_type: str,
        size_bytes: int,
        preview_ref: str | None = None,
        width: int | None = None,
        height: int | None = None,
        page_count: int | None = None,
        duration_s: float | None = None,
        linked_to: list[str] | None = None,
        status: str = "uploaded",
        metadata: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> "UploadAsset":
        return cls(
            id=asset_id,
            source_path=source_path,
            media_type=media_type,
            size_bytes=size_bytes,
            preview_ref=preview_ref,
            width=width,
            height=height,
            page_count=page_count,
            duration_s=duration_s,
            linked_to=copy_list(linked_to),
            status=status,
            metadata=copy_mapping(metadata),
            notes=notes,
        )

    def update(self, **changes: Any) -> "UploadAsset":
        for key in [
            "source_path",
            "media_type",
            "size_bytes",
            "preview_ref",
            "width",
            "height",
            "page_count",
            "duration_s",
            "status",
            "notes",
        ]:
            if key in changes and changes[key] is not None:
                setattr(self, key, changes[key])
        if "linked_to" in changes and changes["linked_to"] is not None:
            self.linked_to = copy_list(changes["linked_to"])
        if "metadata" in changes and changes["metadata"] is not None:
            self.metadata = copy_mapping(changes["metadata"])
        if self.status not in UPLOAD_STATUSES:
            raise ValueError(f"不合法的 upload status：{self.status}")
        self.touch()
        return self

    def soft_delete(self) -> "UploadAsset":
        self.status = "deleted"
        self.touch()
        return self

    def restore(self) -> "UploadAsset":
        self.status = "uploaded"
        self.touch()
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "preview_ref": self.preview_ref,
            "width": self.width,
            "height": self.height,
            "page_count": self.page_count,
            "duration_s": self.duration_s,
            "linked_to": copy_list(self.linked_to),
            "status": self.status,
            "metadata": copy_mapping(self.metadata),
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UploadAsset":
        created_at = str(payload.get("created_at") or payload.get("updated_at") or utc_now_iso())
        entity = cls(
            id=str(payload.get("id") or ""),
            source_path=str(payload.get("source_path") or ""),
            media_type=str(payload.get("media_type") or "application/octet-stream"),
            size_bytes=int(payload.get("size_bytes") or 0),
            preview_ref=payload.get("preview_ref"),
            width=payload.get("width"),
            height=payload.get("height"),
            page_count=payload.get("page_count"),
            duration_s=payload.get("duration_s"),
            linked_to=copy_list(payload.get("linked_to")),
            status=str(payload.get("status") or "uploaded"),
            metadata=copy_mapping(payload.get("metadata")),
            notes=payload.get("notes"),
            created_at=created_at,
            updated_at=str(payload.get("updated_at") or created_at),
        )
        if entity.status not in UPLOAD_STATUSES:
            raise ValueError(f"不合法的 upload status：{entity.status}")
        return entity
