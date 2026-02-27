import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.config import DEFAULT_CONFIG
from amon.events import (
    EXECUTION_MODE_DECISION,
    KNOWN_EVENT_TYPES,
    PLAN_COMPILED,
    PLAN_GENERATED,
    TOOL_DISPATCH,
)


class PlanExecGraphContractTests(unittest.TestCase):
    def test_feature_flags_default_values(self) -> None:
        planner = DEFAULT_CONFIG["amon"]["planner"]
        tools = DEFAULT_CONFIG["amon"]["tools"]

        self.assertTrue(planner["enabled"])
        self.assertFalse(planner["preview_only"])
        self.assertFalse(tools["unified_dispatch"])

    def test_new_event_types_are_registered(self) -> None:
        self.assertIn(EXECUTION_MODE_DECISION, KNOWN_EVENT_TYPES)
        self.assertIn(PLAN_GENERATED, KNOWN_EVENT_TYPES)
        self.assertIn(PLAN_COMPILED, KNOWN_EVENT_TYPES)
        self.assertIn(TOOL_DISPATCH, KNOWN_EVENT_TYPES)


if __name__ == "__main__":
    unittest.main()
