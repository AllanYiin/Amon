"""OpenAI-compatible non-stream chat completions client for TaskGraph2 tool loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request

from .schema import TaskNodeTool


@dataclass(frozen=True)
class OpenAIToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class OpenAIChatCompletionResult:
    content: str
    tool_calls: list[OpenAIToolCall]


class OpenAIToolClientError(RuntimeError):
    """Raised when OpenAI-compatible tool completion request/response is invalid."""


class OpenAIToolClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_s: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s

    def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[TaskNodeTool],
        tool_choice: str | dict[str, Any] | None,
        stream: bool = False,
    ) -> OpenAIChatCompletionResult:
        if stream:
            raise OpenAIToolClientError("openai tool client currently supports stream=false only")

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = [_tool_to_openai_payload(item) for item in tools]
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        response = self._post_json("/chat/completions", payload)
        message = _extract_choice_message(response)
        content = str(message.get("content") or "")
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls is None:
            return OpenAIChatCompletionResult(content=content, tool_calls=[])
        if not isinstance(raw_tool_calls, list):
            raise OpenAIToolClientError("choices[0].message.tool_calls must be a list")

        parsed_calls: list[OpenAIToolCall] = []
        for index, item in enumerate(raw_tool_calls):
            if not isinstance(item, dict):
                raise OpenAIToolClientError(f"choices[0].message.tool_calls[{index}] must be an object")
            function_payload = item.get("function")
            if not isinstance(function_payload, dict):
                raise OpenAIToolClientError(f"tool_calls[{index}].function must be an object")
            name = str(function_payload.get("name") or "").strip()
            if not name:
                raise OpenAIToolClientError(f"tool_calls[{index}].function.name is required")
            args = _parse_arguments(function_payload.get("arguments"), index=index)
            parsed_calls.append(
                OpenAIToolCall(
                    id=str(item.get("id") or f"call_{index}"),
                    name=name,
                    arguments=args,
                )
            )

        return OpenAIChatCompletionResult(content=content, tool_calls=parsed_calls)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self._base_url}{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        with request.urlopen(req, timeout=self._timeout_s) as response:
            raw = response.read().decode("utf-8")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OpenAIToolClientError(f"chat completions response is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise OpenAIToolClientError("chat completions response root must be an object")
        return parsed


def _tool_to_openai_payload(tool: TaskNodeTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.when_to_use or "",
            "parameters": tool.args_schema_hint or {"type": "object", "properties": {}},
        },
    }


def _extract_choice_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAIToolClientError("chat completions response must include non-empty choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise OpenAIToolClientError("choices[0] must be an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise OpenAIToolClientError("choices[0].message must be an object")
    return message


def _parse_arguments(raw_arguments: Any, *, index: int) -> dict[str, Any]:
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return dict(raw_arguments)
    if not isinstance(raw_arguments, str):
        raise OpenAIToolClientError(
            f"tool_calls[{index}].function.arguments must be a JSON string/object"
        )
    try:
        decoded = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise OpenAIToolClientError(
            f"tool_calls[{index}].function.arguments JSON parse failed: {exc}"
        ) from exc
    if not isinstance(decoded, dict):
        raise OpenAIToolClientError(f"tool_calls[{index}].function.arguments must decode to object")
    return decoded
