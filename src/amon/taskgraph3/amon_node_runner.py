"""Amon-specific TaskGraph v3 task runner."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Any

from amon.artifacts.store import ingest_artifacts
from amon.sandbox.service import run_sandbox_step

from .schema import TaskNode


class AmonNodeRunner:
    def __init__(
        self,
        *,
        core,
        project_path: Path,
        run_id: str,
        variables: dict[str, Any],
        stream_handler=None,
        request_id: str | None = None,
        thread_id: str | None = None,
    ) -> None:
        self.core = core
        self.project_path = Path(project_path)
        self.run_id = run_id
        self.variables = variables
        self.stream_handler = stream_handler
        self.request_id = request_id
        self.thread_id = thread_id

    def run_task(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        if not node.task_spec.runnable:
            raise ValueError(node.task_spec.non_runnable_reason or f"node={node.id} task_spec not runnable")
        executor = node.task_spec.executor
        if executor == "agent":
            return self._run_agent(node, context)
        if executor == "tool":
            return self._run_tool(node, context)
        if executor == "sandbox_run":
            return self._run_sandbox(node, context)
        raise ValueError(f"node={node.id} unsupported executor={executor}")

    def _run_agent(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        agent = node.task_spec.agent
        assert agent is not None
        render_ctx = self._render_context(node, context)
        prompt_template = agent.prompt or agent.instructions or ""
        prompt = Template(prompt_template).safe_substitute(render_ctx)
        conversation_history = render_ctx.get("conversation_history")
        response = self.core.run_agent_task(
            prompt,
            project_path=self.project_path,
            model=agent.model,
            system_prompt=agent.system_prompt,
            stream_handler=self.stream_handler,
            skill_names=agent.skills or None,
            allowed_tools=agent.allowed_tools,
            conversation_history=conversation_history if isinstance(conversation_history, list) else None,
            run_id=self.run_id,
            node_id=node.id,
            thread_id=self.thread_id,
            request_id=self.request_id,
        )
        ingest_summary = ingest_artifacts(
            response_text=response,
            project_path=self.project_path,
            source={"run_id": self.run_id, "node_id": node.id},
        )
        return {
            "raw_output": response,
            "ingest_summary": ingest_summary,
        }

    def _run_tool(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        tool_cfg = node.task_spec.tool
        assert tool_cfg is not None
        render_ctx = self._render_context(node, context)
        call_results: list[dict[str, Any]] = []
        primary_path = ""
        project_id, _ = self.core.resolve_project_identity(self.project_path)
        for spec in tool_cfg.tools:
            payload = self._render_payload(spec.args, render_ctx)
            if not primary_path and isinstance(payload, dict) and isinstance(payload.get("path"), str):
                primary_path = str(payload.get("path") or "")
            result = self.core.run_tool(
                spec.name,
                payload,
                project_id=project_id,
                project_path=self.project_path,
                stream_handler=self.stream_handler,
                run_id=self.run_id,
                node_id=node.id,
                thread_id=self.thread_id,
                request_id=self.request_id,
            )
            if bool(result.get("is_error", False)):
                raise RuntimeError(result.get("text") or f"tool={spec.name} execution failed")
            call_results.append({"name": spec.name, "payload": payload, "result": result})
        return {
            "raw_output": json.dumps(call_results, ensure_ascii=False),
            "tool_calls": call_results,
            "path": primary_path or None,
        }

    def _run_sandbox(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        config = self.core.load_config(self.project_path)
        run_cfg = node.task_spec.sandbox_run
        assert run_cfg is not None
        render_ctx = self._render_context(node, context)
        command = Template(run_cfg.command or "").safe_substitute(render_ctx)
        workdir = Template(run_cfg.workdir or "").safe_substitute(render_ctx)
        language = "bash"
        code = command
        if (run_cfg.shell or "").strip().lower() == "python":
            language = "python"
            code = command
        output_prefix = f"docs/artifacts/{self.run_id}/{node.id}/"
        result = run_sandbox_step(
            project_path=self.project_path,
            config=config,
            run_id=self.run_id,
            step_id=node.id,
            language=language,
            code=code,
            input_paths=[],
            output_prefix=output_prefix,
            timeout_s=None,
            overwrite=False,
        )
        return {"raw_output": json.dumps(result, ensure_ascii=False), **result}

    def _render_context(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        render_ctx = {**self.variables, **context, "run_id": self.run_id}
        render_ctx.update(self._resolve_input_bindings(node, render_ctx, context))
        return render_ctx

    def _resolve_input_bindings(
        self,
        node: TaskNode,
        render_ctx: dict[str, Any],
        runtime_context: dict[str, Any],
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for binding in node.task_spec.input_bindings:
            if binding.source == "literal":
                resolved[binding.key] = binding.value
                continue
            if binding.source == "variable":
                source_key = str(binding.value).strip() if binding.value is not None else binding.key
                resolved[binding.key] = render_ctx.get(source_key)
                continue
            if binding.source == "upstream":
                resolved[binding.key] = self._resolve_upstream_binding(runtime_context, binding.from_node or "", binding.port or "")
        return resolved

    @staticmethod
    def _resolve_upstream_binding(runtime_context: dict[str, Any], from_node: str, port: str) -> Any:
        nodes = runtime_context.get("nodes")
        if not isinstance(nodes, dict):
            return None
        upstream_state = nodes.get(from_node)
        if not isinstance(upstream_state, dict):
            return None
        output = upstream_state.get("output")
        if port == "raw":
            if isinstance(output, dict):
                if "raw" in output:
                    return output.get("raw")
                if "raw_output" in output:
                    return output.get("raw_output")
            return output
        if not isinstance(output, dict):
            return None
        ports = output.get("ports")
        if isinstance(ports, dict) and port in ports:
            return ports.get(port)
        return output.get(port)

    def _render_payload(self, payload: Any, context: dict[str, Any]) -> Any:
        if isinstance(payload, str):
            return Template(payload).safe_substitute(context)
        if isinstance(payload, list):
            return [self._render_payload(item, context) for item in payload]
        if isinstance(payload, dict):
            return {key: self._render_payload(value, context) for key, value in payload.items()}
        return payload
