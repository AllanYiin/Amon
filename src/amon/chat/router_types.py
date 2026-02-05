"""Shared router types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RouterResult:
    type: str
    confidence: float = 0.0
    api: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    requires_confirm: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "confidence": self.confidence,
            "api": self.api,
            "args": self.args,
            "requires_confirm": self.requires_confirm,
            "reason": self.reason,
        }
