import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.config import DEFAULT_FEATURE_FLAGS, FeatureFlags, load_feature_flags


class FeatureFlagTests(unittest.TestCase):
    def test_defaults_are_all_disabled(self) -> None:
        flags = load_feature_flags({})
        self.assertEqual(flags.as_dict(), DEFAULT_FEATURE_FLAGS)

    def test_truthy_values_enable_flags(self) -> None:
        flags = FeatureFlags.from_env(
            {
                "AMON_VNEXT_MANIFEST": "1",
                "AMON_VNEXT_BINDER": "true",
                "AMON_VNEXT_RUNTIME": "YES",
                "AMON_VNEXT_UI": "On",
            }
        )

        self.assertTrue(flags.manifest)
        self.assertTrue(flags.binder)
        self.assertTrue(flags.runtime)
        self.assertTrue(flags.ui)

    def test_invalid_flag_value_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_feature_flags({"AMON_VNEXT_MANIFEST": "maybe"})

    def test_unknown_flag_lookup_raises(self) -> None:
        with self.assertRaises(KeyError):
            load_feature_flags({}).is_enabled("AMON_VNEXT_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
