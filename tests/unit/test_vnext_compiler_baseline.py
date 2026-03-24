import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.taskgraph3.validate import validate_v3_graph_json


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "vnext_manifest"


def _load_manifest() -> AmonManifest:
    return AmonManifest.from_dict(json.loads((_fixture_root() / "pipeline_baseline_manifest.json").read_text(encoding="utf-8")))


class VNextCompilerBaselineTests(unittest.TestCase):
    def test_compile_baseline_manifest_matches_characterization_fixture(self) -> None:
        manifest = _load_manifest()
        expected = json.loads((_fixture_root() / "pipeline_baseline_compiled.json").read_text(encoding="utf-8"))

        result = compile_manifest_workflow(manifest, "workflow.vnext_baseline")
        payload = result.compiled_graph

        validate_v3_graph_json(payload)
        self.assertEqual(payload, expected)

    def test_compiler_emits_canonical_metadata_contract(self) -> None:
        manifest = _load_manifest()

        payload = compile_manifest_workflow(manifest, "workflow.vnext_baseline").compiled_graph
        metadata_by_node = {node["id"]: node["metadata"] for node in payload["nodes"]}

        self.assertEqual(
            {node_id: sorted(metadata.keys()) for node_id, metadata in metadata_by_node.items()},
            {
                "research": [
                    "agent_profile_ref",
                    "agent_profile_version",
                    "approval_policy",
                    "executor_ref",
                    "executor_type",
                    "executor_version",
                    "required_capabilities",
                    "retry_policy",
                    "streaming_required",
                    "task_ref",
                    "task_version",
                    "timeout_s",
                    "tool_invocation_mode",
                    "tool_policy",
                ],
                "memory_lookup": [
                    "agent_profile_ref",
                    "agent_profile_version",
                    "approval_policy",
                    "executor_ref",
                    "executor_type",
                    "executor_version",
                    "required_capabilities",
                    "retry_policy",
                    "streaming_required",
                    "task_ref",
                    "task_version",
                    "timeout_s",
                    "tool_invocation_mode",
                    "tool_policy",
                ],
                "sandbox_probe": [
                    "agent_profile_ref",
                    "agent_profile_version",
                    "approval_policy",
                    "executor_ref",
                    "executor_type",
                    "executor_version",
                    "required_capabilities",
                    "retry_policy",
                    "streaming_required",
                    "task_ref",
                    "task_version",
                    "timeout_s",
                    "tool_invocation_mode",
                    "tool_policy",
                ],
            },
        )
        self.assertEqual(metadata_by_node["research"]["executor_type"], "llm")
        self.assertEqual(metadata_by_node["research"]["tool_invocation_mode"], "delegated")
        self.assertEqual(metadata_by_node["research"]["tool_policy"]["id"], "policy.readonly_web")
        self.assertEqual(metadata_by_node["memory_lookup"]["executor_type"], "tool")
        self.assertEqual(metadata_by_node["memory_lookup"]["tool_policy"]["allowed_tools"], ["memory.search"])
        self.assertEqual(metadata_by_node["sandbox_probe"]["executor_type"], "sandbox")
        self.assertIsNone(metadata_by_node["sandbox_probe"]["tool_invocation_mode"])
        self.assertEqual(
            {node["id"]: node["taskSpec"]["executor"] for node in payload["nodes"]},
            {
                "research": "agent",
                "memory_lookup": "tool",
                "sandbox_probe": "sandbox_run",
            },
        )


if __name__ == "__main__":
    unittest.main()
