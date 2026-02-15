import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.tooling.builtins.terminal import build_sandbox_terminal_executor, register_terminal_tools
from amon.tooling.policy import ToolPolicy
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolCall


class TerminalSandboxBackendTests(unittest.TestCase):
    def test_terminal_exec_routes_to_sandbox_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            fake_run_step = Mock(
                return_value={
                    "exit_code": 0,
                    "timed_out": False,
                    "duration_ms": 5,
                    "stdout": "hello",
                    "stderr": "",
                    "manifest_path": str(workspace / "audits" / "artifacts" / "manifest.json"),
                }
            )
            executor = build_sandbox_terminal_executor(project_path=workspace, config={}, run_step=fake_run_step)
            registry = ToolRegistry(policy=ToolPolicy(allow=("terminal.exec",)))
            register_terminal_tools(registry, sandbox_executor=executor)

            result = registry.call(ToolCall(tool="terminal.exec", args={"command": "echo hello"}, caller="tester"))

            self.assertFalse(result.is_error)
            self.assertEqual(result.meta.get("backend"), "sandbox")
            self.assertEqual(fake_run_step.call_count, 1)
            kwargs = fake_run_step.call_args.kwargs
            self.assertEqual(kwargs["language"], "bash")
            self.assertIn("echo hello", kwargs["code"])
            self.assertTrue(str(kwargs["output_prefix"]).startswith("audits/artifacts/"))

    def test_terminal_session_exec_uses_sandbox_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            fake_run_step = Mock(
                return_value={
                    "exit_code": 0,
                    "timed_out": False,
                    "duration_ms": 5,
                    "stdout": "/tmp/workspace",
                    "stderr": "",
                    "manifest_path": str(workspace / "audits" / "artifacts" / "manifest.json"),
                }
            )
            executor = build_sandbox_terminal_executor(project_path=workspace, config={}, run_step=fake_run_step)
            registry = ToolRegistry(policy=ToolPolicy(allow=("terminal.session.start", "terminal.session.exec", "terminal.session.stop")))
            register_terminal_tools(registry, sandbox_executor=executor)

            start = registry.call(ToolCall(tool="terminal.session.start", args={"cwd": "/tmp/workspace"}, caller="tester"))
            session_id = start.meta["session_id"]
            result = registry.call(ToolCall(tool="terminal.session.exec", args={"session_id": session_id, "command": "pwd"}, caller="tester"))

            self.assertFalse(result.is_error)
            self.assertEqual(result.meta.get("backend"), "sandbox")
            kwargs = fake_run_step.call_args.kwargs
            self.assertIn("cd /tmp/workspace", kwargs["code"])


if __name__ == "__main__":
    unittest.main()
