"""Shared primitives for manifest v1 domain entities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class EntityTimestamps:
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()


@dataclass
class VersionedEntity(EntityTimestamps):
    id: str = ""
    version: int = 1
    status: str = "draft"

    def clone_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload["version"] = int(payload.get("version") or 1) + 1
        payload["status"] = "draft"
        payload["created_at"] = utc_now_iso()
        payload["updated_at"] = payload["created_at"]
        return deepcopy(payload)

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def copy_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def copy_list(value: list[Any] | None) -> list[Any]:
    return deepcopy(value) if isinstance(value, list) else []
