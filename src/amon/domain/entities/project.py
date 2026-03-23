from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import EntityTimestamps, copy_mapping, utc_now_iso

PROJECT_STATUSES = {"active", "trashed", "archived"}


@dataclass
class Project(EntityTimestamps):
    id: str = ""
    name: str = ""
    root_path: str = ""
    mode: str = "managed"
    status: str = "active"
    defaults: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    last_opened_at: str | None = None
    archived_at: str | None = None

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        name: str,
        root_path: str,
        mode: str = "managed",
        defaults: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> "Project":
        return cls(
            id=project_id,
            name=name,
            root_path=root_path,
            mode=mode,
            status="active",
            defaults=copy_mapping(defaults),
            description=description,
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        defaults: dict[str, Any] | None = None,
        last_opened_at: str | None = None,
        mode: str | None = None,
        status: str | None = None,
    ) -> "Project":
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if defaults is not None:
            self.defaults = copy_mapping(defaults)
        if last_opened_at is not None:
            self.last_opened_at = last_opened_at
        if mode is not None:
            self.mode = mode
        if status is not None:
            if status not in PROJECT_STATUSES:
                raise ValueError(f"不合法的 project status：{status}")
            self.status = status
        self.touch()
        return self

    def soft_delete(self) -> "Project":
        self.status = "trashed"
        self.touch()
        return self

    def restore(self) -> "Project":
        self.status = "active"
        self.touch()
        return self

    def archive(self) -> "Project":
        self.status = "archived"
        self.archived_at = utc_now_iso()
        self.touch()
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "root_path": self.root_path,
            "mode": self.mode,
            "status": self.status,
            "defaults": copy_mapping(self.defaults),
            "description": self.description,
            "last_opened_at": self.last_opened_at,
            "archived_at": self.archived_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Project":
        project = cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            root_path=str(payload.get("root_path") or ""),
            mode=str(payload.get("mode") or "managed"),
            status=str(payload.get("status") or "active"),
            defaults=copy_mapping(payload.get("defaults")),
            description=payload.get("description"),
            last_opened_at=payload.get("last_opened_at"),
            archived_at=payload.get("archived_at"),
            created_at=str(payload.get("created_at") or utc_now_iso()),
            updated_at=str(payload.get("updated_at") or utc_now_iso()),
        )
        if project.status not in PROJECT_STATUSES:
            raise ValueError(f"不合法的 project status：{project.status}")
        return project
