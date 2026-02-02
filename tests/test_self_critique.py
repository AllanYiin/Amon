import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class SelfCritiqueTests(unittest.TestCase):
    def test_self_critique_creates_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                core.set_config_value(
                    "providers.mock",
                    {
                        "type": "mock",
                        "default_model": "mock-model",
                        "stream_chunks": ["草", "稿"],
                    },
                    project_path=project_path,
                )
                core.set_config_value("amon.provider", "mock", project_path=project_path)

                core.run_self_critique("測試 self critique", project_path=project_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            docs_dir = project_path / "docs"
            self.assertTrue((docs_dir / "draft.md").exists())
            self.assertTrue((docs_dir / "final.md").exists())
            reviews_dir = docs_dir / "reviews"
            self.assertTrue(reviews_dir.exists())
            review_files = list(reviews_dir.glob("*.md"))
            self.assertEqual(len(review_files), 10)


if __name__ == "__main__":
    unittest.main()
