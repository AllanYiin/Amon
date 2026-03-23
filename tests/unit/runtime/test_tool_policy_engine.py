import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.domain import ToolPolicy
from amon.runtime_vnext.tool_policy_engine import ToolPolicyEngine


class ToolPolicyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ToolPolicyEngine()

    def test_deterministic_read_only_tool_is_allowed_without_policy(self) -> None:
        decision = self.engine.evaluate(
            "filesystem.read",
            payload={"path": "workspace/input.txt"},
            tool_policy=None,
            invocation_mode="deterministic",
            selected_by="workflow",
        )

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.approval_state, "approved")
        self.assertEqual(decision.side_effect_class, "read_only")

    def test_delegated_tool_requires_policy(self) -> None:
        decision = self.engine.evaluate(
            "filesystem.read",
            payload={"path": "workspace/input.txt"},
            tool_policy=None,
            invocation_mode="delegated",
            selected_by="model",
        )

        self.assertEqual(decision.decision, "deny")
        self.assertIn("tool policy", decision.reason)

    def test_tool_path_must_stay_within_allowed_paths(self) -> None:
        policy = ToolPolicy.create(
            policy_id="policy.readwrite",
            allowed_tools=["filesystem.write"],
            allowed_paths=["workspace"],
            side_effect_ceiling="workspace_write",
            status="active",
        )

        decision = self.engine.evaluate(
            "filesystem.write",
            payload={"path": "../escape.txt"},
            tool_policy=policy,
            invocation_mode="deterministic",
            selected_by="workflow",
        )

        self.assertEqual(decision.decision, "deny")
        self.assertIn("allowed_paths", decision.reason)

    def test_destructive_write_requires_confirmation(self) -> None:
        policy = ToolPolicy.create(
            policy_id="policy.fs",
            allowed_tools=["filesystem.delete"],
            side_effect_ceiling="destructive_write",
            status="active",
        )

        decision = self.engine.evaluate(
            "filesystem.delete",
            payload={"path": "workspace/data.txt"},
            tool_policy=policy,
            invocation_mode="deterministic",
            selected_by="workflow",
        )

        self.assertEqual(decision.decision, "ask")
        self.assertEqual(decision.approval_state, "pending")
        self.assertEqual(decision.side_effect_class, "destructive_write")


if __name__ == "__main__":
    unittest.main()
