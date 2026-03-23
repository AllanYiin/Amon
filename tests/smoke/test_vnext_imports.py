import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


class VNextImportSmokeTests(unittest.TestCase):
    def test_vnext_packages_are_importable(self) -> None:
        modules = [
            "amon.application",
            "amon.config",
            "amon.config.feature_flags",
            "amon.domain",
            "amon.interfaces",
            "amon.interfaces.api",
            "amon.interfaces.cli",
            "amon.runtime_vnext",
            "amon.storage",
            "amon.templates",
        ]

        for module_name in modules:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)

    def test_config_loader_import_stays_compatible(self) -> None:
        from amon.config import ConfigLoader, FeatureFlags, load_feature_flags

        self.assertIsNotNone(ConfigLoader)
        self.assertIsInstance(load_feature_flags({}), FeatureFlags)


if __name__ == "__main__":
    unittest.main()
