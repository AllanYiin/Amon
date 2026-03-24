from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from string import Template
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.binder import bind_workflow
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.runtime_vnext import ExecutorDispatcher, RuntimeExecutionContext


def _load_manifest() -> AmonManifest:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest" / "pipeline_baseline_manifest.json"
    return AmonManifest.from_dict(json.loads(fixture_path.read_text(encoding="utf-8")))


class _RuntimeCoreStub:
    def __init__(self) -> None:
        self.agent_calls: list[dict[str, object]] = []
        self.tool_calls: list[dict[str, object]] = []

    def run_agent_task(self, prompt: str, **kwargs: object) -> str:
        self.agent_calls.append({"prompt": prompt, **kwargs})
        return "baseline llm output"

    def run_tool(self, tool_name: str, payload: dict[str, object], **kwargs: object) -> dict[str, object]:
        self.tool_calls.append({"tool_name": tool_name, "payload": payload, **kwargs})
        return {"is_error": False, "text": "baseline tool output"}


class VNextBindCompileDispatchBaselineTests(unittest.TestCase):
    def test_bind_compile_dispatch_uses_canonical_metadata_contract(self) -> None:
        manifest = _load_manifest()
        workflow = manifest.workflows["workflow.vnext_baseline"]
        manifest.workflows["workflow.vnext_baseline"] = workflow.clone()
        manifest.workflows["workflow.vnext_baseline"].update(
            nodes=[replace(node, executor_ref="", status="draft") for node in workflow.nodes]
        )

        bound = bind_workflow(manifest, "workflow.vnext_baseline")
        manifest.workflows["workflow.vnext_baseline"] = bound
        compiled = compile_manifest_workflow(manifest, "workflow.vnext_baseline")
        nodes = {node.id: node for node in compiled.graph.nodes}

        self.assertEqual(
            {node_id: node.metadata["executor_type"] for node_id, node in nodes.items()},
            {
                "research": "llm",
                "memory_lookup": "tool",
                "sandbox_probe": "sandbox",
            },
        )
        self.assertEqual(nodes["research"].metadata["tool_policy"]["id"], "policy.readonly_web")
        self.assertEqual(nodes["memory_lookup"].metadata["tool_invocation_mode"], "deterministic")
        self.assertEqual(nodes["sandbox_probe"].metadata["timeout_s"], 60)

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            events: list[dict[str, object]] = []
            core = _RuntimeCoreStub()
            dispatcher = ExecutorDispatcher(project_path=project_path)
            runtime_context = RuntimeExecutionContext(
                core=core,
                project_path=project_path,
                run_id="run-baseline",
                variables={},
                event_sink=events.append,
                render_context=self._render_context,
                render_payload=self._render_payload,
            )

            llm_result = dispatcher.dispatch(nodes["research"], {}, runtime_context)
            tool_result = dispatcher.dispatch(nodes["memory_lookup"], {}, runtime_context)
            with patch("amon.runtime_vnext.sandbox_executor.run_sandbox_step") as mock_sandbox:
                sandbox_result = dispatcher.dispatch(nodes["sandbox_probe"], {}, runtime_context)

            self.assertEqual(llm_result["raw_output"], "baseline llm output")
            self.assertEqual(tool_result["status"], "succeeded")
            self.assertEqual(tool_result["tool_calls"][0]["name"], "memory.search")
            self.assertEqual(tool_result["tool_calls"][0]["payload"], {"query": "Phase 0 baseline"})
            self.assertEqual(sandbox_result["status"], "waiting_confirmation")
            self.assertEqual(len(core.agent_calls), 1)
            self.assertEqual(len(core.tool_calls), 1)
            self.assertFalse(mock_sandbox.called)
            self.assertEqual(
                [event["event"] for event in events],
                ["node.tool_requested", "node.tool_requested", "node.confirmation_requested"],
            )

    @staticmethod
    def _render_context(node, context: dict[str, object]) -> dict[str, object]:
        rendered = dict(context)
        for binding in node.task_spec.input_bindings:
            if binding.source == "literal":
                rendered[binding.key] = binding.value
        return rendered

    @classmethod
    def _render_payload(cls, payload, context: dict[str, object]):
        if isinstance(payload, str):
            return Template(payload).safe_substitute(context)
        if isinstance(payload, list):
            return [cls._render_payload(item, context) for item in payload]
        if isinstance(payload, dict):
            return {key: cls._render_payload(value, context) for key, value in payload.items()}
        return payload


if __name__ == "__main__":
    unittest.main()
