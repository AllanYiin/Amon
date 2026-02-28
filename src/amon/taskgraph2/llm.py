"""LLM abstraction helpers for TaskGraphRuntime 2.0."""

from __future__ import annotations

from typing import Iterable, Protocol

from amon.config import ConfigLoader
from amon.models import build_provider


class TaskGraphLLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


def build_default_llm_client(
    *,
    provider_cfg: dict[str, str | int | list[str]] | None = None,
    model: str | None = None,
    config_loader: ConfigLoader | None = None,
) -> TaskGraphLLMClient:
    """Build default LLM client for TaskGraph runtime.

    Caller may inject `provider_cfg` directly for deterministic/offline tests.
    """

    if provider_cfg is None:
        loader = config_loader or ConfigLoader()
        resolution = loader.resolve()
        effective = resolution.effective
        provider_name = str((effective.get("amon") or {}).get("provider") or "")
        providers = effective.get("providers") if isinstance(effective.get("providers"), dict) else {}
        selected = providers.get(provider_name) if isinstance(providers, dict) else None
        if not isinstance(selected, dict):
            raise ValueError(f"找不到 provider 設定：{provider_name}")
        provider_cfg = dict(selected)
    return build_provider(provider_cfg, model=model)
