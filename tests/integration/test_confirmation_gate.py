from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.models import decode_stream_event
from amon.taskgraph3.amon_node_runner import AmonNodeRunner
from amon.taskgraph3.payloads import SandboxRunConfig, TaskSpec
from amon.taskgraph3.schema import TaskNode


class ConfirmationGateIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_runtime_flag = os.environ.get("AMON_VNEXT_RUNTIME")
        os.environ["AMON_VNEXT_RUNTIME"] = "1"

    def tearDown(self) -> None:
        if self._old_runtime_flag is None:
            os.environ.pop("AMON_VNEXT_RUNTIME", None)
            return
        os.environ["AMON_VNEXT_RUNTIME"] = self._old_runtime_flag

    def test_sandbox_execution_waits_for_confirmation_before_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            stream_tokens: list[str] = []
            runner = AmonNodeRunner(
                core=SimpleNamespace(load_config=lambda project_path: {"sandbox": {"runner": {"base_url": "http://sandbox.local"}}}),
                project_path=project_path,
                run_id="run-sandbox",
                variables={},
                stream_handler=stream_tokens.append,
            )
            node = TaskNode(
                id="sandbox-1",
                metadata={
                    "tool_policy": {
                        "id": "policy.sandbox",
                        "status": "active",
                        "allowed_tools": ["sandbox.run"],
                        "side_effect_ceiling": "sandbox_exec",
                    }
                },
                task_spec=TaskSpec(
                    executor="sandbox_run",
                    sandbox_run=SandboxRunConfig(command="echo hi", shell="bash"),
                ),
            )

            with patch("amon.runtime_vnext.sandbox_executor.run_sandbox_step") as mock_sandbox:
                result = runner.run_task(node, {})

            confirmation_dir = project_path / ".amon" / "runs" / "run-sandbox" / "confirmations"
            audit_path = project_path / ".amon" / "runs" / "run-sandbox" / "tool_audit.jsonl"
            events = [payload for token in stream_tokens for ok, payload in [decode_stream_event(token)] if ok]
            audit_payload = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(result["status"], "waiting_confirmation")
            self.assertFalse(mock_sandbox.called)
            self.assertTrue(any(confirmation_dir.glob("*.json")))
            self.assertEqual(audit_payload[0]["tool_name"], "sandbox.run")
            self.assertEqual(audit_payload[0]["approval_state"], "pending")
            self.assertTrue(any(item.get("event") == "node.confirmation_requested" for item in events))


if __name__ == "__main__":
    unittest.main()
