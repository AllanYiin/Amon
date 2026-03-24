import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.domain.compiled_node_metadata import CompiledNodeMetadata
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.taskgraph3.validate import graph_definition_from_payload


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest"


def _load_manifest() -> AmonManifest:
    return AmonManifest.from_dict(json.loads((_fixture_root() / "pipeline_baseline_manifest.json").read_text(encoding="utf-8")))


class VNextCompiledMetadataTests(unittest.TestCase):
    def test_runtime_parser_reads_canonical_compiled_metadata(self) -> None:
        manifest = _load_manifest()

        graph = compile_manifest_workflow(manifest, "workflow.vnext_baseline").graph
        parsed = {node.id: CompiledNodeMetadata.from_node(node) for node in graph.nodes}

        self.assertEqual(parsed["research"].runtime_executor_type, "llm")
        self.assertEqual(parsed["research"].runtime_tool_invocation_mode, "delegated")
        self.assertEqual(parsed["research"].parsed_tool_policy.allowed_tools, ["web.search"])
        self.assertEqual(parsed["research"].agent_profile_ref, "agent.researcher.v1")
        self.assertEqual(parsed["memory_lookup"].runtime_executor_type, "tool")
        self.assertEqual(parsed["memory_lookup"].runtime_tool_invocation_mode, "deterministic")
        self.assertEqual(parsed["memory_lookup"].parsed_tool_policy.allowed_tools, ["memory.search"])
        self.assertEqual(parsed["sandbox_probe"].runtime_executor_type, "sandbox")
        self.assertEqual(parsed["sandbox_probe"].runtime_tool_invocation_mode, "deterministic")
        self.assertEqual(parsed["sandbox_probe"].parsed_tool_policy.side_effect_ceiling, "sandbox_exec")

    def test_legacy_stage0_compiled_graph_still_parses_via_task_spec_fallback(self) -> None:
        legacy_payload = json.loads((_fixture_root() / "pipeline_baseline_compiled_legacy.json").read_text(encoding="utf-8"))
        graph = graph_definition_from_payload(legacy_payload)
        parsed = {node.id: CompiledNodeMetadata.from_node(node) for node in graph.nodes}

        self.assertNotIn("executor_type", legacy_payload["nodes"][0]["metadata"])
        self.assertEqual(parsed["research"].runtime_executor_type, "llm")
        self.assertEqual(parsed["research"].runtime_tool_invocation_mode, "delegated")
        self.assertIsNone(parsed["research"].parsed_tool_policy)
        self.assertEqual(parsed["memory_lookup"].runtime_executor_type, "tool")
        self.assertEqual(parsed["memory_lookup"].runtime_tool_invocation_mode, "deterministic")
        self.assertEqual(parsed["sandbox_probe"].runtime_executor_type, "sandbox")
        self.assertEqual(parsed["sandbox_probe"].runtime_tool_invocation_mode, "deterministic")


if __name__ == "__main__":
    unittest.main()
