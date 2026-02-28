"""OpenAI-compatible non-stream chat client for tool calling."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from amon.config import ConfigLoader


class OpenAIToolClientError(RuntimeError):
    """Raised when OpenAI-compatible request/response handling fails."""


@dataclass
class OpenAIToolCall:
    """Parsed tool call payload from an assistant response."""

    id: str | None
    name: str
    arguments: dict[str, Any]
    raw_arguments: str | dict[str, Any] | None


@dataclass
class OpenAIChatCompletionResult:
    """Normalized OpenAI-compatible chat.completions response."""

    content: str
    tool_calls: list[OpenAIToolCall]
    raw: dict[str, Any]


class OpenAIToolClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key_env: str,
        model: str,
        timeout_s: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.model = model
        self.timeout_s = max(timeout_s, 1)

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        model: str | None = None,
    ) -> OpenAIChatCompletionResult:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._get_api_key()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:  # noqa: S310
                raw = json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise OpenAIToolClientError("OpenAI tool client: invalid JSON response") from exc
        except urllib.error.HTTPError as exc:
            raise OpenAIToolClientError(f"OpenAI tool client HTTP error: {exc}") from exc
        except urllib.error.URLError as exc:
            raise OpenAIToolClientError(f"OpenAI tool client connection error: {exc}") from exc

        message = _extract_message(raw)
        tool_calls = _parse_tool_calls(message.get("tool_calls"))
        content = str(message.get("content") or "")
        return OpenAIChatCompletionResult(content=content, tool_calls=tool_calls, raw=raw)

    def _get_api_key(self) -> str:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise OpenAIToolClientError(f"missing API key in env var: {self.api_key_env}")
        return api_key


def build_default_openai_tool_client(
    *,
    model: str | None = None,
    provider_cfg: dict[str, Any] | None = None,
    config_loader: ConfigLoader | None = None,
) -> OpenAIToolClient:
    if provider_cfg is None:
        loader = config_loader or ConfigLoader()
        resolution = loader.resolve()
        effective = resolution.effective
        provider_name = str((effective.get("amon") or {}).get("provider") or "")
        providers = effective.get("providers") if isinstance(effective.get("providers"), dict) else {}
        selected = providers.get(provider_name) if isinstance(providers, dict) else None
        if not isinstance(selected, dict):
            raise OpenAIToolClientError(f"provider config not found: {provider_name}")
        provider_cfg = dict(selected)

    base_url = str(provider_cfg.get("base_url") or "").strip()
    api_key_env = str(provider_cfg.get("api_key_env") or "").strip()
    final_model = str(model or provider_cfg.get("model") or "").strip()
    timeout_s = int(provider_cfg.get("timeout_s") or 60)

    if not base_url:
        raise OpenAIToolClientError("provider base_url is required")
    if not api_key_env:
        raise OpenAIToolClientError("provider api_key_env is required")
    if not final_model:
        raise OpenAIToolClientError("provider model is required")

    return OpenAIToolClient(base_url=base_url, api_key_env=api_key_env, model=final_model, timeout_s=timeout_s)


def _extract_message(raw: dict[str, Any]) -> dict[str, Any]:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAIToolClientError("OpenAI tool client: missing choices in response")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message")
    if not isinstance(message, dict):
        raise OpenAIToolClientError("OpenAI tool client: missing choices[0].message")
    return message


def _parse_tool_calls(raw_tool_calls: Any) -> list[OpenAIToolCall]:
    if raw_tool_calls is None:
        return []
    if not isinstance(raw_tool_calls, list):
        raise OpenAIToolClientError("OpenAI tool client: message.tool_calls must be a list")

    calls: list[OpenAIToolCall] = []
    for index, item in enumerate(raw_tool_calls):
        if not isinstance(item, dict):
            raise OpenAIToolClientError(f"OpenAI tool client: tool_call[{index}] must be an object")
        function_payload = item.get("function")
        if not isinstance(function_payload, dict):
            raise OpenAIToolClientError(f"OpenAI tool client: tool_call[{index}].function missing")
        name = str(function_payload.get("name") or "").strip()
        if not name:
            raise OpenAIToolClientError(f"OpenAI tool client: tool_call[{index}].function.name missing")

        raw_arguments = function_payload.get("arguments")
        arguments = _parse_arguments(raw_arguments, tool_name=name)
        calls.append(
            OpenAIToolCall(
                id=str(item.get("id")) if item.get("id") is not None else None,
                name=name,
                arguments=arguments,
                raw_arguments=raw_arguments,
            )
        )
    return calls


def _parse_arguments(raw_arguments: Any, *, tool_name: str) -> dict[str, Any]:
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return dict(raw_arguments)
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise OpenAIToolClientError(
                f"OpenAI tool client: failed to parse arguments for tool '{tool_name}': {exc.msg}"
            ) from exc
        if not isinstance(parsed, dict):
            raise OpenAIToolClientError(
                f"OpenAI tool client: arguments for tool '{tool_name}' must decode to an object"
            )
        return parsed
    raise OpenAIToolClientError(
        f"OpenAI tool client: unsupported argument type for tool '{tool_name}': {type(raw_arguments).__name__}"
    )
