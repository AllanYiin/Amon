"""Amon-specific TaskGraph v3 task runner."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Any

from amon.artifacts.store import ingest_artifacts
from amon.fs.atomic import atomic_write_text
from amon.fs.safety import canonicalize_path
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
        chat_id: str | None = None,
    ) -> None:
        self.core = core
        self.project_path = Path(project_path)
        self.run_id = run_id
        self.variables = variables
        self.stream_handler = stream_handler
        self.request_id = request_id
        self.chat_id = chat_id

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
        if executor == "write_file":
            return self._run_write_file(node, context)
        raise ValueError(f"node={node.id} unsupported executor={executor}")

    def _run_agent(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        agent = node.task_spec.agent
        assert agent is not None
        render_ctx = self._render_context(context)
        prompt_template = agent.prompt or agent.instructions or ""
        prompt = Template(prompt_template).safe_substitute(render_ctx)
        response = self.core.run_agent_task(
            prompt,
            project_path=self.project_path,
            model=agent.model,
            stream_handler=self.stream_handler,
            run_id=self.run_id,
            node_id=node.id,
            chat_id=self.chat_id,
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
        render_ctx = self._render_context(context)
        call_results: list[dict[str, Any]] = []
        for spec in tool_cfg.tools:
            payload = self._render_payload(spec.args, render_ctx)
            result = self.core.run_tool(spec.name, payload)
            call_results.append({"name": spec.name, "payload": payload, "result": result})
        return {"raw_output": json.dumps(call_results, ensure_ascii=False), "tool_calls": call_results}

    def _run_sandbox(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        config = self.core.load_config(self.project_path)
        run_cfg = node.task_spec.sandbox_run
        assert run_cfg is not None
        render_ctx = self._render_context(context)
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

    def _run_write_file(self, node: TaskNode, context: dict[str, Any]) -> dict[str, Any]:
        cfg = node.task_spec.write_file
        assert cfg is not None
        render_ctx = self._render_context(context)
        rel_path = Template(cfg.path or "").safe_substitute(render_ctx)
        content = Template(cfg.content_template or "").safe_substitute(render_ctx)
        target = canonicalize_path(self.project_path, rel_path, allowed_prefixes=["docs", "audits"])
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, content)
        return {
            "raw_output": content,
            "path": str(target.relative_to(self.project_path).as_posix()),
        }

    def _render_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return {**self.variables, **context, "run_id": self.run_id}

    def _render_payload(self, payload: Any, context: dict[str, Any]) -> Any:
        if isinstance(payload, str):
            return Template(payload).safe_substitute(context)
        if isinstance(payload, list):
            return [self._render_payload(item, context) for item in payload]
        if isinstance(payload, dict):
            return {key: self._render_payload(value, context) for key, value in payload.items()}
        return payload
