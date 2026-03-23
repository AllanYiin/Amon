"""Persistent dedupe records for trigger-originated run requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.storage.common import read_json, write_json


def _normalize_now(now: datetime | None) -> datetime:
    if now is not None:
        return now.astimezone() if now.tzinfo else now
    return datetime.now().astimezone()


@dataclass
class TriggerDedupeStore:
    data_dir: Path

    @property
    def path(self) -> Path:
        return self.data_dir / "triggers" / "dedupe.json"

    def load(self) -> dict[str, Any]:
        return read_json(self.path, default={"triggers": {}})

    def _save(self, payload: dict[str, Any]) -> None:
        write_json(self.path, payload)

    def is_duplicate(
        self,
        trigger_kind: str,
        trigger_id: str,
        dedupe_key: str,
        *,
        cooldown_seconds: int | None = None,
        now: datetime | None = None,
    ) -> bool:
        state = self.load()
        trigger_state = (
            state.setdefault("triggers", {})
            .setdefault(str(trigger_kind), {})
            .setdefault(str(trigger_id), {})
        )
        raw_value = trigger_state.get(str(dedupe_key))
        if not raw_value:
            return False
        try:
            last_seen = datetime.fromisoformat(str(raw_value))
        except ValueError:
            return False
        current_time = _normalize_now(now)
        if cooldown_seconds is None or cooldown_seconds <= 0:
            return True
        return (current_time - last_seen).total_seconds() < cooldown_seconds

    def record(
        self,
        trigger_kind: str,
        trigger_id: str,
        dedupe_key: str,
        *,
        now: datetime | None = None,
    ) -> None:
        state = self.load()
        trigger_state = (
            state.setdefault("triggers", {})
            .setdefault(str(trigger_kind), {})
            .setdefault(str(trigger_id), {})
        )
        trigger_state[str(dedupe_key)] = _normalize_now(now).isoformat(timespec="seconds")
        self._save(state)
