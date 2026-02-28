"""Tool-calling execution loop for TaskGraph2 nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolCall

from .openai_tool_client import OpenAIChatCompletionResult, OpenAIToolCall, OpenAIToolClient


class ToolLoopError(RuntimeError):
    """Raised when tool loop cannot complete successfully."""


@dataclass
class ToolTraceItem:
    tool: str
    args: dict[str, Any]
    result_text: str
    is_error: bool


class ToolLoopRunner:
    def __init__(
        self,
        *,
        client: OpenAIToolClient,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.client = client
        self.on_event = on_event

    def run(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None,
        max_turns: int,
        registry: ToolRegistry,
        model: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        caller: str = "taskgraph2",
    ) -> tuple[str, list[dict[str, Any]]]:
        conversation = [dict(item) for item in messages]
        trace: list[dict[str, Any]] = []

        for _ in range(max(max_turns, 1)):
            completion = self.client.chat(
                messages=conversation,
                tools=tools,
                tool_choice=tool_choice,
                model=model,
            )
            self._append_assistant_message(conversation, completion)
            if completion.tool_calls:
                for tool_call in completion.tool_calls:
                    trace_item = self._execute_tool_call(
                        registry=registry,
                        tool_call=tool_call,
                        conversation=conversation,
                        project_id=project_id,
                        session_id=session_id,
                        run_id=run_id,
                        node_id=node_id,
                        caller=caller,
                    )
                    trace.append(trace_item)
                continue
            if completion.content:
                return completion.content, trace
            return "", trace

        raise ToolLoopError(f"tool loop exceeded max_turns={max_turns}")

    def _append_assistant_message(
        self,
        conversation: list[dict[str, Any]],
        completion: OpenAIChatCompletionResult,
    ) -> None:
        assistant_message: dict[str, Any] = {"role": "assistant", "content": completion.content}
        if completion.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.raw_arguments if call.raw_arguments is not None else call.arguments,
                    },
                }
                for call in completion.tool_calls
            ]
        conversation.append(assistant_message)

    def _execute_tool_call(
        self,
        *,
        registry: ToolRegistry,
        tool_call: OpenAIToolCall,
        conversation: list[dict[str, Any]],
        project_id: str | None,
        session_id: str | None,
        run_id: str | None,
        node_id: str | None,
        caller: str,
    ) -> dict[str, Any]:
        self._emit(
            {
                "event": "tool_call_requested",
                "node_id": node_id,
                "tool": tool_call.name,
                "args": tool_call.arguments,
                "tool_call_id": tool_call.id,
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
                event_id=tool_call.id,
            ),
            require_approval=False,
        )
        text = result.as_text()
        if result.is_error:
            self._emit(
                {
                    "event": "tool_call_failed",
                    "node_id": node_id,
                    "tool": tool_call.name,
                    "tool_call_id": tool_call.id,
                    "error": text,
                    "meta": dict(result.meta),
                }
            )
            raise ToolLoopError(f"tool call failed: {tool_call.name}: {text or result.meta}")

        self._emit(
            {
                "event": "tool_call_executed",
                "node_id": node_id,
                "tool": tool_call.name,
                "tool_call_id": tool_call.id,
                "result": text,
                "meta": dict(result.meta),
            }
        )

        tool_message: dict[str, Any] = {
            "role": "tool",
            "name": tool_call.name,
            "content": text,
        }
        if tool_call.id:
            tool_message["tool_call_id"] = tool_call.id
        conversation.append(tool_message)

        return {
            "tool": tool_call.name,
            "args": tool_call.arguments,
            "result": text,
            "meta": dict(result.meta),
        }

    def _emit(self, payload: dict[str, Any]) -> None:
        if self.on_event is not None:
            self.on_event(payload)
