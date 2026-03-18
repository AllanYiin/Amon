"""Model providers for Amon."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


_REASONING_CHUNK_PREFIX = "__AMON_REASONING__::"
_STREAM_EVENT_PREFIX = "__AMON_EVENT__::"


def encode_reasoning_chunk(text: str) -> str:
    return f"{_REASONING_CHUNK_PREFIX}{text}"


def decode_reasoning_chunk(token: str) -> tuple[bool, str]:
    if isinstance(token, str) and token.startswith(_REASONING_CHUNK_PREFIX):
        return True, token[len(_REASONING_CHUNK_PREFIX) :]
    return False, token


def encode_stream_event(event_type: str, payload: dict[str, object] | None = None) -> str:
    data = dict(payload or {})
    data["event"] = str(event_type or "").strip() or "notice"
    return f"{_STREAM_EVENT_PREFIX}{json.dumps(data, ensure_ascii=False)}"


def decode_stream_event(token: str) -> tuple[bool, dict[str, object]]:
    if not isinstance(token, str) or not token.startswith(_STREAM_EVENT_PREFIX):
        return False, {}
    raw_payload = token[len(_STREAM_EVENT_PREFIX) :]
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return False, {}
    if not isinstance(payload, dict):
        return False, {}
    payload["event"] = str(payload.get("event") or "").strip() or "notice"
    return True, payload


def _extract_reasoning_text(delta: dict[str, object]) -> str:
    reasoning_fields = [delta.get("reasoning"), delta.get("reasoning_content"), delta.get("summary")]
    for raw in reasoning_fields:
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, dict):
            summary = raw.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()
    return ""


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
        payload = {"model": chosen_model, "messages": messages, "stream": True}
        try:
            for chunk in self._iter_streaming_chunks(payload):
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if not isinstance(delta, dict):
                    continue
                reasoning_text = _extract_reasoning_text(delta)
                if reasoning_text:
                    yield encode_reasoning_chunk(reasoning_text)
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield content
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"模型請求失敗：{exc}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"模型連線失敗：{exc}") from exc

    def generate_text(self, messages: list[dict[str, Any]], model: str | None = None) -> str:
        chosen_model = model or self._config.default_model
        payload = {"model": chosen_model, "messages": messages, "stream": False}
        response = self._request_json(payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("模型未回傳 choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderError("模型回傳 message 格式錯誤")
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
            return "".join(parts)
        return ""

    def run_tool_conversation(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None,
        tools: list[dict[str, Any]],
        execute_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
        stream_handler: Callable[[str], None] | None = None,
        max_rounds: int = 8,
        max_auto_continue: int = 3,
        continue_prompt: str = "繼續，請接著前文輸出，不要重複已完成內容。",
    ) -> dict[str, Any]:
        if not tools:
            raise ProviderError("缺少 tools 定義")

        working_messages = [dict(item) for item in messages]
        final_text_parts: list[str] = []
        auto_continue_count = 0
        last_finish_reason: str | None = None

        for _ in range(max_rounds):
            assistant_chunks: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            payload = {
                "model": model or self._config.default_model,
                "messages": working_messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": True,
            }

            for chunk in self._iter_streaming_chunks(payload):
                choice = chunk.get("choices", [{}])[0]
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta", {})
                if not isinstance(delta, dict):
                    continue
                finish_reason = choice.get("finish_reason")
                if isinstance(finish_reason, str) and finish_reason:
                    last_finish_reason = finish_reason
                reasoning_text = _extract_reasoning_text(delta)
                if reasoning_text and callable(stream_handler):
                    stream_handler(encode_reasoning_chunk(reasoning_text))
                content = delta.get("content")
                if isinstance(content, str) and content:
                    assistant_chunks.append(content)
                    final_text_parts.append(content)
                    if callable(stream_handler):
                        stream_handler(content)
                delta_tool_calls = delta.get("tool_calls")
                if isinstance(delta_tool_calls, list):
                    for item in delta_tool_calls:
                        if isinstance(item, dict):
                            _merge_stream_tool_call(tool_calls, item)

            assistant_text = "".join(assistant_chunks)
            if assistant_text or tool_calls:
                assistant_message: dict[str, Any] = {"role": "assistant", "content": assistant_text}
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls
                working_messages.append(assistant_message)

            if tool_calls:
                auto_continue_count = 0
                for tool_call in tool_calls:
                    function = tool_call.get("function") if isinstance(tool_call, dict) else None
                    function_name = str((function or {}).get("name") or "").strip()
                    argument_text = str((function or {}).get("arguments") or "")
                    tool_args = _decode_tool_arguments(argument_text)
                    tool_result = execute_tool(function_name, tool_args)
                    tool_text = _tool_result_to_message_text(tool_result)
                    working_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": str(tool_call.get("id") or ""),
                            "name": function_name,
                            "content": tool_text,
                        }
                    )
                continue

            if last_finish_reason == "length" and auto_continue_count < max_auto_continue:
                auto_continue_count += 1
                working_messages.append({"role": "user", "content": continue_prompt})
                continue

            return {
                "text": "".join(final_text_parts),
                "messages": working_messages,
                "finish_reason": last_finish_reason,
                "auto_continue_count": auto_continue_count,
            }

        raise ProviderError("tool conversation exceeded max rounds")

    def _request_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
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
        with urllib.request.urlopen(request, timeout=self._config.timeout_s) as response:  # noqa: S310
            raw_body = response.read().decode("utf-8")
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ProviderError("解析模型回應失敗") from exc
        if not isinstance(parsed, dict):
            raise ProviderError("模型回應格式錯誤")
        return parsed

    def _iter_streaming_chunks(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
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
                if isinstance(chunk, dict):
                    yield chunk


def _merge_stream_tool_call(tool_calls: list[dict[str, Any]], delta: dict[str, Any]) -> None:
    index = delta.get("index")
    if not isinstance(index, int) or index < 0:
        index = len(tool_calls)
    while len(tool_calls) <= index:
        tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
    target = tool_calls[index]
    tool_id = delta.get("id")
    if isinstance(tool_id, str) and tool_id:
        target["id"] = tool_id
    tool_type = delta.get("type")
    if isinstance(tool_type, str) and tool_type:
        target["type"] = tool_type
    function = delta.get("function")
    if not isinstance(function, dict):
        return
    target_function = target.setdefault("function", {})
    function_name = function.get("name")
    if isinstance(function_name, str) and function_name:
        target_function["name"] = function_name
    arguments = function.get("arguments")
    if isinstance(arguments, str) and arguments:
        target_function["arguments"] = str(target_function.get("arguments") or "") + arguments


def _decode_tool_arguments(argument_text: str) -> dict[str, Any]:
    cleaned = str(argument_text or "").strip()
    if not cleaned:
        return {}
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"_raw": cleaned}
    if isinstance(parsed, dict):
        return parsed
    return {"_value": parsed}


def _tool_result_to_message_text(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return str(result)
    content_text = result.get("content_text")
    if isinstance(content_text, str) and content_text.strip():
        return content_text
    text = result.get("text")
    if isinstance(text, str) and text.strip():
        return text
    try:
        return json.dumps(result, ensure_ascii=False)
    except TypeError:
        return str(result)


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
