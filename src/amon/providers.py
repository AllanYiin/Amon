"""Provider abstraction for Amon."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class ProviderResponse:
    text: str
    usage: dict[str, Any] | None
    model: str
    raw: dict[str, Any] | None = None


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key_env: str, model: str, timeout_s: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.model = model
        self.timeout_s = timeout_s

    def _get_api_key(self) -> str:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderError(f"未設定 API Key（請設定環境變數 {self.api_key_env}）")
        return api_key

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterable[str]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
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
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:  # noqa: S310
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

    def chat(self, messages: list[dict[str, str]]) -> ProviderResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
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
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:  # noqa: S310
                try:
                    data = json.loads(response.read().decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise ProviderError("解析模型回應失敗") from exc
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"模型請求失敗：{exc}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"模型連線失敗：{exc}") from exc
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ProviderResponse(text=text, usage=data.get("usage"), model=self.model, raw=data)
