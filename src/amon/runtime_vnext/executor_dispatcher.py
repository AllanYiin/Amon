"""Executor dispatcher for runtime vNext."""

from __future__ import annotations

import json

from amon.domain import UNSUPPORTED_EXECUTOR_TYPE_CODE, unsupported_executor_type_message
from amon.domain.compiled_node_metadata import CompiledNodeMetadata

from .audit_log import RuntimeAuditLog
from .confirmation_service import ConfirmationService
from .llm_executor import LLMExecutor
from .runner import RuntimeExecutionContext
from .sandbox_executor import SandboxExecutor
from .tool_executor import ToolExecutor
from .tool_policy_engine import ToolPolicyEngine


class ExecutorDispatcher:
    def __init__(self, *, project_path) -> None:
        policy_engine = ToolPolicyEngine()
        confirmation_service = ConfirmationService(project_path)
        audit_log = RuntimeAuditLog(project_path)
        self._llm = LLMExecutor(policy_engine)
        self._tool = ToolExecutor(
            policy_engine=policy_engine,
            confirmation_service=confirmation_service,
            audit_log=audit_log,
        )
        self._sandbox = SandboxExecutor(
            policy_engine=policy_engine,
            confirmation_service=confirmation_service,
            audit_log=audit_log,
        )
        self._confirmation_service = confirmation_service

    def dispatch(self, node, context: dict, runtime_context: RuntimeExecutionContext) -> dict:
        executor_type = self._resolve_executor_type(node)
        if executor_type == "llm":
            return self._llm.execute(node, context, runtime_context)
        if executor_type == "tool":
            return self._tool.execute(node, context, runtime_context)
        if executor_type == "sandbox":
            return self._sandbox.execute(node, context, runtime_context)
        if executor_type == "human_gate":
            confirmation = self._confirmation_service.request(
                run_id=runtime_context.run_id,
                node_id=node.id,
                tool_name="human_gate",
                reason="human gate requires explicit approval",
                preview={"node_id": node.id},
            )
            runtime_context.emit(
                "node.confirmation_requested",
                {
                    "run_id": runtime_context.run_id,
                    "node_id": node.id,
                    "confirmation_id": confirmation.id,
                    "tool_name": "human_gate",
                    "reason": confirmation.reason,
                },
            )
            return {
                "status": "waiting_confirmation",
                "confirmation": confirmation.to_dict(),
                "raw_output": json.dumps(confirmation.to_dict(), ensure_ascii=False),
            }
        if executor_type == "subgraph":
            raise ValueError(
                f"{UNSUPPORTED_EXECUTOR_TYPE_CODE}: "
                f"{unsupported_executor_type_message(executor_ref=node.id, executor_type=executor_type)}"
            )
        raise ValueError(f"AMON_RUNTIME_001: unsupported executor type={executor_type}")

    @staticmethod
    def _resolve_executor_type(node) -> str:
        return CompiledNodeMetadata.from_node(node).runtime_executor_type
