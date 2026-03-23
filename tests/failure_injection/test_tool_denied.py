from __future__ import annotations

import sys
import tempfile
import unittest
import os
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.models import decode_stream_event
from amon.taskgraph3.amon_node_runner import AmonNodeRunner
from amon.taskgraph3.payloads import TaskSpec, ToolCallSpec, ToolTaskConfig
from amon.taskgraph3.schema import TaskNode


class ToolDeniedFailureInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_runtime_flag = os.environ.get("AMON_VNEXT_RUNTIME")
        os.environ["AMON_VNEXT_RUNTIME"] = "1"

    def tearDown(self) -> None:
        if self._old_runtime_flag is None:
            os.environ.pop("AMON_VNEXT_RUNTIME", None)
            return
        os.environ["AMON_VNEXT_RUNTIME"] = self._old_runtime_flag

    def test_delegated_tool_denied_is_emitted_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream_tokens: list[str] = []
            core = SimpleNamespace(
                run_tool=lambda *args, **kwargs: {"ok": True},
                load_config=lambda project_path: {"sandbox": {"runner": {"base_url": "http://sandbox.local"}}},
                resolve_project_identity=lambda project_path: ("project.demo", Path(project_path)),
            )
            runner = AmonNodeRunner(
                core=core,
                project_path=Path(tmp),
                run_id="run-denied",
                variables={},
                stream_handler=stream_tokens.append,
            )
            node = TaskNode(
                id="tool-denied",
                metadata={
                    "tool_invocation_mode": "delegated",
                    "tool_policy": {
                        "id": "policy.readonly",
                        "status": "active",
                        "allowed_tools": ["web.search"],
                        "delegated_allowed": True,
                        "allow_network": False,
                        "side_effect_ceiling": "read_only",
                    },
                },
                task_spec=TaskSpec(
                    executor="tool",
                    tool=ToolTaskConfig(
                        tools=[ToolCallSpec(name="filesystem.write", args={"path": "workspace/out.txt", "content": "x"})]
                    ),
                ),
            )

            with self.assertRaisesRegex(PermissionError, "AMON_TOOL_001"):
                runner.run_task(node, {})
            events = [payload for token in stream_tokens for ok, payload in [decode_stream_event(token)] if ok]

            self.assertTrue(any(item.get("event") == "node.tool_requested" for item in events))


if __name__ == "__main__":
    unittest.main()
