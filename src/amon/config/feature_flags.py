"""Feature flags for the staged Amon vNext rollout."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "AMON_VNEXT_MANIFEST": False,
    "AMON_VNEXT_BINDER": False,
    "AMON_VNEXT_RUNTIME": False,
    "AMON_VNEXT_UI": False,
}

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def _parse_flag(name: str, raw_value: str | None, default: bool) -> bool:
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"不合法的 feature flag 值：{name}={raw_value!r}")


@dataclass(frozen=True)
class FeatureFlags:
    manifest: bool = False
    binder: bool = False
    runtime: bool = False
    ui: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "FeatureFlags":
        source = env if env is not None else os.environ
        return cls(
            manifest=_parse_flag(
                "AMON_VNEXT_MANIFEST",
                source.get("AMON_VNEXT_MANIFEST"),
                DEFAULT_FEATURE_FLAGS["AMON_VNEXT_MANIFEST"],
            ),
            binder=_parse_flag(
                "AMON_VNEXT_BINDER",
                source.get("AMON_VNEXT_BINDER"),
                DEFAULT_FEATURE_FLAGS["AMON_VNEXT_BINDER"],
            ),
            runtime=_parse_flag(
                "AMON_VNEXT_RUNTIME",
                source.get("AMON_VNEXT_RUNTIME"),
                DEFAULT_FEATURE_FLAGS["AMON_VNEXT_RUNTIME"],
            ),
            ui=_parse_flag(
                "AMON_VNEXT_UI",
                source.get("AMON_VNEXT_UI"),
                DEFAULT_FEATURE_FLAGS["AMON_VNEXT_UI"],
            ),
        )

    def as_dict(self) -> dict[str, bool]:
        return {
            "AMON_VNEXT_MANIFEST": self.manifest,
            "AMON_VNEXT_BINDER": self.binder,
            "AMON_VNEXT_RUNTIME": self.runtime,
            "AMON_VNEXT_UI": self.ui,
        }

    def is_enabled(self, name: str) -> bool:
        try:
            return self.as_dict()[name]
        except KeyError as exc:
            raise KeyError(f"未知的 feature flag：{name}") from exc


def load_feature_flags(env: Mapping[str, str] | None = None) -> FeatureFlags:
    return FeatureFlags.from_env(env)
