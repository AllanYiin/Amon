"""Hook state storage."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from amon.fs.atomic import atomic_write_text


def _resolve_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir:
        return data_dir
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.amon").expanduser()


@dataclass
class HookStateStore:
    data_dir: Path | None = None

    def _state_path(self) -> Path:
        return _resolve_data_dir(self.data_dir) / "hooks" / "state.json"

    def load(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.exists():
            return {"hooks": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8")) or {"hooks": {}}
        except (OSError, json.JSONDecodeError):
            return {"hooks": {}}

    def save(self, state: dict[str, Any]) -> None:
        path = self._state_path()
        atomic_write_text(path, json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_hook_state(self, hook_id: str) -> dict[str, Any]:
        state = self.load()
        return state.setdefault("hooks", {}).setdefault(hook_id, {"inflight": 0, "dedupe": {}, "last_triggered_at": None})

    def update_hook_state(self, hook_id: str, payload: dict[str, Any]) -> None:
        state = self.load()
        hooks_state = state.setdefault("hooks", {})
        current = hooks_state.setdefault(hook_id, {"inflight": 0, "dedupe": {}, "last_triggered_at": None})
        current.update(payload)
        hooks_state[hook_id] = current
        self.save(state)

    def increment_inflight(self, hook_id: str) -> None:
        state = self.load()
        hooks_state = state.setdefault("hooks", {})
        current = hooks_state.setdefault(hook_id, {"inflight": 0, "dedupe": {}, "last_triggered_at": None})
        current["inflight"] = int(current.get("inflight", 0)) + 1
        hooks_state[hook_id] = current
        self.save(state)

    def decrement_inflight(self, hook_id: str) -> None:
        state = self.load()
        hooks_state = state.setdefault("hooks", {})
        current = hooks_state.setdefault(hook_id, {"inflight": 0, "dedupe": {}, "last_triggered_at": None})
        current["inflight"] = max(int(current.get("inflight", 0)) - 1, 0)
        hooks_state[hook_id] = current
        self.save(state)

    def record_trigger(self, hook_id: str, when: datetime, dedupe_key: str | None) -> None:
        state = self.load()
        hooks_state = state.setdefault("hooks", {})
        current = hooks_state.setdefault(hook_id, {"inflight": 0, "dedupe": {}, "last_triggered_at": None})
        current["last_triggered_at"] = when.isoformat()
        if dedupe_key:
            dedupe = current.setdefault("dedupe", {})
            dedupe[dedupe_key] = when.isoformat()
        hooks_state[hook_id] = current
        self.save(state)
