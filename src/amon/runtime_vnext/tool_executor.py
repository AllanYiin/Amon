"""Deterministic and delegated tool execution with policy/audit hooks."""

from __future__ import annotations

import json
from typing import Any

from amon.domain import ToolPolicy

from .audit_log import RuntimeAuditLog, ToolAuditRecord
from .confirmation_service import ConfirmationService
from .runner import RuntimeExecutionContext
from .tool_policy_engine import ToolPolicyDecision, ToolPolicyEngine


class ToolExecutor:
    def __init__(
        self,
        *,
        policy_engine: ToolPolicyEngine,
        confirmation_service: ConfirmationService,
        audit_log: RuntimeAuditLog,
    ) -> None:
        self.policy_engine = policy_engine
        self.confirmation_service = confirmation_service
        self.audit_log = audit_log

    def execute(self, node, context: dict[str, Any], runtime_context: RuntimeExecutionContext) -> dict[str, Any]:
        tool_cfg = node.task_spec.tool
        assert tool_cfg is not None
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        invocation_mode = str(metadata.get("tool_invocation_mode") or "deterministic")
        selected_by = "workflow" if invocation_mode == "deterministic" else "model"
        tool_policy = self._tool_policy_from_metadata(metadata)
        render_context = runtime_context.render_context(node, context) if callable(runtime_context.render_context) else context

        call_results: list[dict[str, Any]] = []
        primary_path = ""
        for spec in tool_cfg.tools:
            payload = runtime_context.render_payload(spec.args, render_context) if callable(runtime_context.render_payload) else spec.args
            if not primary_path and isinstance(payload, dict) and isinstance(payload.get("path"), str):
                primary_path = str(payload.get("path") or "")
            decision = self.policy_engine.evaluate(
                spec.name,
                payload=payload if isinstance(payload, dict) else {},
                tool_policy=tool_policy,
                invocation_mode=invocation_mode,
                selected_by=selected_by,
            )
            runtime_context.emit("node.tool_requested", self._decision_payload(runtime_context, node.id, decision))
            self.audit_log.record_tool_call(
                ToolAuditRecord(
                    run_id=runtime_context.run_id,
                    node_id=node.id,
                    tool_name=spec.name,
                    invocation_mode=invocation_mode,
                    selected_by=selected_by,
                    approval_state=decision.approval_state,
                    side_effect_class=decision.side_effect_class,
                    request_id=runtime_context.request_id,
                    thread_id=runtime_context.thread_id,
                    payload_preview=decision.preview,
                )
            )
            if decision.decision == "deny":
                raise PermissionError(f"AMON_TOOL_001: {decision.reason}")
            if decision.decision == "ask":
                confirmation = self.confirmation_service.request(
                    run_id=runtime_context.run_id,
                    node_id=node.id,
                    tool_name=spec.name,
                    reason=decision.reason,
                    preview=decision.preview,
                )
                runtime_context.emit(
                    "node.confirmation_requested",
                    {
                        "run_id": runtime_context.run_id,
                        "node_id": node.id,
                        "confirmation_id": confirmation.id,
                        "tool_name": spec.name,
                        "reason": decision.reason,
                    },
                )
                return {
                    "status": "waiting_confirmation",
                    "confirmation": confirmation.to_dict(),
                    "raw_output": json.dumps(confirmation.to_dict(), ensure_ascii=False),
                    "tool_calls": [],
                }

            result = runtime_context.core.run_tool(
                spec.name,
                payload if isinstance(payload, dict) else {},
                project_path=runtime_context.project_path,
                stream_handler=runtime_context.stream_handler,
                run_id=runtime_context.run_id,
                node_id=node.id,
                thread_id=runtime_context.thread_id,
                request_id=runtime_context.request_id,
            )
            if bool(result.get("is_error", False)):
                raise RuntimeError(result.get("text") or f"tool={spec.name} execution failed")
            call_results.append({"name": spec.name, "payload": payload, "result": result})

        return {
            "status": "succeeded",
            "raw_output": json.dumps(call_results, ensure_ascii=False),
            "tool_calls": call_results,
            "path": primary_path or None,
        }

    @staticmethod
    def _tool_policy_from_metadata(metadata: dict[str, Any]) -> ToolPolicy | None:
        payload = metadata.get("tool_policy")
        if not isinstance(payload, dict):
            return None
        return ToolPolicy.from_dict(payload)

    @staticmethod
    def _decision_payload(runtime_context: RuntimeExecutionContext, node_id: str, decision: ToolPolicyDecision) -> dict[str, Any]:
        return {
            "run_id": runtime_context.run_id,
            "node_id": node_id,
            "invocation_mode": decision.invocation_mode,
            "selected_by": decision.selected_by,
            "tool_name": decision.tool_name,
            "approval_state": decision.approval_state,
            "side_effect_class": decision.side_effect_class,
        }
