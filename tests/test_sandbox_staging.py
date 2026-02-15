import base64
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.sandbox.staging import pack_input_files, rewrite_output_paths, unpack_output_files  # noqa: E402


class SandboxStagingTests(unittest.TestCase):
    def test_pack_input_files_collects_meta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            docs = project_path / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            target = docs / "a.txt"
            target.write_text("hello", encoding="utf-8")

            input_files, meta = pack_input_files(project_path, ["docs/a.txt"])

            self.assertEqual(len(input_files), 1)
            self.assertEqual(input_files[0]["path"], "docs/a.txt")
            self.assertEqual(base64.b64decode(input_files[0]["content_b64"]), b"hello")
            self.assertEqual(meta["total_bytes"], 5)
            self.assertEqual(meta["files"][0]["size"], 5)
            self.assertEqual(meta["files"][0]["path"], "docs/a.txt")
            self.assertEqual(len(meta["files"][0]["sha256"]), 64)

    def test_pack_input_files_blocks_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            with self.assertRaises(ValueError):
                pack_input_files(project_path, ["../secrets.txt"])

    def test_pack_input_files_respects_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            workspace = project_path / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "f1.txt").write_text("aa", encoding="utf-8")
            (workspace / "f2.txt").write_text("bb", encoding="utf-8")

            with self.assertRaises(ValueError):
                pack_input_files(project_path, ["workspace/f1.txt", "workspace/f2.txt"], limits={"max_input_files": 1})

            with self.assertRaises(ValueError):
                pack_input_files(project_path, ["workspace/f1.txt", "workspace/f2.txt"], limits={"max_input_total_kb": 0.001})

    def test_rewrite_output_paths_puts_files_under_prefix(self) -> None:
        files = [{"path": "result/out.txt", "content_b64": "aGVsbG8="}]
        rewritten = rewrite_output_paths(files, "docs/artifacts/run-1")
        self.assertEqual(rewritten[0]["path"], "docs/artifacts/run-1/result/out.txt")

    def test_unpack_output_files_enforces_allowed_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            payload = [
                {
                    "path": "docs/artifacts/run-1/out.txt",
                    "content_b64": base64.b64encode(b"ok").decode("ascii"),
                }
            ]
            written = unpack_output_files(project_path, payload, allowed_prefixes=["docs/", "audits/"])
            self.assertEqual(len(written), 1)
            self.assertEqual((project_path / "docs" / "artifacts" / "run-1" / "out.txt").read_text(encoding="utf-8"), "ok")

            bad = [
                {
                    "path": "workspace/private.txt",
                    "content_b64": base64.b64encode(b"bad").decode("ascii"),
                }
            ]
            with self.assertRaises(ValueError):
                unpack_output_files(project_path, bad, allowed_prefixes=["docs/", "audits/"])


if __name__ == "__main__":
    unittest.main()
