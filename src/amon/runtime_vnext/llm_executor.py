"""LLM executor with streaming chunk relay for runtime vNext."""

from __future__ import annotations

from string import Template
from typing import Any
from datetime import datetime, timezone

from amon.domain import ToolPolicy
from amon.artifacts.store import ingest_artifacts
from amon.models import decode_reasoning_chunk, decode_stream_event

from .runner import RuntimeExecutionContext


class LLMExecutor:
    def __init__(self, policy_engine) -> None:
        self.policy_engine = policy_engine

    def execute(self, node, context: dict[str, Any], runtime_context: RuntimeExecutionContext) -> dict[str, Any]:
        agent = node.task_spec.agent
        assert agent is not None
        render_context = runtime_context.render_context(node, context) if callable(runtime_context.render_context) else context
        prompt_template = agent.prompt or agent.instructions or ""
        prompt = Template(prompt_template).safe_substitute(render_context)
        conversation_history = (
            runtime_context.build_conversation_history(node, render_context, context)
            if callable(runtime_context.build_conversation_history)
            else []
        )
        allowed_tools = [tool for tool in agent.allowed_tools if self._is_tool_usable(tool, node)]
        chunk_index = 0

        def relay(token: str) -> None:
            nonlocal chunk_index
            is_event, _ = decode_stream_event(token)
            is_reasoning, _ = decode_reasoning_chunk(token)
            if not is_event and not is_reasoning and token:
                runtime_context.emit(
                    "node.chunk",
                    {
                        "run_id": runtime_context.run_id,
                        "node_id": node.id,
                        "chunk_index": chunk_index,
                        "text": token,
                        "ts": _utc_now_iso(),
                    },
                )
                chunk_index += 1
            if callable(runtime_context.stream_handler):
                runtime_context.stream_handler(token)

        response = runtime_context.core.run_agent_task(
            prompt,
            project_path=runtime_context.project_path,
            model=agent.model,
            system_prompt=agent.system_prompt,
            stream_handler=relay,
            skill_names=agent.skills or None,
            allowed_tools=allowed_tools,
            conversation_history=conversation_history or None,
            run_id=runtime_context.run_id,
            node_id=node.id,
            thread_id=runtime_context.thread_id,
            request_id=runtime_context.request_id,
        )
        ingest_summary = ingest_artifacts(
            response_text=response,
            project_path=runtime_context.project_path,
            source={"run_id": runtime_context.run_id, "node_id": node.id},
        )
        return {"raw_output": response, "ingest_summary": ingest_summary}

    def _is_tool_usable(self, tool_name: str, node) -> bool:
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        tool_policy = metadata.get("tool_policy")
        if not isinstance(tool_policy, dict):
            return True
        try:
            decision = self.policy_engine.evaluate(
                tool_name,
                payload={},
                tool_policy=ToolPolicy.from_dict(tool_policy),
                invocation_mode=str(metadata.get("tool_invocation_mode") or "delegated"),
                selected_by="model",
            )
        except Exception:
            return False
        return decision.decision != "deny"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
