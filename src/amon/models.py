"""Model providers for Amon."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Protocol


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


@dataclass
class OpenAIProviderConfig:
    base_url: str
    api_key_env: str
    default_model: str
    timeout_s: int = 60


class OpenAICompatibleProvider:
    def __init__(self, config: OpenAIProviderConfig) -> None:
        self._config = config

    def _get_api_key(self) -> str:
        api_key = os.getenv(self._config.api_key_env)
        if not api_key:
            raise ProviderError(f"未設定 API Key（請設定環境變數 {self._config.api_key_env}）")
        return api_key

    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        chosen_model = model or self._config.default_model
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": chosen_model,
            "messages": messages,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_s) as response:  # noqa: S310
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ProviderError("解析模型串流資料失敗") from exc
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"模型請求失敗：{exc}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"模型連線失敗：{exc}") from exc


def build_provider(provider_cfg: dict[str, str | int | list[str]], model: str | None = None) -> Provider:
    provider_type = provider_cfg.get("type")
    if provider_type == "mock":
        provider_cfg = {
            "type": "openai_compatible",
            "base_url": provider_cfg.get("base_url") or "https://api.openai.com/v1",
            "api_key_env": provider_cfg.get("api_key_env") or "OPENAI_API_KEY",
            "default_model": provider_cfg.get("default_model") or provider_cfg.get("model") or "gpt-4o-mini",
            "model": provider_cfg.get("model") or provider_cfg.get("default_model") or "gpt-4o-mini",
            "timeout_s": provider_cfg.get("timeout_s", 60),
        }
        provider_type = "openai_compatible"
    if provider_type == "openai_compatible":
        config = OpenAIProviderConfig(
            base_url=str(provider_cfg.get("base_url", "")),
            api_key_env=str(provider_cfg.get("api_key_env", "")),
            default_model=str(model or provider_cfg.get("default_model") or provider_cfg.get("model") or ""),
            timeout_s=int(provider_cfg.get("timeout_s", 60)),
        )
        return OpenAICompatibleProvider(config)
    raise ValueError(f"不支援的 provider 類型：{provider_type}")
