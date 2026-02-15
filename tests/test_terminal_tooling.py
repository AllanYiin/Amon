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


class TerminalSessionTests(unittest.TestCase):
    def test_terminal_session_persists_cwd_and_env(self) -> None:
        registry = ToolRegistry(policy=ToolPolicy(allow=("terminal.session.start", "terminal.session.exec", "terminal.session.stop")))
        register_terminal_tools(registry)

        start = registry.call(
            ToolCall(
                tool="terminal.session.start",
                args={"env": {"AMON_SESSION_TEST": "persisted"}},
                caller="tester",
            )
        )
        self.assertFalse(start.is_error)
        session_id = start.meta.get("session_id")
        self.assertIsInstance(session_id, str)

        first = registry.call(
            ToolCall(
                tool="terminal.session.exec",
                args={"session_id": session_id, "command": "pwd"},
                caller="tester",
            )
        )
        self.assertFalse(first.is_error)

        second = registry.call(
            ToolCall(
                tool="terminal.session.exec",
                args={"session_id": session_id, "command": "cd ..; pwd"},
                caller="tester",
            )
        )
        self.assertFalse(second.is_error)
        self.assertNotEqual(first.as_text(), second.as_text())

        env_value = registry.call(
            ToolCall(
                tool="terminal.session.exec",
                args={"session_id": session_id, "command": "echo $AMON_SESSION_TEST"},
                caller="tester",
            )
        )
        self.assertFalse(env_value.is_error)
        self.assertIn("persisted", env_value.as_text())

        stop = registry.call(
            ToolCall(tool="terminal.session.stop", args={"session_id": session_id}, caller="tester")
        )
        self.assertFalse(stop.is_error)

    def test_terminal_session_exec_after_stop_returns_not_found(self) -> None:
        registry = ToolRegistry(policy=ToolPolicy(allow=("terminal.session.start", "terminal.session.exec", "terminal.session.stop")))
        register_terminal_tools(registry)

        start = registry.call(ToolCall(tool="terminal.session.start", args={}, caller="tester"))
        session_id = start.meta.get("session_id")
        registry.call(ToolCall(tool="terminal.session.stop", args={"session_id": session_id}, caller="tester"))

        result = registry.call(
            ToolCall(
                tool="terminal.session.exec",
                args={"session_id": session_id, "command": "pwd"},
                caller="tester",
            )
        )
        self.assertTrue(result.is_error)
        self.assertEqual(result.meta.get("status"), "not_found")

    def test_terminal_session_exec_command_glob_policy(self) -> None:
        policy = ToolPolicy(allow=("terminal.session.exec:git *",))
        allowed = ToolCall(tool="terminal.session.exec", args={"command": "git status", "session_id": "s"}, caller="tester")
        denied = ToolCall(tool="terminal.session.exec", args={"command": "python -m unittest", "session_id": "s"}, caller="tester")

        self.assertEqual(policy.decide(allowed), "allow")
        self.assertEqual(policy.decide(denied), "deny")

    def test_terminal_session_exec_truncates_output(self) -> None:
        registry = ToolRegistry(policy=ToolPolicy(allow=("terminal.session.start", "terminal.session.exec", "terminal.session.stop")))
        register_terminal_tools(registry)

        start = registry.call(
            ToolCall(
                tool="terminal.session.start",
                args={"max_output_chars": 256},
                caller="tester",
            )
        )
        session_id = start.meta.get("session_id")

        result = registry.call(
            ToolCall(
                tool="terminal.session.exec",
                args={"session_id": session_id, "command": "python -c \"print(\'x\'*2000)\""},
                caller="tester",
            )
        )
        self.assertFalse(result.is_error)
        self.assertTrue(result.meta.get("truncated"))
        self.assertIn("[output truncated]", result.as_text())

        registry.call(ToolCall(tool="terminal.session.stop", args={"session_id": session_id}, caller="tester"))

    def test_terminal_session_denied_by_builtin_default_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_builtin_registry(Path(tmpdir))
            result = registry.call(
                ToolCall(
                    tool="terminal.session.start",
                    args={},
                    caller="tester",
                )
            )
            self.assertEqual(result.meta.get("status"), "denied")


if __name__ == "__main__":
    unittest.main()
