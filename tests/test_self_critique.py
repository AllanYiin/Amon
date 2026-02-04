import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class SelfCritiqueTests(unittest.TestCase):
    def test_self_critique_creates_docs(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("需要設定 OPENAI_API_KEY 才能執行 LLM 測試")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)

                core.run_self_critique("測試 self critique", project_path=project_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            docs_dir = project_path / "docs"
            self.assertTrue((docs_dir / "draft_v1.md").exists())
            self.assertTrue((docs_dir / "final_v1.md").exists())
            reviews_dir = docs_dir / "reviews_v1"
            self.assertTrue(reviews_dir.exists())
            review_files = list(reviews_dir.glob("*.md"))
            self.assertEqual(len(review_files), 10)


if __name__ == "__main__":
    unittest.main()
