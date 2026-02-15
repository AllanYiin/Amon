import tempfile
import unittest
from pathlib import Path

from amon.tooling.builtin import build_registry as build_builtin_registry
from amon.tooling.builtins.terminal import register_terminal_tools
from amon.tooling.policy import ToolPolicy, WorkspaceGuard
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolCall


class TerminalExecTests(unittest.TestCase):
    def test_terminal_exec_supports_pipe_and_redirect(self) -> None:
        registry = ToolRegistry(policy=ToolPolicy(allow=("terminal.exec",)))
        register_terminal_tools(registry)

        result = registry.call(
            ToolCall(
                tool="terminal.exec",
                args={"command": 'printf "a\\nb\\n" | wc -l'},
                caller="tester",
            )
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.meta.get("returncode"), 0)
        self.assertIn("2", result.as_text())

    def test_terminal_exec_cwd_is_restricted_to_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            outside = Path(tmpdir) / "outside"
            outside.mkdir(parents=True, exist_ok=True)

            registry = ToolRegistry(
                policy=ToolPolicy(allow=("terminal.exec",)),
                workspace_guard=WorkspaceGuard(workspace_root=workspace),
            )
            register_terminal_tools(registry)

            with self.assertRaises(ValueError):
                registry.call(
                    ToolCall(
                        tool="terminal.exec",
                        args={"command": "pwd", "cwd": str(outside)},
                        caller="tester",
                    )
                )

    def test_terminal_exec_command_glob_policy(self) -> None:
        policy = ToolPolicy(allow=("terminal.exec:git *",))
        allowed = ToolCall(tool="terminal.exec", args={"command": "git status"}, caller="tester")
        denied = ToolCall(tool="terminal.exec", args={"command": "python -m unittest"}, caller="tester")

        self.assertEqual(policy.decide(allowed), "allow")
        self.assertEqual(policy.decide(denied), "deny")

    def test_terminal_exec_denied_by_builtin_default_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_builtin_registry(Path(tmpdir))
            result = registry.call(
                ToolCall(
                    tool="terminal.exec",
                    args={"command": "echo hi"},
                    caller="tester",
                )
            )
            self.assertEqual(result.meta.get("status"), "denied")


if __name__ == "__main__":
    unittest.main()
