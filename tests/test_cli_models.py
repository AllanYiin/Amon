import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon import cli


class ModelsCliTests(unittest.TestCase):
    def test_models_pull_downloads_all_known_models_to_amon_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            created: list[tuple[str, Path]] = []

            class FakeStore:
                def __init__(self, base_dir):
                    self.base_dir = Path(base_dir)

                def ensure_model(self, spec):
                    target = self.base_dir / spec.repo_id.replace("/", "__") / spec.revision
                    target.mkdir(parents=True, exist_ok=True)
                    created.append((spec.repo_id, target))
                    return target

            try:
                with patch("amon.cli.LocalModelStore", FakeStore):
                    output = self._run_cli(["models", "pull"])
            finally:
                os.environ.pop("AMON_HOME", None)

            self.assertIn("jina-embeddings-v5-text-nano-retrieval", output)
            self.assertIn("jina-reranker-v3", output)
            self.assertEqual(len(created), 2)
            self.assertTrue(all(str(path).startswith(str(Path(temp_dir) / "cache" / "models")) for _, path in created))

    def test_models_pull_honors_alias_and_custom_cache_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_cache = Path(temp_dir) / "custom-model-cache"
            seen: list[Path] = []

            class FakeStore:
                def __init__(self, base_dir):
                    self.base_dir = Path(base_dir)

                def ensure_model(self, spec):
                    target = self.base_dir / spec.repo_id.replace("/", "__")
                    seen.append(target)
                    return target

            with patch("amon.cli.LocalModelStore", FakeStore):
                output = self._run_cli(["models", "pull", "embedding", "--cache-dir", str(custom_cache)])

            self.assertIn("jina-embeddings-v5-text-nano-retrieval", output)
            self.assertEqual(seen, [custom_cache / "jinaai__jina-embeddings-v5-text-nano-retrieval"])

    def _run_cli(self, args: list[str]) -> str:
        original_argv = sys.argv
        sys.argv = ["amon", *args]
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                cli.main()
        finally:
            sys.argv = original_argv
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
