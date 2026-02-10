import os
import sys
import tempfile
import unittest
import zipfile
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

    def test_init_installs_missing_global_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
            finally:
                os.environ.pop("AMON_HOME", None)

            base_path = Path(temp_dir)
            source_dir = Path(__file__).resolve().parents[1] / "src" / "amon" / "resources" / "skills"
            expected_skill_dirs = set()
            for source_file in source_dir.glob("*.skill"):
                with zipfile.ZipFile(source_file) as archive:
                    for member in archive.namelist():
                        if member.endswith("/SKILL.md"):
                            expected_skill_dirs.add(Path(member).parent.name)

            installed_skill_dirs = {path.name for path in (base_path / "skills").iterdir() if path.is_dir()}
            self.assertTrue(expected_skill_dirs.issubset(installed_skill_dirs))

            index_path = base_path / "cache" / "skills" / "index.json"
            self.assertTrue(index_path.exists())
            index_content = index_path.read_text(encoding="utf-8")
            for skill_dir in expected_skill_dirs:
                self.assertIn(f'/skills/{skill_dir}/SKILL.md', index_content)


if __name__ == "__main__":
    unittest.main()
