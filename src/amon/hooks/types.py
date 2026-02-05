"""Hook data models for Amon."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HookFilter:
    path_glob: str | None = None
    min_size: int | None = None
    mime: str | None = None
    ignore_actors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HookAction:
    type: str
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HookPolicy:
    require_confirm: bool = False


@dataclass(frozen=True)
class Hook:
    hook_id: str
    event_types: list[str]
    filters: HookFilter
    action: HookAction
    policy: HookPolicy
    enabled: bool = True
    dedupe_key: str | None = None
    cooldown_seconds: int | None = None
    max_concurrency: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
