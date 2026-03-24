from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from string import Template
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.runtime_vnext import ExecutorDispatcher, RuntimeExecutionContext
from amon.taskgraph3.validate import graph_definition_from_payload


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest"


def _load_manifest() -> AmonManifest:
    return AmonManifest.from_dict(json.loads((_fixture_root() / "pipeline_baseline_manifest.json").read_text(encoding="utf-8")))


class _RuntimeCoreStub:
    def __init__(self) -> None:
        self.agent_calls: list[dict[str, object]] = []
        self.tool_calls: list[dict[str, object]] = []

    def run_agent_task(self, prompt: str, **kwargs: object) -> str:
        self.agent_calls.append({"prompt": prompt, **kwargs})
        return "contract llm output"

    def run_tool(self, tool_name: str, payload: dict[str, object], **kwargs: object) -> dict[str, object]:
        self.tool_calls.append({"tool_name": tool_name, "payload": payload, **kwargs})
        return {"is_error": False, "text": "contract tool output"}


class VNextCompileDispatchContractTests(unittest.TestCase):
    def test_compile_and_dispatch_path_uses_canonical_metadata(self) -> None:
        graph = compile_manifest_workflow(_load_manifest(), "workflow.vnext_baseline").graph
        nodes = {node.id: node for node in graph.nodes}

        with tempfile.TemporaryDirectory() as tmp:
            llm_result, tool_result, sandbox_result, events, core, mock_sandbox = self._dispatch_all(nodes, Path(tmp))

        self.assertEqual(nodes["research"].metadata["executor_type"], "llm")
        self.assertEqual(nodes["memory_lookup"].metadata["tool_invocation_mode"], "deterministic")
        self.assertEqual(nodes["sandbox_probe"].metadata["tool_policy"]["id"], "policy.sandbox_exec")
        self.assertEqual(llm_result["raw_output"], "contract llm output")
        self.assertEqual(tool_result["status"], "succeeded")
        self.assertEqual(tool_result["tool_calls"][0]["payload"], {"query": "Phase 0 baseline"})
        self.assertEqual(sandbox_result["status"], "waiting_confirmation")
        self.assertEqual(len(core.agent_calls), 1)
        self.assertEqual(len(core.tool_calls), 1)
        self.assertFalse(mock_sandbox.called)
        self.assertEqual(
            [event["event"] for event in events],
            ["node.tool_requested", "node.tool_requested", "node.confirmation_requested"],
        )

    def test_legacy_compiled_graph_without_new_metadata_still_dispatches(self) -> None:
        legacy_payload = json.loads((_fixture_root() / "pipeline_baseline_compiled_legacy.json").read_text(encoding="utf-8"))
        graph = graph_definition_from_payload(legacy_payload)
        nodes = {node.id: node for node in graph.nodes}

        self.assertTrue(all("executor_type" not in (node.metadata or {}) for node in nodes.values()))

        with tempfile.TemporaryDirectory() as tmp:
            llm_result, tool_result, sandbox_result, events, core, mock_sandbox = self._dispatch_all(nodes, Path(tmp))

        self.assertEqual(llm_result["raw_output"], "contract llm output")
        self.assertEqual(tool_result["status"], "succeeded")
        self.assertEqual(tool_result["tool_calls"][0]["payload"], {"query": "Phase 0 baseline"})
        self.assertEqual(sandbox_result["status"], "waiting_confirmation")
        self.assertEqual(len(core.agent_calls), 1)
        self.assertEqual(len(core.tool_calls), 1)
        self.assertFalse(mock_sandbox.called)
        self.assertEqual(
            [event["event"] for event in events],
            ["node.tool_requested", "node.tool_requested", "node.confirmation_requested"],
        )

    def _dispatch_all(self, nodes: dict[str, object], project_path: Path):
        events: list[dict[str, object]] = []
        core = _RuntimeCoreStub()
        dispatcher = ExecutorDispatcher(project_path=project_path)
        runtime_context = RuntimeExecutionContext(
            core=core,
            project_path=project_path,
            run_id="run-contract",
            variables={},
            event_sink=events.append,
            render_context=self._render_context,
            render_payload=self._render_payload,
        )
        llm_result = dispatcher.dispatch(nodes["research"], {}, runtime_context)
        tool_result = dispatcher.dispatch(nodes["memory_lookup"], {}, runtime_context)
        with patch("amon.runtime_vnext.sandbox_executor.run_sandbox_step") as mock_sandbox:
            sandbox_result = dispatcher.dispatch(nodes["sandbox_probe"], {}, runtime_context)
        return llm_result, tool_result, sandbox_result, events, core, mock_sandbox

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
