import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class InitTests(unittest.TestCase):
    def test_init_creates_required_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
            finally:
                os.environ.pop("AMON_HOME", None)

            base_path = Path(temp_dir)
            expected_dirs = [
                base_path / "projects",
                base_path / "skills",
                base_path / "trash",
                base_path / "logs",
                base_path / "python_env",
                base_path / "node_env",
                base_path / "cache",
            ]
            for path in expected_dirs:
                self.assertTrue(path.exists(), f"missing {path}")

            self.assertTrue((base_path / "logs" / "amon.log").exists())
            self.assertTrue((base_path / "logs" / "billing.log").exists())
            self.assertTrue((base_path / "config.yaml").exists())
            bundled_skill = base_path / "skills" / "spec-to-tasks.skill"
            self.assertTrue(bundled_skill.exists())


if __name__ == "__main__":
    unittest.main()
