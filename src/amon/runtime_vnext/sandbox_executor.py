"""Sandbox execution adapter with confirmation gate."""

from __future__ import annotations

import json
from string import Template
from typing import Any

from amon.domain import ToolPolicy
from amon.sandbox.service import run_sandbox_step

from .audit_log import RuntimeAuditLog, ToolAuditRecord
from .confirmation_service import ConfirmationService
from .runner import RuntimeExecutionContext
from .tool_policy_engine import ToolPolicyEngine


class SandboxExecutor:
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
        sandbox_run = node.task_spec.sandbox_run
        assert sandbox_run is not None
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        tool_policy = ToolPolicy.from_dict(metadata["tool_policy"]) if isinstance(metadata.get("tool_policy"), dict) else None
        render_context = runtime_context.render_context(node, context) if callable(runtime_context.render_context) else context
        command = Template(sandbox_run.command or "").safe_substitute(render_context)
        payload = {
            "command": command,
            "shell": sandbox_run.shell,
            "workdir": Template(sandbox_run.workdir or "").safe_substitute(render_context),
        }
        decision = self.policy_engine.evaluate(
            "sandbox.run",
            payload=payload,
            tool_policy=tool_policy,
            invocation_mode="deterministic",
            selected_by="workflow",
        )
        runtime_context.emit(
            "node.tool_requested",
            {
                "run_id": runtime_context.run_id,
                "node_id": node.id,
                "invocation_mode": "deterministic",
                "selected_by": "workflow",
                "tool_name": "sandbox.run",
                "approval_state": decision.approval_state,
                "side_effect_class": decision.side_effect_class,
            },
        )
        self.audit_log.record_tool_call(
            ToolAuditRecord(
                run_id=runtime_context.run_id,
                node_id=node.id,
                tool_name="sandbox.run",
                invocation_mode="deterministic",
                selected_by="workflow",
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
                tool_name="sandbox.run",
                reason=decision.reason,
                preview=decision.preview,
            )
            runtime_context.emit(
                "node.confirmation_requested",
                {
                    "run_id": runtime_context.run_id,
                    "node_id": node.id,
                    "confirmation_id": confirmation.id,
                    "tool_name": "sandbox.run",
                    "reason": decision.reason,
                },
            )
            return {
                "status": "waiting_confirmation",
                "confirmation": confirmation.to_dict(),
                "raw_output": json.dumps(confirmation.to_dict(), ensure_ascii=False),
            }

        config = runtime_context.core.load_config(runtime_context.project_path)
        result = run_sandbox_step(
            project_path=runtime_context.project_path,
            config=config,
            run_id=runtime_context.run_id,
            step_id=node.id,
            language="python" if (sandbox_run.shell or "").strip().lower() == "python" else "bash",
            code=command,
            input_paths=[],
            output_prefix=f"docs/artifacts/{runtime_context.run_id}/{node.id}/",
            timeout_s=None,
            overwrite=False,
        )
        return {"status": "succeeded", "raw_output": json.dumps(result, ensure_ascii=False), **result}
