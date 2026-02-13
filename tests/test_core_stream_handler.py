import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class CoreStreamHandlerTests(unittest.TestCase):
    def test_run_self_critique_forwards_stream_handler_to_run_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                docs_dir = project_path / "docs"
                docs_dir.mkdir(parents=True, exist_ok=True)
                draft_path = docs_dir / "draft_v1.md"
                reviews_dir = docs_dir / "reviews_v1"
                final_path = docs_dir / "final_v1.md"
                final_path.write_text("done", encoding="utf-8")
                handler = object()

                with patch.object(
                    core,
                    "_resolve_doc_paths",
                    return_value=(draft_path, reviews_dir, final_path, 1),
                ), patch.object(core, "run_graph", return_value=SimpleNamespace()) as mock_run_graph:
                    core.run_self_critique("測試", project_path=project_path, stream_handler=handler)

                self.assertIs(mock_run_graph.call_args.kwargs.get("stream_handler"), handler)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_team_forwards_stream_handler_to_run_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("測試專案")
                project_path = Path(project.path)
                final_path = project_path / "docs" / "final.md"
                final_path.parent.mkdir(parents=True, exist_ok=True)
                final_path.write_text("done", encoding="utf-8")
                handler = object()

                with patch.object(core, "run_graph", return_value=SimpleNamespace()) as mock_run_graph, patch.object(
                    core, "_sync_team_tasks"
                ):
                    core.run_team("測試", project_path=project_path, stream_handler=handler)

                self.assertIs(mock_run_graph.call_args.kwargs.get("stream_handler"), handler)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
