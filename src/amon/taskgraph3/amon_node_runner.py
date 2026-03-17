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
    _CONTEXT_HISTORY_LIMIT = 3
    _CONTEXT_TEXT_LIMIT = 1200

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
        conversation_history = self._build_conversation_history(node, render_ctx, context)
        response = self.core.run_agent_task(
            prompt,
            project_path=self.project_path,
            model=agent.model,
            system_prompt=agent.system_prompt,
            stream_handler=self.stream_handler,
            skill_names=agent.skills or None,
            allowed_tools=agent.allowed_tools,
            conversation_history=conversation_history or None,
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

    def _build_conversation_history(
        self,
        node: TaskNode,
        render_ctx: dict[str, Any],
        runtime_context: dict[str, Any],
    ) -> list[dict[str, str]]:
        base_history = self._normalize_conversation_history(render_ctx.get("conversation_history"))
        enriched = list(base_history)
        seen_messages = {(item["role"], item["content"]) for item in enriched}
        supplemental: list[dict[str, str]] = []

        if node.id != "concept_alignment":
            concept_summary = self._resolve_upstream_binding(runtime_context, "concept_alignment", "raw")
            concept_text = self._normalize_context_excerpt(concept_summary)
            if concept_text:
                supplemental.append({"role": "assistant", "content": f"前置概念摘要：\n{concept_text}"})

        for binding in node.task_spec.input_bindings:
            if binding.source != "upstream" or not binding.from_node:
                continue
            source_node = str(binding.from_node)
            if source_node == "concept_alignment":
                continue
            value = self._resolve_upstream_binding(runtime_context, source_node, binding.port or "raw")
            excerpt = self._normalize_context_excerpt(value)
            if not excerpt:
                continue
            supplemental.append({"role": "assistant", "content": f"前置節點 {source_node} 摘要：\n{excerpt}"})

        for item in supplemental[: self._CONTEXT_HISTORY_LIMIT]:
            signature = (item["role"], item["content"])
            if signature in seen_messages:
                continue
            seen_messages.add(signature)
            enriched.append(item)
        return enriched

    @staticmethod
    def _normalize_conversation_history(history: Any) -> list[dict[str, str]]:
        if not isinstance(history, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            normalized.append({"role": role, "content": content})
        return normalized

    def _normalize_context_excerpt(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            if "raw" in value and isinstance(value.get("raw"), str):
                text = str(value.get("raw") or "")
            else:
                text = json.dumps(value, ensure_ascii=False, indent=2)
        elif isinstance(value, list):
            text = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            text = str(value)
        cleaned = " ".join(text.split()).strip()
        if len(cleaned) <= self._CONTEXT_TEXT_LIMIT:
            return cleaned
        return f"{cleaned[: self._CONTEXT_TEXT_LIMIT].rstrip()}…"
