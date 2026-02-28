"""Tool calling loop for TaskGraph2 nodes with OpenAI-compatible models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from amon.tooling.types import ToolCall

from .openai_tool_client import OpenAIChatCompletionResult, OpenAIToolCall, OpenAIToolClient
from .schema import TaskNodeTool


class ToolLoopError(RuntimeError):
    """Raised when the tool loop cannot reach a terminal assistant answer."""


@dataclass(frozen=True)
class ToolLoopResult:
    final_text: str
    trace: list[dict[str, Any]]


class ToolLoopRunner:
    def __init__(
        self,
        *,
        client: OpenAIToolClient,
        model: str,
        emit_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._emit_event = emit_event

    def run(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[TaskNodeTool],
        tool_choice: str | dict[str, Any] | None,
        max_turns: int,
        registry,  # ToolRegistry
        caller: str = "taskgraph2",
        project_id: str | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        session_id: str | None = None,
    ) -> ToolLoopResult:
        transcript = [dict(item) for item in messages]
        trace: list[dict[str, Any]] = []

        for turn in range(max_turns):
            completion = self._client.chat_completions(
                model=self._model,
                messages=transcript,
                tools=tools,
                tool_choice=tool_choice,
                stream=False,
            )
            trace.append(_trace_from_completion(turn=turn, completion=completion))

            if completion.tool_calls:
                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": completion.content,
                    "tool_calls": [_raw_tool_call_payload(item) for item in completion.tool_calls],
                }
                transcript.append(assistant_message)

                for tool_call in completion.tool_calls:
                    self._emit(
                        {
                            "event": "tool_call_requested",
                            "node_id": node_id,
                            "tool": tool_call.name,
                            "tool_call_id": tool_call.id,
                            "args": tool_call.arguments,
                        }
                    )
                    result = registry.call(
                        ToolCall(
                            tool=tool_call.name,
                            args=tool_call.arguments,
                            caller=caller,
                            project_id=project_id,
                            session_id=session_id,
                            run_id=run_id,
                            node_id=node_id,
                        ),
                        require_approval=False,
                    )
                    if result.is_error:
                        detail = result.as_text() or str(result.meta.get("status") or "tool call failed")
                        self._emit(
                            {
                                "event": "tool_call_failed",
                                "node_id": node_id,
                                "tool": tool_call.name,
                                "tool_call_id": tool_call.id,
                                "error": detail,
                                "meta": dict(result.meta or {}),
                            }
                        )
                        raise ToolLoopError(f"tool call failed: {tool_call.name}: {detail}")

                    tool_text = result.as_text()
                    self._emit(
                        {
                            "event": "tool_call_executed",
                            "node_id": node_id,
                            "tool": tool_call.name,
                            "tool_call_id": tool_call.id,
                            "result": tool_text,
                            "meta": dict(result.meta or {}),
                        }
                    )
                    transcript.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": tool_text,
                            "structured": result.content,
                        }
                    )
                continue

            if completion.content:
                return ToolLoopResult(final_text=completion.content, trace=trace)

            raise ToolLoopError("assistant response has neither content nor tool_calls")

        raise ToolLoopError(f"tool loop exceeded max_turns={max_turns}")

    def _emit(self, payload: dict[str, Any]) -> None:
        if self._emit_event is None:
            return
        self._emit_event(payload)


def _trace_from_completion(*, turn: int, completion: OpenAIChatCompletionResult) -> dict[str, Any]:
    return {
        "turn": turn,
        "content": completion.content,
        "tool_calls": [
            {"id": item.id, "name": item.name, "arguments": json.dumps(item.arguments, ensure_ascii=False)}
            for item in completion.tool_calls
        ],
    }


def _raw_tool_call_payload(tool_call: OpenAIToolCall) -> dict[str, Any]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
        },
    }
