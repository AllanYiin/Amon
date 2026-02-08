import tempfile
import unittest
from pathlib import Path

from amon.tooling.policy import ToolPolicy, WorkspaceGuard
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolCall, ToolResult, ToolSpec


class ToolPolicyTests(unittest.TestCase):
    def test_policy_priority(self) -> None:
        policy = ToolPolicy(
            allow=("filesystem.*",),
            ask=("filesystem.read",),
            deny=("filesystem.delete",),
        )
        delete_call = ToolCall(tool="filesystem.delete", args={}, caller="tester")
        read_call = ToolCall(tool="filesystem.read", args={}, caller="tester")
        list_call = ToolCall(tool="filesystem.list", args={}, caller="tester")
        other_call = ToolCall(tool="process.exec", args={}, caller="tester")

        self.assertEqual(policy.decide(delete_call), "deny")
        self.assertEqual(policy.decide(read_call), "ask")
        self.assertEqual(policy.decide(list_call), "allow")
        self.assertEqual(policy.decide(other_call), "deny")

    def test_process_exec_command_glob(self) -> None:
        policy = ToolPolicy(allow=("process.exec:git *",))
        call = ToolCall(tool="process.exec", args={"command": "git status"}, caller="tester")
        self.assertEqual(policy.decide(call), "allow")


class WorkspaceGuardTests(unittest.TestCase):
    def test_workspace_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            guard = WorkspaceGuard(workspace_root=Path(tmpdir))
            outside = Path(tmpdir).parent / "outside.txt"
            with self.assertRaises(ValueError):
                guard.assert_in_workspace(outside)

    def test_workspace_denied_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            guard = WorkspaceGuard(workspace_root=root)
            denied = root / ".env"
            denied.write_text("SECRET=1", encoding="utf-8")
            with self.assertRaises(ValueError):
                guard.assert_in_workspace(denied)


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = ToolSpec(
            name="filesystem.read",
            description="Read a file",
            input_schema={},
            output_schema=None,
            risk="low",
            annotations={},
        )

    def test_unknown_tool(self) -> None:
        registry = ToolRegistry()
        result = registry.call(ToolCall(tool="missing", args={}, caller="tester"))
        self.assertTrue(result.is_error)
        self.assertEqual(result.meta.get("status"), "unknown_tool")

    def test_policy_deny(self) -> None:
        registry = ToolRegistry(policy=ToolPolicy(deny=("filesystem.*",)))
        registry.register(self.spec, lambda call: ToolResult())
        result = registry.call(ToolCall(tool="filesystem.read", args={}, caller="tester"))
        self.assertTrue(result.is_error)
        self.assertEqual(result.meta.get("status"), "denied")

    def test_policy_ask_requires_approval(self) -> None:
        registry = ToolRegistry(policy=ToolPolicy(ask=("filesystem.*",)))
        registry.register(self.spec, lambda call: ToolResult())
        result = registry.call(
            ToolCall(tool="filesystem.read", args={}, caller="tester"),
            require_approval=True,
        )
        self.assertTrue(result.is_error)
        self.assertEqual(result.meta.get("status"), "approval_required")

    def test_policy_allow(self) -> None:
        registry = ToolRegistry(policy=ToolPolicy(allow=("filesystem.*",)))
        registry.register(self.spec, lambda call: ToolResult(content=[{"text": "ok"}]))
        result = registry.call(ToolCall(tool="filesystem.read", args={}, caller="tester"))
        self.assertFalse(result.is_error)
        self.assertEqual(result.as_text(), "ok")

    def test_workspace_guard_blocks_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            guard = WorkspaceGuard(workspace_root=root)
            registry = ToolRegistry(
                policy=ToolPolicy(allow=("filesystem.*",)),
                workspace_guard=guard,
            )
            registry.register(self.spec, lambda call: ToolResult())
            with self.assertRaises(ValueError):
                registry.call(
                    ToolCall(
                        tool="filesystem.read",
                        args={"path": str(root.parent / "nope.txt")},
                        caller="tester",
                    )
                )


if __name__ == "__main__":
    unittest.main()
