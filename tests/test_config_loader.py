import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.config import ConfigLoader


class ConfigLoaderTests(unittest.TestCase):
    def test_precedence_and_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                data_dir = Path(temp_dir)
                project_id = "project-123"
                project_dir = data_dir / "projects" / project_id
                project_dir.mkdir(parents=True, exist_ok=True)

                (data_dir / "config.yaml").write_text(
                    "\n".join(
                        [
                            "amon:",
                            "  default_mode: team",
                            "providers:",
                            "  openai:",
                            "    model: gpt-4",
                        ]
                    ),
                    encoding="utf-8",
                )
                (project_dir / "amon.project.yaml").write_text(
                    "\n".join(
                        [
                            "providers:",
                            "  openai:",
                            "    model: gpt-4o",
                        ]
                    ),
                    encoding="utf-8",
                )

                loader = ConfigLoader()
                resolution = loader.resolve(
                    project_id=project_id,
                    cli_overrides={
                        "providers": {"openai": {"model": "gpt-4.1"}},
                        "amon": {"default_mode": "single"},
                    },
                )

                self.assertEqual(resolution.effective["providers"]["openai"]["model"], "gpt-4.1")
                self.assertEqual(resolution.sources["providers"]["openai"]["model"], "cli")
                self.assertEqual(resolution.effective["amon"]["default_mode"], "single")
                self.assertEqual(resolution.sources["amon"]["default_mode"], "cli")
                self.assertEqual(resolution.sources["amon"]["ui"]["theme"], "default")
                self.assertEqual(resolution.effective["amon"]["ui"]["theme"], "light")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_rejects_invalid_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                loader = ConfigLoader()
                with self.assertRaises(ValueError):
                    loader.load_project("../escape")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
